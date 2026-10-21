"""Small local signature check; not a substitute for Gitleaks or a full history audit."""
import argparse
import json
from pathlib import Path
import re
import subprocess

PATTERNS = {
    'github_classic_token': re.compile(rb'gh[pousr]_[A-Za-z0-9]{36}\b'),
    'github_fine_grained_token': re.compile(rb'github_pat_[A-Za-z0-9_]{70,}\b'),
    'openai_project_token': re.compile(rb'sk-proj-[A-Za-z0-9_-]{40,}\b'),
    'aws_access_key_id': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private_key_header': re.compile(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
}
TEXT_SUFFIXES = {'.py', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.jsx', '.json', '.toml',
                 '.yml', '.yaml', '.md', '.txt', '.html', '.css', '.ini', '.cfg', '.sh', '.ps1'}
MAX_FILE_BYTES = 2 * 1024 * 1024


def findings(data):
    result = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(data):
            result.append({'kind': kind, 'line': data.count(b'\n', 0, match.start()) + 1})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = args.root.resolve(strict=True)
    try:
        paths = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                               cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=30, check=True).stdout
        rows, checked = [], 0
        for name in sorted(set(paths.split(b'\0')) - {b''}):
            relative = Path(name.decode('utf-8', errors='strict'))
            candidate = root / relative
            if relative.is_absolute() or '..' in relative.parts or candidate.is_symlink():
                raise ValueError('unsafe repository path')
            if not candidate.exists():
                continue  # A tracked deletion has no current bytes to inspect.
            if relative.name == '.env':
                rows.append({'file': relative.as_posix(), 'kind': 'tracked_environment_file', 'line': 1})
            if relative.suffix not in TEXT_SUFFIXES and not relative.name.startswith('.env'):
                continue
            if not candidate.is_file() or candidate.stat().st_size > MAX_FILE_BYTES:
                raise ValueError('source file unavailable or too large')
            with candidate.open('rb') as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError('source file grew during read')
            checked += 1
            rows.extend({'file': relative.as_posix(), **item} for item in findings(data))
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError):
        print(json.dumps({'secret_signature_check': 'incomplete', 'values_recorded': False}))
        return 2
    print(json.dumps({'secret_signature_check': 'failed' if rows else 'passed',
                      'files_checked': checked, 'findings': rows, 'values_recorded': False,
                      'full_git_history_scanned': False}))
    return 1 if rows else 0


if __name__ == '__main__':
    raise SystemExit(main())
