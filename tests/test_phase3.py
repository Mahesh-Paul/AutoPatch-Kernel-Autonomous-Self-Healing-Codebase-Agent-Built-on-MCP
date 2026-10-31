"""Phase 3 Verification Tests: Parallel Git Worktrees, Critic Agent & Trajectory Memory.

Validates that:
1. Muse Wonder Critic evaluates candidates, catching syntax errors and flagging test probes.
2. Trajectory Memory Store records execution history and persists to .autopatch/memory.json.
3. Reproducer Subagent synthesizes standalone reproducers confirming Red-to-Green transition.
4. Parallel Worktree Manager spawns 3 concurrent candidate branches, executes tests,
   traps Worktree B via the Read-Only Guardrail, and crowns Worktree A.
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from engine.critic_agent import MuseWonderCritic
from engine.memory_store import TrajectoryMemoryStore
from engine.meta_model_router import FilePatch, MetaModelRouter, ModelPatchCandidate
from engine.reproducer_agent import ReproducerAgent
from engine.worktree_manager import WorktreeManager
from mcp_server.ast_graph_mcp import ASTCallGraphEngine, SyscallTelemetryEngine


class TestPhase3WorktreeAndAgentHarness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = WORKSPACE_ROOT
        cls.ast_engine = ASTCallGraphEngine(str(cls.workspace))
        cls.worktree_manager = WorktreeManager(str(cls.workspace))
        cls.memory_store = TrajectoryMemoryStore()
        cls.reproducer = ReproducerAgent(str(cls.workspace))

    def test_01_critic_evaluates_syntax_and_catches_invalid_code(self):
        """Verifies Muse Wonder Critic evaluates candidates and rejects syntax errors."""
        # Clean candidate
        clean_patch = FilePatch(
            relative_path="target_app/processor.py",
            original_snippet="pass",
            patched_snippet="    x = 10 + 20\n    return x",
            patch_rationale="Clean valid code",
            mutation_type="REFACTOR",
        )
        cand_clean = ModelPatchCandidate(
            strategy_id="test_clean",
            hypothesis_name="Test Clean",
            target_worktree="test_wt_1",
            model_used="muse-spark",
            temperature=0.1,
            patches=[clean_patch],
            confidence_score=0.9,
            description="Clean valid code candidate",
        )
        res_clean = MuseWonderCritic.evaluate_candidate(cand_clean)
        self.assertTrue(res_clean.is_approved)
        self.assertTrue(res_clean.syntax_valid)

        # Syntax error candidate
        broken_patch = FilePatch(
            relative_path="target_app/processor.py",
            original_snippet="pass",
            patched_snippet="    def broken( { return",  # Syntax error
            patch_rationale="Broken code",
            mutation_type="REFACTOR",
        )
        cand_broken = ModelPatchCandidate(
            strategy_id="test_broken",
            hypothesis_name="Test Broken",
            target_worktree="test_wt_2",
            model_used="muse-spark",
            temperature=0.1,
            patches=[broken_patch],
            confidence_score=0.2,
            description="Broken syntax candidate",
        )
        res_broken = MuseWonderCritic.evaluate_candidate(cand_broken)
        self.assertFalse(res_broken.is_approved)
        self.assertFalse(res_broken.syntax_valid)
        self.assertTrue(any("SYNTAX_ERROR" in f for f in res_broken.flags))

    def test_02_trajectory_memory_store_persistence(self):
        """Verifies TrajectoryMemoryStore writes and reads records from .autopatch/memory.json."""
        test_memory_path = self.workspace / ".autopatch" / "test_memory.json"
        if test_memory_path.exists():
            test_memory_path.unlink()

        store = TrajectoryMemoryStore(memory_path=test_memory_path)
        record = store.record_trajectory(
            strategy_id="strategy_test_mock",
            hypothesis_name="Mock Hypothesis",
            worktree_name="worktree_test",
            verdict="LUCKY_PASS_BLOCKED",
            files_modified=["target_app/tests/test_processor.py"],
            error_summary="Detected test modification",
        )

        self.assertTrue(test_memory_path.exists())
        self.assertTrue(store.is_known_dead_end("strategy_test_mock"))

        # Re-load from disk
        store2 = TrajectoryMemoryStore(memory_path=test_memory_path)
        self.assertEqual(len(store2.records), 1)
        self.assertEqual(store2.records[0].strategy_id, "strategy_test_mock")
        self.assertEqual(store2.records[0].verdict, "LUCKY_PASS_BLOCKED")

        if test_memory_path.exists():
            test_memory_path.unlink()

    def test_03_reproducer_agent_synthesizes_script(self):
        """Verifies ReproducerAgent generates standalone reproduction test script."""
        script_path = self.reproducer.generate_reproduction_script()
        self.assertTrue(script_path.exists())
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("REPRODUCER", content)
        self.assertIn("Boundary Promo ZeroDivision", content)
        self.assertIn("Modern API v2 Tier Profile", content)

    def test_04_parallel_worktree_race_execution(self):
        """Verifies full parallel execution of 3 Git worktrees:

        - Spawns worktree_a_refactor, worktree_b_adapter, worktree_c_guard concurrently.
        - Traps Worktree B via Read-Only Guardrail (LUCKY_PASS_BLOCKED).
        - Executes tests and populates trajectory records.
        """
        processor_file = str(self.workspace / "target_app" / "processor.py")
        subgraph = self.ast_engine.extract_subgraph(processor_file, line_number=26)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        race_result = self.worktree_manager.race_competing_hypotheses(subgraph, telemetry)

        self.assertEqual(race_result.total_candidates, 3)
        self.assertEqual(len(race_result.outcomes), 3)

        # Verify Worktree B was trapped by Read-Only Sandbox Guardrail
        outcome_b = next(o for o in race_result.outcomes if o.worktree_name == "worktree_b_adapter")
        self.assertTrue(outcome_b.is_disqualified)
        self.assertTrue(
            outcome_b.sandbox_result.lucky_pass_blocked,
            f"Worktree B must be blocked by Read-Only Guardrail. Result: {outcome_b}",
        )
        self.assertEqual(outcome_b.trajectory_record.verdict, "LUCKY_PASS_BLOCKED")

        # Verify Worktree A succeeded
        outcome_a = next(o for o in race_result.outcomes if o.worktree_name == "worktree_a_refactor")
        self.assertFalse(outcome_a.is_disqualified)
        self.assertTrue(outcome_a.sandbox_result.tests_passed)
        self.assertEqual(outcome_a.trajectory_record.verdict, "PASSED")

        # Verify Winner was crowned
        self.assertIsNotNone(race_result.winner_outcome)
        self.assertEqual(race_result.winner_outcome.worktree_name, "worktree_a_refactor")


if __name__ == "__main__":
    unittest.main()
