import subprocess
import sys
import unittest
import contextlib
import io
import tempfile
from pathlib import Path
from html.parser import HTMLParser
from unittest.mock import patch
from gensia.agent_catalog import AgentInfo, Capability
from gensia.catalog_report import render_report, main


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)


class CatalogReportTests(unittest.TestCase):
    def export(self, path):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(["--output", str(path)])

    def test_export_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catálogo.html"
            self.assertEqual(self.export(path), 0)
            self.assertEqual(path.read_bytes(), render_report().encode("utf-8"))

    def test_existing_files_preserved_including_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.html"
            for content in (b"", b"personal data"):
                path.write_bytes(content)
                self.assertEqual(self.export(path), 13)
                self.assertEqual(path.read_bytes(), content)

    def test_missing_parent_is_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing" / "catalog.html"
            self.assertEqual(self.export(path), 14)
            self.assertFalse(path.parent.exists())

    def test_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            link = Path(tmp) / "catalog.html"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            self.assertEqual(self.export(link), 13)
            self.assertFalse(target.exists())
            target.write_bytes(b"preserve")
            self.assertEqual(self.export(link), 13)
            self.assertEqual(target.read_bytes(), b"preserve")

    def test_export_real_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.html"
            command = [sys.executable, "-m", "gensia.catalog_report", "--output", str(path)]
            first = subprocess.run(command, capture_output=True, timeout=10)
            second = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual((first.returncode, second.returncode), (0, 13))
            self.assertEqual(path.read_text(encoding="utf-8"), render_report())

    def test_dangling_symlink_is_rejected_before_platform_open(self):
        # Exercise the guard even on platforms whose open('x') follows dangling
        # links; this regression must not depend on filesystem link privileges.
        with patch.object(Path, 'is_symlink', return_value=True):
            with patch.object(Path, 'open') as opened:
                self.assertEqual(self.export(Path('synthetic-link.html')), 13)
        opened.assert_not_called()

    def test_reparse_point_is_rejected_before_platform_open(self):
        from types import SimpleNamespace
        with patch.object(Path, 'is_symlink', return_value=False):
            with patch.object(Path, 'lstat', return_value=SimpleNamespace(st_file_attributes=0x400)):
                with patch.object(Path, 'open') as opened:
                    self.assertEqual(self.export(Path('synthetic-reparse.html')), 13)
        opened.assert_not_called()

    def test_report_has_four_cards_and_honest_state(self):
        report = render_report()
        parser = Elements()
        parser.feed(report)
        self.assertEqual(parser.tags.count("article"), 4)
        self.assertIn("Dependências não verificadas", report)
        self.assertIn("não indica agentes ativos", report)

    def test_metadata_is_escaped(self):
        payload = '<script>alert("x")</script>'
        agent = AgentInfo(payload, payload, (Capability(payload, (payload,), "none", (payload,)),))
        report = render_report((agent,))
        self.assertNotIn(payload, report)
        self.assertEqual(report.count("&lt;script&gt;"), 5)

    def test_no_executable_or_remote_elements(self):
        parser = Elements()
        parser.feed(render_report())
        self.assertFalse(set(parser.tags) & {"script", "iframe", "img", "link", "form", "object"})
        self.assertFalse(any(k in ("src", "href") or k.startswith("on") for k, v in parser.attrs))
        self.assertIn("default-src 'none'", render_report())

    def test_cli_and_import_do_not_load_execution_modules(self):
        result = subprocess.run([sys.executable, "-m", "gensia.catalog_report"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), render_report().strip())
        code = "import sys; import gensia.catalog_report; assert not any(x in sys.modules for x in ['gensia.agents', 'gensia.providers', 'gensia.tools', 'gensia.doctor'])"
        subprocess.run([sys.executable, "-c", code], check=True, timeout=10)
