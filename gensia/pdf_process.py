"""Opt-in supervised PDF extraction. A process boundary, not an OS sandbox."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

# -I omits the script directory. Only bootstrap our own trusted checkout.
if __name__ == '__main__' and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gensia.documents import DocumentError, SafePdfDocuments
from gensia.tools import AuditLogger, ToolError

MAX_OUTPUT_BYTES = 2 * 1024 * 1024


def extract_pdf_process(workspace, relative_path, audit_path, max_mib=10,
                        max_pages=25, timeout=30.0, runner=None):
    if (type(timeout) not in (int, float) or not math.isfinite(timeout)
            or not 1 <= timeout <= 120):
        raise DocumentError('Timeout PDF deve estar entre 1 e 120 segundos.')
    if type(max_mib) is not int or not 1 <= max_mib <= SafePdfDocuments.MAX_READ_MIB:
        raise DocumentError('Limite PDF inválido (1–50 MiB).')
    if type(max_pages) is not int or not 1 <= max_pages <= SafePdfDocuments.MAX_PAGES:
        raise DocumentError('Limite de páginas inválido (1–100).')
    try:
        audit_file = Path(audit_path).absolute()
        audit = AuditLogger(audit_file)
        reader = SafePdfDocuments(workspace, audit)
        _, label = reader._resolve(relative_path)
        request = json.dumps({'workspace': str(reader.workspace), 'path': label,
                              'audit': str(audit_file), 'max_mib': max_mib,
                              'max_pages': max_pages}).encode('utf-8')
        if len(request) > 65536:
            raise DocumentError('Caminhos PDF excedem o limite de comunicação.')
        command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker']
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
        with tempfile.TemporaryDirectory(prefix='gensia-pdf-') as temp:
            with tempfile.TemporaryFile(mode='w+b') as output:
                try:
                    completed = (runner or subprocess.run)(
                        command, input=request, stdout=output, stderr=subprocess.DEVNULL,
                        cwd=temp, env=environment, shell=False, close_fds=True,
                        timeout=timeout, check=False)
                except subprocess.TimeoutExpired as exc:
                    audit.record('read_pdf_process', 'timeout', label)
                    raise DocumentError('A extração PDF excedeu o prazo; o processo foi encerrado.') from exc
                if completed.returncode != 0:
                    raise DocumentError('A extração PDF falhou. Verifica o PDF, auditoria e requirements-documents.txt.')
                output.seek(0)
                raw = output.read(MAX_OUTPUT_BYTES + 1)
        if len(raw) > MAX_OUTPUT_BYTES:
            raise DocumentError('Resultado PDF excedeu 2 MiB.')
        result = json.loads(raw.decode('utf-8'))
        if not isinstance(result, dict) or set(result) != {'path', 'bytes', 'characters', 'sha256', 'pages', 'content'}:
            raise DocumentError('Resultado PDF inválido.')
        if (result['path'] != label or not isinstance(result['content'], str)
                or len(result['content']) > 210000
                or type(result['characters']) is not int
                or result['characters'] != len(result['content'])
                or type(result['bytes']) is not int or not 0 <= result['bytes'] <= max_mib * 1024 * 1024
                or type(result['pages']) is not int or not 1 <= result['pages'] <= max_pages
                or not isinstance(result['sha256'], str) or len(result['sha256']) != 64
                or any(char not in '0123456789abcdef' for char in result['sha256'])):
            raise DocumentError('Metadados PDF inválidos.')
        result['supervision'] = {'separate_process': True, 'timeout_seconds': timeout,
                                 'os_sandbox': False}
        return result
    except (OSError, ToolError, UnicodeError, ValueError, RecursionError) as exc:
        raise DocumentError('Não foi possível executar ou validar a extração PDF supervisionada.') from exc


def _worker():
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            return 8
        request = json.loads(raw.decode('utf-8'))
        reader = SafePdfDocuments(request['workspace'], AuditLogger(request['audit']))
        document = reader.read_pdf(request['path'], request['max_mib'], request['max_pages'])
        sys.stdout.buffer.write(json.dumps(document.as_dict(), ensure_ascii=False).encode('utf-8'))
        return 0
    except Exception:
        # Do not propagate parser logs, local paths or document contents as errors.
        return 8


if __name__ == '__main__':
    raise SystemExit(_worker() if sys.argv[1:] == ['--worker'] else 2)
