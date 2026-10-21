"""Análise local de URLs e consulta externa de reputação estritamente opt-in."""
import base64
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_to_bytes, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .tools import AuditLogger, ToolError


class SecurityError(RuntimeError):
    pass


class PassiveUrlAnalyzer:
    MAX_URL_CHARACTERS = 2048

    def __init__(self, audit: AuditLogger):
        self.audit = audit

    def analyze(self, value: str) -> dict:
        fingerprint = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
        if not value or len(value) > self.MAX_URL_CHARACTERS:
            self.audit.record("analyze_url", "denied", fingerprint)
            raise SecurityError("A URL deve ter entre 1 e 2048 caracteres.")
        if value != value.strip() or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            self.audit.record("analyze_url", "denied", fingerprint)
            raise SecurityError("A URL contém espaços externos, barras invertidas ou controlos.")
        if re.search(r"%(?![0-9A-Fa-f]{2})", value):
            raise SecurityError("A codificação percentual da URL é inválida.")
        try:
            decoded = unquote_to_bytes(value)
        except Exception as exc:
            raise SecurityError("A codificação percentual da URL é inválida.") from exc
        if any(byte < 32 or byte == 127 for byte in decoded):
            self.audit.record("analyze_url", "denied", fingerprint)
            raise SecurityError("A URL contém controlos codificados.")
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            self.audit.record("analyze_url", "denied", fingerprint)
            raise SecurityError("A URL ou porta é inválida.") from exc
        scheme = parsed.scheme.casefold()
        if scheme not in {"http", "https"}:
            self.audit.record("analyze_url", "denied", fingerprint)
            raise SecurityError("Apenas URLs HTTP e HTTPS são aceites para análise.")
        if not parsed.netloc or not parsed.hostname:
            self.audit.record("analyze_url", "denied", fingerprint)
            raise SecurityError("A URL deve incluir um hostname.")
        host = parsed.hostname.rstrip(".").casefold()
        if not host or "%" in host:
            raise SecurityError("O hostname é inválido.")
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise SecurityError("O hostname internacionalizado é inválido.") from exc
        labels = ascii_host.split(".")
        try:
            parsed_ip = ipaddress.ip_address(ascii_host)
        except ValueError:
            parsed_ip = None
        invalid_label = parsed_ip is None and any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in labels
        )
        if len(ascii_host) > 253 or any(not label or len(label) > 63 for label in labels) or invalid_label:
            raise SecurityError("O hostname excede os limites DNS.")

        findings = []
        score = 0
        def add(code, points, explanation):
            nonlocal score
            score += points
            findings.append({"code": code, "points": points, "explanation": explanation})

        if parsed.username is not None or parsed.password is not None:
            add("userinfo_present", 60, "Credenciais ou texto antes de @ podem ocultar o hostname real.")
        if scheme == "http":
            add("unencrypted_http", 20, "HTTP não protege o transporte com TLS.")
        if ascii_host == "localhost" or ascii_host.endswith(".localhost"):
            add("localhost", 80, "O destino refere-se ao contexto local.")
        ip = parsed_ip
        if ip is not None:
            add("ip_literal", 20, "A URL usa um endereço IP literal em vez de domínio.")
            if not ip.is_global:
                add("non_public_ip", 80, "O endereço IP não é global e pode alcançar recursos internos.")
        elif re.fullmatch(r"[0-9.]+", ascii_host):
            add("numeric_hostname", 40, "Hostname numérico ambíguo; não foi tratado como IPv4 decimal válido.")
        if any(label.startswith("xn--") for label in labels):
            add("punycode", 20, "O domínio usa IDNA/Punycode; confirma visualmente o hostname.")
        default_port = 443 if scheme == "https" else 80
        if port is not None and port != default_port:
            add("non_default_port", 10, "A URL usa uma porta não padrão.")
        if len(labels) > 5:
            add("many_subdomains", 10, "O hostname tem muitas etiquetas/subdomínios.")
        if len(ascii_host) > 120:
            add("long_hostname", 10, "O hostname é invulgarmente longo.")
        if len(parsed.query) > 500:
            add("long_query", 10, "A query string é extensa.")

        if ip is not None and ip.version == 6:
            display_host = f"[{ascii_host}]"
        else:
            display_host = ascii_host
        authority = display_host + ((f":{port}") if port is not None else "")
        canonical = urlunsplit((scheme, authority, parsed.path or "/", parsed.query, parsed.fragment))
        level = "high" if score >= 60 else "medium" if score >= 20 else "low"
        self.audit.record("analyze_url", "success", fingerprint)
        return {
            "canonical_url": canonical,
            "hostname": ascii_host,
            "scheme": scheme,
            "port": port or default_port,
            "risk_score": min(score, 100),
            "risk_level": level,
            "findings": findings,
            "verdict": "heuristic_review_required",
            "network_accessed": False,
            "limitations": "Análise sintática; não verifica conteúdo, DNS, reputação ou malware.",
        }


class VirusTotalUrlReputation:
    """Obtém um relatório já existente; nunca submete uma URL para análise."""

    API_ROOT = "https://www.virustotal.com/api/v3"
    MAX_RESPONSE_BYTES = 1024 * 1024
    PRIVATE_SUFFIXES = (".local", ".internal", ".lan", ".home", ".corp")

    def __init__(self, audit: AuditLogger, api_key: str, timeout: float = 15.0, opener=None):
        api_key = (api_key or "").strip()
        if len(api_key) > 512:
            raise SecurityError("A chave VIRUSTOTAL_API_KEY é inválida.")
        if not 1 <= timeout <= 60:
            raise SecurityError("O timeout deve estar entre 1 e 60 segundos.")
        self.audit = audit
        self.api_key = api_key
        self.timeout = timeout
        self.opener = opener or urlopen

    def lookup(self, value: str, approved: bool = False) -> dict:
        fingerprint = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
        if approved is not True:
            self.audit.record("lookup_url_reputation", "denied", fingerprint)
            raise SecurityError("A consulta externa exige --approve-external.")
        if not self.api_key:
            self.audit.record("lookup_url_reputation", "denied", fingerprint)
            raise SecurityError("Define VIRUSTOTAL_API_KEY antes da consulta externa.")

        local = PassiveUrlAnalyzer(self.audit).analyze(value)
        codes = {finding["code"] for finding in local["findings"]}
        hostname = local["hostname"]
        if (
            codes & {"localhost", "non_public_ip", "userinfo_present", "numeric_hostname"}
            or "." not in hostname
            or hostname.endswith(self.PRIVATE_SUFFIXES)
        ):
            self.audit.record("lookup_url_reputation", "denied", fingerprint)
            raise SecurityError(
                "A URL parece local, privada ou ambígua e não será enviada ao VirusTotal."
            )

        canonical = local["canonical_url"]
        url_id = base64.urlsafe_b64encode(canonical.encode("utf-8")).decode("ascii").rstrip("=")
        request = Request(
            f"{self.API_ROOT}/urls/{url_id}",
            headers={"Accept": "application/json", "x-apikey": self.api_key},
            method="GET",
        )
        self.audit.record('lookup_url_reputation', 'intent', fingerprint)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = response.read(self.MAX_RESPONSE_BYTES + 1)
            if len(payload) > self.MAX_RESPONSE_BYTES:
                raise SecurityError("A resposta do VirusTotal excedeu 1 MiB.")
            document = json.loads(payload.decode("utf-8"))
            result = self._parse_report(document, local)
        except HTTPError as exc:
            exc.close()
            if exc.code == 404:
                result = self._not_found(local)
            else:
                self.audit.record("lookup_url_reputation", "error", fingerprint)
                raise SecurityError(f"O VirusTotal devolveu HTTP {exc.code}.") from exc
        except (URLError, socket.timeout, TimeoutError) as exc:
            self.audit.record("lookup_url_reputation", "error", fingerprint)
            raise SecurityError("Não foi possível contactar o VirusTotal.") from exc
        except (
            UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError,
            OverflowError, OSError,
        ) as exc:
            self.audit.record("lookup_url_reputation", "error", fingerprint)
            raise SecurityError("O VirusTotal devolveu uma resposta inválida.") from exc
        except SecurityError:
            self.audit.record("lookup_url_reputation", "error", fingerprint)
            raise

        outcome = "success" if result["found"] else "not_found"
        try:
            self.audit.record("lookup_url_reputation", outcome, fingerprint)
        except ToolError:
            result['audit_completed'] = False
            result['warning'] = 'external_request_completed_final_audit_failed_do_not_retry'
        else:
            result['audit_completed'] = True
        return result

    @staticmethod
    def _not_found(local: dict) -> dict:
        return {
            "provider": "virustotal",
            "found": False,
            "external_request_performed": True,
            "submitted_for_analysis": False,
            "local_analysis": local,
            "interpretation": "Sem relatório existente; isto não significa que a URL seja segura.",
            "privacy_notice": "Um identificador Base64 reversível da URL canónica foi enviado ao VirusTotal.",
        }

    @classmethod
    def _parse_report(cls, document: dict, local: dict) -> dict:
        if not isinstance(document, dict) or not isinstance(document.get("data"), dict):
            raise ValueError("missing data")
        attributes = document["data"].get("attributes")
        if not isinstance(attributes, dict):
            raise ValueError("missing attributes")
        raw_stats = attributes.get("last_analysis_stats")
        if not isinstance(raw_stats, dict):
            raise ValueError("missing stats")
        stats = {}
        for name in ("harmless", "malicious", "suspicious", "undetected", "timeout"):
            value = raw_stats.get(name, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("invalid stats")
            stats[name] = value
        if stats["malicious"]:
            interpretation = "malicious_engines_flagged"
        elif stats["suspicious"]:
            interpretation = "suspicious_engines_flagged"
        else:
            interpretation = "no_engines_flagged_not_a_safety_verdict"
        timestamp = attributes.get("last_analysis_date")
        if timestamp is not None and (isinstance(timestamp, bool) or not isinstance(timestamp, int)):
            raise ValueError("invalid timestamp")
        analyzed_at = (
            datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            if timestamp is not None else None
        )
        return {
            "provider": "virustotal",
            "found": True,
            "stats": stats,
            "last_analysis_at": analyzed_at,
            "interpretation": interpretation,
            "external_request_performed": True,
            "submitted_for_analysis": False,
            "local_analysis": local,
            "privacy_notice": "Um identificador Base64 reversível da URL canónica foi enviado ao VirusTotal.",
        }
