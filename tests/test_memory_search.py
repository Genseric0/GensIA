import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gensia.memory import MemoryStore, MemoryError


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'notes' / 'memory.sqlite3'
        self.store = MemoryStore(self.path)

    def test_missing_database_is_not_created(self):
        self.assertEqual(self.store.search('DNS'), [])
        self.assertFalse(self.path.parent.exists())

    def test_key_value_unicode_and_case(self):
        self.store.set('Redes', 'Estudar DNS e propagação')
        for query in ('Redes', 'DNS', 'propagação'):
            self.assertEqual(self.store.search(query)[0]['key'], 'Redes')
        for query in ('redes', 'dns', 'propagacao', 'ausente'):
            self.assertEqual(self.store.search(query), [])

    def test_wildcards_and_sql_are_literal(self):
        for i, query in enumerate(('%', '_', "' OR 1=1 --")):
            self.store.set(str(i), query)
            self.assertEqual(len(self.store.search(query)), 1)
        self.assertEqual(len(self.store.list()), 3)

    def test_pagination_and_no_mutation(self):
        for key in ('c', 'a', 'b'):
            self.store.set(key, 'DNS')
        before = self.path.read_bytes()
        self.assertEqual([row['key'] for row in self.store.search('DNS', 1, 1)], ['b'])
        self.assertEqual(self.store.search('DNS', 1, 3), [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_arguments(self):
        for query in ('', ' ', '\x00', 'x' * 201):
            with self.assertRaises(MemoryError):
                self.store.search(query)
        for limit, offset in ((0, 0), (201, 0), (1, -1), (True, 0), (1, 0.5)):
            with self.assertRaises(MemoryError):
                self.store.search('DNS', limit, offset)
        self.assertFalse(self.path.exists())

    def test_corrupt_database(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b'not a database')
        with self.assertRaises(MemoryError):
            self.store.search('DNS')

    def test_real_cli(self):
        self.store.set('tema', 'DNS')
        result = subprocess.run(
            [sys.executable, '-m', 'gensia', 'memory', '--db', str(self.path),
             'search', 'DNS', '--limit', '1'],
            cwd=Path(__file__).resolve().parents[1], capture_output=True,
            text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['value'], 'DNS')
