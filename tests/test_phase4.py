"""Phase 4 Verification Tests: Deterministic Patch Tournament & Flight Recorder PR Generator.

Validates that:
1. Tournament Kernel deterministically scores candidate worktrees across 5 weighted pillars.
2. Disqualifies Worktree B (LUCKY_PASS_BLOCKED) with 0 points.
3. Penalizes Worktree C (latency and unverified invariants).
4. Crowns Worktree A as the winner with highest composite score.
5. PR Generator synthesizes and writes `artifacts/FLIGHT_RECORDER_PR.md` containing
   Mermaid causal graphs, Meta model telemetry, and the cryptographic Z3 Certificate.
"""
import os
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from engine.tournament_kernel import PatchTournamentKernel
from engine.worktree_manager import WorktreeManager
from github_integration.pr_generator import PRGenerator
from mcp_server.ast_graph_mcp import ASTCallGraphEngine, SyscallTelemetryEngine
from verification.z3_verifier import Z3TheoremProver


class TestPhase4TournamentAndPRGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = WORKSPACE_ROOT
        cls.ast_engine = ASTCallGraphEngine(str(cls.workspace))
        cls.worktree_manager = WorktreeManager(str(cls.workspace))
        cls.pr_generator = PRGenerator(str(cls.workspace))

    def test_01_tournament_kernel_scoring_and_winner_selection(self):
        """Verifies PatchTournamentKernel evaluates 3 worktrees, disqualifying B and crowning A."""
        processor_file = str(self.workspace / "target_app" / "processor.py")
        subgraph = self.ast_engine.extract_subgraph(processor_file, line_number=26)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        # Run 3-way worktree race
        race_res = self.worktree_manager.race_competing_hypotheses(subgraph, telemetry)
        z3_res = Z3TheoremProver.verify_patched_discount_logic()

        # Evaluate tournament
        tournament_res = PatchTournamentKernel.evaluate_tournament(race_res, z3_res)

        self.assertEqual(tournament_res.total_candidates_evaluated, 3)

        # Worktree A must be winner
        self.assertTrue(tournament_res.winner.is_winner)
        self.assertEqual(tournament_res.winner.worktree_name, "worktree_a_refactor")
        self.assertGreaterEqual(tournament_res.winner.breakdown.total_score, 85.0)
        self.assertEqual(tournament_res.winner.breakdown.z3_score, 35.0)

        # Worktree B must be disqualified
        card_b = next(c for c in tournament_res.scorecards if c.worktree_name == "worktree_b_adapter")
        self.assertTrue(card_b.breakdown.disqualified)
        self.assertEqual(card_b.breakdown.total_score, 0.0)
        self.assertIn("LUCKY_PASS_BLOCKED", card_b.breakdown.disqualification_reason)

        # Worktree C must have lower score than winner
        card_c = next(c for c in tournament_res.scorecards if c.worktree_name == "worktree_c_guard")
        self.assertLess(card_c.breakdown.total_score, tournament_res.winner.breakdown.total_score)

    def test_02_pr_generator_produces_flight_recorder_artifact(self):
        """Verifies PRGenerator writes artifacts/FLIGHT_RECORDER_PR.md with all required sections."""
        processor_file = str(self.workspace / "target_app" / "processor.py")
        subgraph = self.ast_engine.extract_subgraph(processor_file, line_number=26)
        cmd = f'"{sys.executable}" -m unittest target_app/tests/test_processor.py'
        telemetry = SyscallTelemetryEngine.capture(command=cmd, cwd=str(self.workspace))

        race_res = self.worktree_manager.race_competing_hypotheses(subgraph, telemetry)
        z3_res = Z3TheoremProver.verify_patched_discount_logic()
        tournament_res = PatchTournamentKernel.evaluate_tournament(race_res, z3_res)

        flight_pr = self.pr_generator.write_pr_artifact(tournament_res)

        # Check artifact on disk
        artifact_path = Path(flight_pr.artifact_path)
        self.assertTrue(artifact_path.exists(), "FLIGHT_RECORDER_PR.md must exist on disk")

        content = artifact_path.read_text(encoding="utf-8")
        self.assertIn("AutoPatch-Kernel: Autonomous Self-Healing Flight Recorder PR", content)
        self.assertIn("```mermaid", content)
        self.assertIn("Meta Model Telemetry Matrix", content)
        self.assertIn("Meta Muse Spark 1.3", content)
        self.assertIn("Meta Muse Wonder 1.0", content)
        self.assertIn("Meta Muse Code 1.0", content)
        self.assertIn("3-Way Worktree Tournament Scorecard", content)
        self.assertIn("MICROSOFT Z3 SMT FORMAL VERIFICATION CERTIFICATE", content)
        self.assertIn("UNSAT_PROVEN_SAFE", content)
        self.assertIn("diff --git a/target_app/processor.py", content)
        self.assertIn("diff --git a/target_app/validators.py", content)


if __name__ == "__main__":
    unittest.main()
