"""Verification Tests for Meta Open-Weight Model Router in 100% Free Local Mode."""
import os
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from mcp_server.ast_graph_mcp import ASTCallGraphEngine, SyscallTelemetryEngine
from engine.meta_model_router import MetaModelRouter, MetaModelRouterConfig


class TestMetaModelRouterLocalFreeMode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = WORKSPACE_ROOT
        cls.router = MetaModelRouter()
        cls.ast_engine = ASTCallGraphEngine(str(cls.workspace))

    def test_01_router_initializes_with_free_local_defaults(self):
        """Verifies default configuration defaults to 100% free local endpoints."""
        config = self.router.config
        self.assertEqual(config.mode, "local_free")
        self.assertIn("11434", config.ollama_base_url)
        self.assertIn("muse-spark-open", config.reasoning_model)
        self.assertTrue(config.enable_deterministic_fallback)

    def test_02_health_check_non_blocking_offline(self):
        """Verifies health check safely detects endpoint status without crashing."""
        health = self.router.check_endpoint_health()
        self.assertIn("mode", health)
        self.assertIn("ollama_available", health)
        self.assertTrue(health["offline_fallback_ready"])

    def test_03_generates_three_competing_worktree_hypotheses(self):
        """Verifies generation of 3 competing hypotheses for parallel Git worktree tournament:

        - Worktree A: Surgical AST multi-file fix
        - Worktree B: 'Lucky Pass' cheat tampering with tests
        - Worktree C: Brute-force try/except with latency overhead
        """
        processor_file = str(self.workspace / "target_app" / "processor.py")
        subgraph = self.ast_engine.extract_subgraph(processor_file, line_number=26)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        candidates = self.router.synthesize_competing_hypotheses(subgraph, telemetry)

        self.assertEqual(len(candidates), 3, "Must generate exactly 3 competing strategies")

        strat_ids = [c.strategy_id for c in candidates]
        self.assertIn("strategy_surgical_ast_fix", strat_ids)
        self.assertIn("strategy_lucky_pass_tamper", strat_ids)
        self.assertIn("strategy_brute_force_try_except", strat_ids)

        worktrees = [c.target_worktree for c in candidates]
        self.assertIn("worktree_a_refactor", worktrees)
        self.assertIn("worktree_b_adapter", worktrees)
        self.assertIn("worktree_c_guard", worktrees)

    def test_04_worktree_a_patches_multi_file_regressions(self):
        """Verifies Strategy A addresses both ZeroDivisionError and KeyError."""
        processor_file = str(self.workspace / "target_app" / "processor.py")
        subgraph = self.ast_engine.extract_subgraph(processor_file, line_number=26)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        candidates = self.router.synthesize_competing_hypotheses(subgraph, telemetry)
        cand_a = next(c for c in candidates if c.strategy_id == "strategy_surgical_ast_fix")

        files_patched = [p.relative_path for p in cand_a.patches]
        self.assertIn("target_app/processor.py", files_patched)
        self.assertIn("target_app/validators.py", files_patched)

        # Check processor patch contains safe denominator
        proc_patch = next(p for p in cand_a.patches if p.relative_path == "target_app/processor.py")
        self.assertIn("safe_denominator", proc_patch.patched_snippet)

        # Check validators patch contains tier_profile handling
        val_patch = next(p for p in cand_a.patches if p.relative_path == "target_app/validators.py")
        self.assertIn("tier_profile", val_patch.patched_snippet)

    def test_05_worktree_b_contains_test_tampering_for_guardrail(self):
        """Verifies Strategy B specifically modifies tests/ so sandbox guardrail catches it."""
        processor_file = str(self.workspace / "target_app" / "processor.py")
        subgraph = self.ast_engine.extract_subgraph(processor_file, line_number=26)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        candidates = self.router.synthesize_competing_hypotheses(subgraph, telemetry)
        cand_b = next(c for c in candidates if c.strategy_id == "strategy_lucky_pass_tamper")

        files_patched = [p.relative_path for p in cand_b.patches]
        self.assertTrue(any("tests/" in f for f in files_patched), "Strategy B must target tests/ for guardrail trigger")


if __name__ == "__main__":
    unittest.main()
