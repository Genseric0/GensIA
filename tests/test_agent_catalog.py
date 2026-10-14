import json
from pathlib import Path
import subprocess
import sys
import unittest

from gensia.agent_catalog import catalog_snapshot, descriptions


class AgentCatalogTests(unittest.TestCase):
    def test_stable_ids_and_cli_contract(self):
        from gensia.agents import CATALOG
        self.assertEqual(CATALOG, descriptions())
        self.assertEqual(list(CATALOG), ["coordinator", "security", "reviewer", "study"])
        self.assertTrue(all(isinstance(v, str) for v in CATALOG.values()))

    def test_snapshot_is_detached(self):
        snapshot = catalog_snapshot()
        snapshot["agents"][0]["description"] = "changed"
        snapshot["agents"][1]["capabilities"][0]["id"] = "changed"
        self.assertNotIn("changed", json.dumps(catalog_snapshot()))

    def test_model_dependencies_are_not_runtime_claims(self):
        snapshot = catalog_snapshot()
        agents = {a["id"]: a for a in snapshot["agents"]}
        self.assertEqual(agents["reviewer"]["capabilities"][0]["model_use"], "optional")
        self.assertEqual(agents["study"]["capabilities"][0]["model_use"], "required")
        self.assertEqual(snapshot["runtime_state"], "not_observed")
        self.assertFalse(snapshot["dependencies_checked"])
        self.assertFalse(snapshot["execution_exposed"])

    def test_api_import_does_not_load_tools_or_external_frameworks(self):
        # A fresh interpreter avoids false positives from other test imports.
        code = (
            "import sys,json; import gensia.api; "
            "blocked=['gensia.agents','gensia.providers','gensia.tools','gensia.doctor',"
            "'gensia.documents','gensia.memory','gensia.security','gensia.static_analysis',"
            "'fastapi','bandit','ollama']; "
            "print(json.dumps([m for m in blocked if m in sys.modules]))"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), [])
