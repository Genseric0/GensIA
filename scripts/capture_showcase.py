"""Render actual CLI stdout/stderr as SVG, with accompanying raw transcripts.

No GUI is simulated. Uses synthetic data in a temporary directory only.
Run from repository root: python scripts/capture_showcase.py
"""
import html
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"


def capture(slug, title, commands, cwd):
    transcript = []
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    for args in commands:
        display = "python " + " ".join(args)
        result = subprocess.run([sys.executable, *args], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)
        transcript.extend(["$ " + display, result.stdout.rstrip()])
        if result.stderr:
            transcript.append(result.stderr.rstrip())
        transcript.append("")
    raw = "\n".join(transcript)
    (OUT / (slug + ".txt")).write_text(raw, encoding="utf-8")
    lines = []
    for line in raw.splitlines():
        lines.extend(textwrap.wrap(line, width=104, replace_whitespace=False,
                                  drop_whitespace=False) or [""])
    height = 140 + len(lines) * 24
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{height}" viewBox="0 0 1280 {height}">',
             f'<title>{html.escape(title)}</title>',
             f'<rect width="1280" height="{height}" rx="16" fill="#0d1117"/>',
             '<text x="32" y="44" fill="#79c0ff" font-family="monospace" font-size="23">GensIA / '+html.escape(title)+'</text>',
             '<text x="32" y="75" fill="#8b949e" font-family="monospace" font-size="16">Saída real da CLI • renderização documental • v0.21.0</text>']
    for i, line in enumerate(lines):
        color = "#7ee787" if line.startswith("$") else "#e6edf3"
        parts.append(f'<text x="32" y="{116+i*24}" xml:space="preserve" fill="{color}" font-family="monospace" font-size="18">{html.escape(line)}</text>')
    parts.append('</svg>')
    (OUT / (slug + ".svg")).write_text("\n".join(parts), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gensia-showcase-") as tmp:
        Path(tmp, "redes.txt").write_text("DNS resolve nomes em endereços IP.\nDHCP distribui configuração de rede.\n", encoding="utf-8")
        capture("01-terminal", "Terminal e comandos", [["-m", "gensia", "--help"]], tmp)
        capture("02-agentes", "Equipa de agentes", [["-m", "gensia.agents", "list"]], tmp)
        capture("03-seguranca", "Análise passiva de URL", [["-m", "gensia", "security", "url", "http://example.com/login"]], tmp)
        capture("04-memoria", "Memória local explícita", [
            ["-m", "gensia", "memory", "--db", "demo.sqlite3", "set", "tema", "Redes"],
            ["-m", "gensia", "memory", "--db", "demo.sqlite3", "get", "tema"]], tmp)
        capture("05-documentos", "Pesquisa local em documentos", [["-m", "gensia", "document", "--workspace", ".", "search", "DNS", "redes.txt"]], tmp)
    print("5 imagens SVG e 5 transcrições geradas a partir de execuções reais.")


if __name__ == "__main__":
    main()
