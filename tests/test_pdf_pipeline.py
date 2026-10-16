import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from gensia.agents import StudyAgent
from gensia.cli import main
from gensia.documents import DocumentError, SafePdfDocuments
from gensia.pdf_process import SupervisedPdfDocuments
from gensia.search import LocalDocumentSearch
from gensia.tools import AuditLogger


class PdfPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audit = AuditLogger(self.root / 'audit.jsonl')
        self.content = '--- Página 1 ---\nDNS resolve nomes.'
        self.result = {'path': 'redes.pdf', 'content': self.content, 'bytes': 100,
                       'characters': len(self.content), 'sha256': 'a' * 64, 'pages': 1}
        self.provider = Mock()
        self.provider.status.return_value = {'provider': 'ollama', 'local_only': True, 'model': 'fixture'}
        self.provider.reply.return_value = 'DNS resolve nomes [p. 1] [fonte 1].'

    def test_adapter_forwards_limits_and_preserves_metadata(self):
        with patch('gensia.pdf_process.extract_pdf_process', return_value=self.result) as extract:
            reader = SupervisedPdfDocuments(self.root, self.audit, pdf_timeout=12)
            document = reader.read_pdf('redes.pdf', 2, 3)
        extract.assert_called_once_with(self.root.resolve(), 'redes.pdf', self.audit.path, 2, 3, 12)
        self.assertEqual(document.as_dict(), self.result)

    def test_summary_and_question_use_supervision_and_keep_citations(self):
        reader = SupervisedPdfDocuments(self.root, self.audit)
        with patch('gensia.pdf_process.extract_pdf_process', return_value=self.result) as extract:
            summary = reader.summarize_pdf('redes.pdf', self.provider)
            answer = reader.ask_pdf('redes.pdf', 'DNS?', self.provider)
        self.assertEqual(extract.call_count, 2)
        self.assertEqual(summary['source']['sha256'], 'a' * 64)
        self.assertEqual(answer['cited_pages'], [1])
        prompt_data = json.loads(self.provider.reply.call_args.args[0].split('\n\n', 1)[1])
        self.assertEqual(prompt_data['document'], self.content)

    def test_extraction_failure_never_calls_model_or_raw_fallback(self):
        reader = SupervisedPdfDocuments(self.root, self.audit)
        with patch('gensia.pdf_process.extract_pdf_process', side_effect=DocumentError('timeout')):
            with patch.object(SafePdfDocuments, 'read_pdf') as raw:
                for operation in (lambda: reader.summarize_pdf('redes.pdf', self.provider),
                                  lambda: reader.ask_pdf('redes.pdf', 'DNS?', self.provider)):
                    with self.assertRaises(DocumentError):
                        operation()
                raw.assert_not_called()
        self.provider.reply.assert_not_called()

    def test_mixed_search_preserves_page_and_line_locations(self):
        (self.root / 'aula.txt').write_text('DNS usa consultas.', encoding='utf-8')
        with patch('gensia.pdf_process.extract_pdf_process', return_value=self.result) as extract:
            found = LocalDocumentSearch(self.root, self.audit, pdf_timeout=14).search(
                'DNS', ['aula.txt', 'redes.pdf'])
        self.assertEqual(extract.call_args.args[-1], 14)
        self.assertEqual(len(found['results']), 2)
        self.assertEqual({item['path']: item['location'] for item in found['results']},
                         {'aula.txt': {'lines': [1, 1]}, 'redes.pdf': {'page': 1}})

    def test_study_agent_propagates_failure_before_model_reply(self):
        with patch('gensia.pdf_process.extract_pdf_process', side_effect=DocumentError('timeout')) as extract:
            with self.assertRaises(DocumentError):
                StudyAgent(self.root, self.audit).run('DNS?', ['redes.pdf'], self.provider)
        extract.assert_called_once()
        self.provider.reply.assert_not_called()

    def test_cli_summary_and_question_forward_timeout(self):
        from contextlib import redirect_stdout
        from io import StringIO
        for command in (['pdf-summarize', 'redes.pdf'], ['pdf-ask', 'redes.pdf', 'DNS?']):
            with patch('gensia.cli._provider', return_value=self.provider):
                with patch('gensia.pdf_process.extract_pdf_process', return_value=self.result) as extract:
                    with redirect_stdout(StringIO()):
                        code = main(['document', '--workspace', str(self.root),
                                     '--audit', str(self.audit.path), *command, '--pdf-timeout', '9'])
                    self.assertEqual(code, 0)
                    self.assertEqual(extract.call_args.args[-1], 9)

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'Optional pypdf required')
    def test_default_read_and_search_with_real_pdf_worker(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 20 40 Td (DNS resolve nomes.) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        writer.write(self.root / 'redes.pdf')
        base = [sys.executable, '-m', 'gensia', 'document', '--workspace', str(self.root),
                '--audit', str(self.audit.path)]
        for command in (['pdf-read', 'redes.pdf'], ['search', 'DNS', 'redes.pdf']):
            result = subprocess.run(base + command + ['--pdf-timeout', '10'],
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            if command[0] == 'pdf-read':
                self.assertIn('DNS resolve nomes', output['content'])
            else:
                self.assertEqual(output['results'][0]['location'], {'page': 1})
