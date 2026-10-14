"""Cache local e atualização explícita do catálogo oficial CISA KEV."""
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .tools import AuditLogger


class KevError(RuntimeError):
    pass


class CisaKevCatalog:
    FEED_URL = (
        "https://www.cisa.gov/sites/default/files/feeds/"
        "known_exploited_vulnerabilities.json"
    )
    MAX_BYTES = 10 * 1024 * 1024
    CVE_PATTERN = re.compile(r"CVE-[0-9]{4}-[0-9]{4,19}", re.IGNORECASE)
    REQUIRED_ENTRY_FIELDS = (
        "cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded",
        "shortDescription", "requiredAction", "dueDate",
        "knownRansomwareCampaignUse", "notes",
    )

    def __init__(self, audit: AuditLogger, opener=None):
        self.audit = audit
        self.opener = opener or urlopen

    def update(self, cache, approved=False, timeout=30.0) -> dict:
        if not approved:
            self.audit.record("update_cisa_kev", "denied", self.FEED_URL)
            raise KevError("A atualização externa exige --approve-external.")
        if not 1 <= timeout <= 60:
            raise KevError("O timeout deve estar entre 1 e 60 segundos.")
        path = self._cache_path(cache, require_existing=False)
        request = Request(
            self.FEED_URL,
            headers={"Accept": "application/json", "User-Agent": "GensIA/0.15"},
            method="GET",
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                payload = response.read(self.MAX_BYTES + 1)
        except HTTPError as exc:
            self.audit.record("update_cisa_kev", "error", self.FEED_URL)
            raise KevError(f"A CISA devolveu HTTP {exc.code}.") from exc
        except (URLError, socket.timeout, TimeoutError, OSError) as exc:
            self.audit.record("update_cisa_kev", "error", self.FEED_URL)
            raise KevError("Não foi possível descarregar o catálogo CISA KEV.") from exc
        if len(payload) > self.MAX_BYTES:
            self.audit.record("update_cisa_kev", "error", self.FEED_URL)
            raise KevError("O catálogo CISA KEV excedeu 10 MiB.")
        try:
            document = self._decode_and_validate(payload)
            digest = hashlib.sha256(payload).hexdigest()
            unchanged = False
            if path.exists():
                unchanged = hashlib.sha256(path.read_bytes()).hexdigest() == digest
            if not unchanged:
                self._atomic_write(path, payload)
        except OSError as exc:
            self.audit.record("update_cisa_kev", "error", self.FEED_URL)
            raise KevError("Não foi possível ler o cache CISA KEV existente.") from exc
        except KevError:
            self.audit.record("update_cisa_kev", "error", self.FEED_URL)
            raise
        self.audit.record("update_cisa_kev", "unchanged" if unchanged else "success", self.FEED_URL)
        return {
            "source": "CISA Known Exploited Vulnerabilities Catalog",
            "source_url": self.FEED_URL,
            "catalog_version": document["catalogVersion"],
            "date_released": document["dateReleased"],
            "entries": document["count"],
            "cache": str(path),
            "sha256": digest,
            "external_request_performed": True,
            "cache_changed": not unchanged,
        }

    def check(self, cve_id: str, cache) -> dict:
        normalized = cve_id.strip().upper()
        if not self.CVE_PATTERN.fullmatch(normalized):
            self.audit.record("check_cisa_kev", "denied", normalized)
            raise KevError("Usa um identificador CVE válido, por exemplo CVE-2021-44228.")
        path = self._cache_path(cache, require_existing=True)
        try:
            if path.stat().st_size > self.MAX_BYTES:
                raise KevError("O cache CISA KEV excedeu 10 MiB.")
            payload = path.read_bytes()
        except OSError as exc:
            raise KevError("Não foi possível ler o cache CISA KEV.") from exc
        document = self._decode_and_validate(payload)
        match = next(
            (item for item in document["vulnerabilities"] if item["cveID"].upper() == normalized),
            None,
        )
        self.audit.record("check_cisa_kev", "found" if match else "not_found", normalized)
        result = {
            "cve_id": normalized,
            "in_kev": match is not None,
            "catalog_version": document["catalogVersion"],
            "date_released": document["dateReleased"],
            "cache_sha256": hashlib.sha256(payload).hexdigest(),
            "local_only": True,
            "network_accessed": False,
            "meaning": (
                "A CISA inclui esta CVE entre vulnerabilidades exploradas no mundo real."
                if match else
                "Não consta deste cache; isto não prova ausência de exploração."
            ),
            "due_date_notice": (
                "A data-limite do catálogo é uma exigência para agências federais civis dos EUA; "
                "fora desse âmbito serve como sinal de priorização, não como prazo legal local."
            ),
        }
        if match:
            result["entry"] = {field: match[field] for field in self.REQUIRED_ENTRY_FIELDS}
        return result

    @classmethod
    def _decode_and_validate(cls, payload: bytes) -> dict:
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KevError("O catálogo CISA KEV não contém JSON UTF-8 válido.") from exc
        if not isinstance(document, dict):
            raise KevError("O catálogo CISA KEV tem uma estrutura inválida.")
        for field in ("title", "catalogVersion", "dateReleased"):
            value = document.get(field)
            if not isinstance(value, str) or not value or len(value) > 200:
                raise KevError(f"O campo {field} do catálogo é inválido.")
        try:
            datetime.fromisoformat(document["dateReleased"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise KevError("A data de publicação do catálogo é inválida.") from exc
        count = document.get("count")
        items = document.get("vulnerabilities")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise KevError("A contagem do catálogo é inválida.")
        if not isinstance(items, list) or len(items) != count or count > 100000:
            raise KevError("A lista do catálogo não corresponde à contagem declarada.")
        seen = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise KevError(f"A entrada {index} do catálogo é inválida.")
            for field in cls.REQUIRED_ENTRY_FIELDS:
                value = item.get(field)
                if not isinstance(value, str) or len(value) > 20000:
                    raise KevError(f"O campo {field} da entrada {index} é inválido.")
            cve = item["cveID"].upper()
            if not cls.CVE_PATTERN.fullmatch(cve) or cve in seen:
                raise KevError(f"O CVE da entrada {index} é inválido ou duplicado.")
            seen.add(cve)
            try:
                date.fromisoformat(item["dateAdded"])
                date.fromisoformat(item["dueDate"])
            except ValueError as exc:
                raise KevError(f"Uma data da entrada {index} é inválida.") from exc
        return document

    @staticmethod
    def _cache_path(cache, require_existing: bool) -> Path:
        path = Path(cache).expanduser()
        if path.exists() and path.is_symlink():
            raise KevError("O cache CISA KEV não pode ser um link simbólico.")
        if require_existing and not path.is_file():
            raise KevError("Cache CISA KEV ausente; executa primeiro security kev-update.")
        if path.exists() and not path.is_file():
            raise KevError("O caminho do cache CISA KEV não é um ficheiro.")
        return path.resolve(strict=False)

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise KevError("Não foi possível guardar o cache CISA KEV.") from exc
        finally:
            temporary.unlink(missing_ok=True)
