from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
from io import StringIO
from gensia.cli import main
from gensia.memory import MemoryStore, MemoryError


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data" / "memory.sqlite3"
        self.store = MemoryStore(self.path)

    def test_reads_do_not_create_database(self):
        self.assertEqual(self.store.list(), [])
        self.assertIsNone(self.store.get("missing"))
        self.assertFalse(self.path.parent.exists())

    def test_persists_across_processes_and_updates(self):
        root = Path(__file__).resolve().parents[1]
        def run(*args):
            p = subprocess.run([sys.executable, "-m", "gensia", "memory", "--db",
                                str(self.path), *args], cwd=root, capture_output=True,
                               text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)
        run("set", "idioma", "Português")
        self.assertEqual(run("get", "idioma")["value"], "Português")
        run("set", "idioma", "English")
        self.assertEqual(run("get", "idioma")["value"], "English")
        self.assertEqual(len(run("list")), 1)
        run("delete", "idioma", "--approve")
        self.assertIsNone(run("get", "idioma"))

    def test_sql_is_data_and_listing_omits_values(self):
        key = "'; DROP TABLE memories; --"
        self.store.set(key, "segredo")
        self.assertEqual(self.store.get(key)["value"], "segredo")
        self.assertNotIn("segredo", json.dumps(self.store.list()))

    def test_delete_requires_approval_and_keeps_other_rows(self):
        self.store.set("a", "one")
        self.store.set("b", "two")
        with self.assertRaises(MemoryError):
            self.store.delete("a")
        self.assertIsNotNone(self.store.get("a"))
        self.assertTrue(self.store.delete("a", True)["deleted"])
        self.assertIsNotNone(self.store.get("b"))

    def test_invalid_inputs_do_not_create_database(self):
        for key, value in [("", "a"), ("a"*101, "x"), ("a", ""), ("a", "x"*4001)]:
            with self.assertRaises(MemoryError):
                self.store.set(key, value)
        self.assertFalse(self.path.exists())

    def test_corrupt_database_has_clear_error(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b"not a sqlite database")
        with self.assertRaises(MemoryError):
            self.store.list()

    def test_pagination(self):
        for k in ("a", "b", "c"):
            self.store.set(k, k)
        self.assertEqual(self.store.list(1, 1)[0]["key"], "b")
        with self.assertRaises(MemoryError):
            self.store.list(0)

    def test_chat_does_not_create_memory(self):
        with patch("gensia.cli.MemoryStore") as memory, redirect_stderr(StringIO()):
            self.assertEqual(main(["ask", "ola"]), 3)
            memory.assert_not_called()
