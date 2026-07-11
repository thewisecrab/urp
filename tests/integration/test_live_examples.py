import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LiveExamplesIntegrationTests(unittest.TestCase):
    def test_white_paper_and_use_case_docs_are_linked_to_live_examples(self):
        root = Path(__file__).resolve().parents[2]
        white_paper = (root / "docs/WHITE_PAPER.md").read_text(encoding="utf-8")
        use_cases = (root / "examples/USE_CASES.md").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        start_here = (root / "docs/00_START_HERE.md").read_text(encoding="utf-8")
        for text in (white_paper, use_cases, readme, start_here):
            self.assertIn("examples/live/run_live_examples.py", text)
        self.assertIn("object_gateway_exact.rehydrated_exact", white_paper)
        self.assertIn("ai_gateway_exact_cache.second_cache", white_paper)
        self.assertIn("lakehouse_mock_adapter.external_integrations_required", white_paper)
        self.assertIn("Exact Object Storage Reduction", use_cases)
        self.assertIn("AI Gateway Exact Cache", use_cases)
        self.assertIn("Lakehouse Adapter Contract", use_cases)

    def test_live_examples_runner_outputs_runtime_evidence(self):
        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root / "python")
        with tempfile.TemporaryDirectory() as td:
            output = subprocess.check_output(
                [
                    sys.executable,
                    str(root / "examples/live/run_live_examples.py"),
                    "--state-dir",
                    td,
                    "--reset",
                ],
                cwd=root,
                env=env,
                text=True,
            )
        report = json.loads(output)
        self.assertFalse(report["summary"]["external_services_required"])
        self.assertTrue(report["summary"]["ledger_chain_valid"])
        self.assertEqual(report["summary"]["manifests"], 4)
        self.assertGreaterEqual(report["summary"]["ledger_events"], 20)
        self.assertTrue(report["object_gateway_exact"]["rehydrated_exact"])
        self.assertEqual(report["object_gateway_exact"]["delete_guardrail"]["reason"], "legal_hold")
        self.assertEqual(report["ai_gateway_exact_cache"]["first_cache"], "miss")
        self.assertEqual(report["ai_gateway_exact_cache"]["second_cache"], "exact_hit")
        self.assertTrue(report["ai_gateway_exact_cache"]["provider_avoided_on_second_call"])
        self.assertFalse(report["ai_gateway_exact_cache"]["raw_prompt_logged"])
        self.assertEqual(report["lakehouse_mock_adapter"]["contract"], "exact_logical")
        self.assertFalse(report["lakehouse_mock_adapter"]["external_integrations_required"])
        self.assertTrue(report["lakehouse_mock_adapter"]["rehydrated_contains_snapshot_id"])
        self.assertEqual(
            report["reports_and_audit"]["dashboard_sections"],
            ["executive", "platform", "ai", "data", "security"],
        )


if __name__ == "__main__":
    unittest.main()
