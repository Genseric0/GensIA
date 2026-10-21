"""Build gate: install one wheel offline in a fresh venv and run from elsewhere."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    args = parser.parse_args(argv)
    wheel = args.wheel.resolve(strict=True)
    if wheel.is_dir():
        candidates = sorted(wheel.glob('*.whl'))
        if len(candidates) != 1:
            parser.error('Expected a directory containing exactly one wheel')
        wheel = candidates[0]
    if not wheel.is_file() or wheel.suffix != '.whl':
        parser.error('Expected one regular wheel file')
    with tempfile.TemporaryDirectory(prefix='gensia-installed-check-') as temporary:
        root = Path(temporary)
        environment = root / 'environment'
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        commands = [
            [str(python), '-I', '-B', '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)],
            [str(python), '-I', '-B', '-m', 'gensia', '--version'],
            [str(python), '-I', '-B', '-m', 'gensia', '--help'],
            [str(python), '-I', '-B', '-m', 'gensia.api', '--help'],
            [str(python), '-I', '-B', '-c',
             "from importlib.resources import files; "
             "assets=('panel.html','panel.js','panel.css','app.html','app.js','app.css'); "
             "missing=[name for name in assets if not files('gensia').joinpath('web',name).is_file()]; "
             "raise SystemExit(1 if missing else 0)"],
            [str(python), '-I', '-B', '-c',
             "from pathlib import Path; "
             "from gensia.memory import MemoryStore; "
             "from gensia.memory_backup import backup_notes; "
             "from gensia.memory_restore import restore_notes; "
             "source=MemoryStore(Path('synthetic.sqlite3')); "
             "source.set('idioma','Português 👋'); "
             "before=source.get('idioma'); "
             "backup_notes(source,Path('synthetic.json')); "
             "restored=MemoryStore(Path('restored.sqlite3')); "
             "restore_notes(restored,Path('synthetic.json'),approved=True); "
             "raise SystemExit(0 if restored.get('idioma')==before else 1)"],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=120, check=False)
            if result.returncode:
                print(json.dumps({'installed_wheel_check': 'failed', 'step': commands.index(command)}))
                return 1
    print(json.dumps({'installed_wheel_check': 'passed', 'steps': len(commands),
                      'optional_extras_installed': False, 'model_started': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
