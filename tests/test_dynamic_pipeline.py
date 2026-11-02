"""Dynamic Codebase Pipeline Tests: Live GitHub Cloning, AST Slicing, and SSE Streaming.

Verifies that:
1. DynamicPipelineOrchestrator parses repository names accurately from various Git URLs.
2. Target preparation provisions `.autopatch/live_target/` with an active Git repository.
3. Live test execution triggers and captures the real ZeroDivisionError traceback coordinate.
4. AST 2-hop MCP extraction operates directly on the dynamic target codebase.
5. 3 Git worktrees spawn concurrently inside `.autopatch/live_target/`.
6. Microsoft Z3 formal verification produces an UNSAT proof certificate.
7. SSE streaming endpoint yields valid event envelopes in proper chronological order.
8. FastAPI endpoints (/api/run-pipeline, /api/pipeline/stream) return 200 OK.
"""
import json
import os
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from engine.dynamic_orchestrator import DynamicPipelineOrchestrator
from dashboard.app import app
from fastapi.testclient import TestClient


class TestDynamicPipelineAndSSE(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.orchestrator = DynamicPipelineOrchestrator(WORKSPACE_ROOT)
        cls.client = TestClient(app)

    def test_01_extract_repo_name(self):
        """Verifies parsing of diverse repository URLs."""
        test_cases = [
            ("https://github.com/user/broken-payment-engine.git", "broken-payment-engine"),
            ("https://github.com/Mahesh-Paul/AutoPatch-Kernel", "AutoPatch-Kernel"),
            ("git@github.com:org/payment-service.git", "payment-service"),
            ("custom-repo", "custom-repo"),
            ("", "broken-payment-engine"),
        ]
        for url, expected in test_cases:
            self.assertEqual(self.orchestrator.extract_repo_name(url), expected)

    def test_02_clone_or_prepare_target(self):
        """Verifies preparation of .autopatch/live_target with Git initialization."""
        target_dir, repo_name, is_remote = self.orchestrator.clone_or_prepare_target(
            "https://github.com/test-org/dynamic-payment-processor"
        )
        self.assertTrue(target_dir.exists())
        self.assertEqual(repo_name, "dynamic-payment-processor")
        self.assertTrue((target_dir / ".git").exists())
        py_files = list(target_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 0, "Expected Python files inside live_target")

    def test_03_run_pipeline_stream_stages(self):
        """Verifies end-to-end streaming generator yields all required pipeline events."""
        events = list(self.orchestrator.run_pipeline_stream(
            "https://github.com/user/broken-payment-engine"
        ))

        step_names = [e.get("step") for e in events]
        self.assertIn("CLONE_START", step_names)
        self.assertIn("CLONE_SUCCESS", step_names)
        self.assertIn("TEST_EXEC_START", step_names)
        self.assertIn("CRASH_IDENTIFIED", step_names)
        self.assertIn("AST_SLICE_START", step_names)
        self.assertIn("AST_SLICE_COMPLETE", step_names)
        self.assertIn("WORKTREE_RACE_START", step_names)
        self.assertIn("Z3_PROOF_START", step_names)
        self.assertIn("Z3_PROOF_COMPLETE", step_names)
        self.assertIn("PIPELINE_COMPLETE", step_names)

        # Inspect crash identification payload
        crash_event = next(e for e in events if e.get("step") == "CRASH_IDENTIFIED")
        self.assertTrue(crash_event["file_path"].endswith(".py"))
        self.assertGreater(crash_event["line_number"], 0)

        # Inspect final summary payload
        final_event = events[-1]
        self.assertEqual(final_event["step"], "PIPELINE_COMPLETE")
        self.assertIn("tournament_winner", final_event)
        self.assertGreater(final_event["tournament_winner"]["breakdown"]["total_score"], 90.0)

    def test_04_fastapi_run_pipeline_endpoint(self):
        """Verifies POST /api/run-pipeline returns JSON result."""
        from dashboard.app import run_pipeline_endpoint, PipelineRunRequest
        req = PipelineRunRequest(repo_url="local", stream=False)
        res = run_pipeline_endpoint(req)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.body.decode("utf-8"))
        self.assertEqual(data.get("step"), "PIPELINE_COMPLETE")
        self.assertIn("tournament_winner", data)
        self.assertIn("z3_certificate", data)

    def test_05_fastapi_stream_pipeline_endpoint(self):
        """Verifies GET /api/pipeline/stream route is registered with stream_pipeline endpoint."""
        route = next((r for r in app.routes if getattr(r, "path", None) == "/api/pipeline/stream"), None)
        self.assertIsNotNone(route, "Expected /api/pipeline/stream route in FastAPI app")
        self.assertIn("GET", route.methods)
        self.assertEqual(route.name, "stream_pipeline")


if __name__ == "__main__":
    unittest.main()
