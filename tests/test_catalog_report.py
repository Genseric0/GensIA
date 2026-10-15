import subprocess
import sys
import unittest
from html.parser import HTMLParser
from gensia.agent_catalog import AgentInfo, Capability
from gensia.catalog_report import render_report


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)


class CatalogReportTests(unittest.TestCase):
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
