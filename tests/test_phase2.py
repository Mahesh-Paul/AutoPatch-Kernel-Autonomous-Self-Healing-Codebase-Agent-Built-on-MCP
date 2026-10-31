"""Phase 2 Verification Tests: Read-Only Sandbox Guardrail & Z3 SMT Formal Proofs.

Validates that:
1. Z3 Theorem Prover detects the unpatched division-by-zero bug as SAT (counterexample at promo=4).
2. Z3 Theorem Prover proves patched logic is UNSAT (mathematically safe across infinite domain).
3. Read-Only Sandbox Guardrail catches test-tampering 'Lucky Pass' attempts and blocks them.
4. Differential Shadow Traffic Replay executes 50 synthetic workloads measuring latency and exception delta.
"""
import copy
import os
import shutil
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from verification.z3_verifier import Z3TheoremProver
from sandbox.sandbox_runner import SandboxRunner, ShadowTrafficReplayEngine
from target_app.processor import process_payment_order


class TestPhase2SandboxAndFormalVerification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workspace = WORKSPACE_ROOT
        cls.sandbox_runner = SandboxRunner(str(cls.workspace))

    def test_01_z3_detects_bug_in_unpatched_logic(self):
        """Verifies Z3 produces a SAT counterexample for unpatched calculate_discount."""
        res = Z3TheoremProver.verify_unpatched_discount_logic()

        self.assertFalse(res.is_verified)
        self.assertEqual(res.verdict, "SAT_COUNTEREXAMPLE_FOUND")
        self.assertIsNotNone(res.counterexample)
        self.assertEqual(res.counterexample["active_promos_count"], 4)
        self.assertEqual(res.counterexample["evaluated_denominator"], 0)
        self.assertIn("BUG VERIFIED", res.proof_summary)

    def test_02_z3_proves_patched_logic_unsat_safe(self):
        """Verifies Z3 outputs UNSAT, formally proving mathematical safety across all inputs."""
        res = Z3TheoremProver.verify_patched_discount_logic()

        self.assertTrue(res.is_verified)
        self.assertEqual(res.verdict, "UNSAT_PROVEN_SAFE")
        self.assertIsNone(res.counterexample)
        self.assertTrue(res.certificate.is_safe)
        self.assertEqual(len(res.certificate.sha256_digest), 64)
        self.assertIn("FORMALLY VERIFIED (UNSAT)", res.proof_summary)

    def test_03_sandbox_guardrail_clean_execution(self):
        """Verifies clean test execution does NOT trigger lucky pass block."""
        res = self.sandbox_runner.execute_with_guardrail(
            worktree_path=self.workspace,
            test_command=f'"{sys.executable}" -m unittest target_app/tests/test_processor.py',
            branch_name="baseline_branch",
        )
        self.assertFalse(res.lucky_pass_blocked)
        self.assertEqual(len(res.tampered_test_files), 0)

    def test_04_guardrail_catches_and_blocks_lucky_pass_tampering(self):
        """Verifies that if an agent tampers with a test file, the Read-Only Guardrail

        immediately flags lucky_pass_blocked = True and emits SECURITY_VIOLATION.
        """
        temp_test_dir = self.workspace / ".autopatch" / "test_sandbox_tmp"
        if temp_test_dir.exists():
            shutil.rmtree(temp_test_dir, ignore_errors=True)

        # Copy target_app to temporary sandbox dir
        shutil.copytree(self.workspace / "target_app", temp_test_dir / "target_app")

        try:
            # Simulate a rogue agent modifying test_processor.py to cheat CI
            tampered_file = temp_test_dir / "target_app" / "tests" / "test_processor.py"
            original_code = tampered_file.read_text(encoding="utf-8")
            tampered_code = original_code + "\n# Lucky Pass Cheat\n"
            tampered_file.write_text(tampered_code, encoding="utf-8")

            # Run with guardrail pointing to golden workspace root
            runner = SandboxRunner(str(self.workspace))
            res = runner.execute_with_guardrail(
                worktree_path=temp_test_dir,
                branch_name="worktree_b_cheat",
                reference_tests_dir=self.workspace / "target_app" / "tests",
            )

            self.assertTrue(res.lucky_pass_blocked, "Must detect and block test tampering")
            self.assertEqual(res.exit_code, 126)
            self.assertIn("SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT", res.violation_details)
            self.assertTrue(any("test_processor.py" in f for f in res.tampered_test_files))
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_test_dir, ignore_errors=True)

    def test_05_differential_shadow_traffic_replay_50_payloads(self):
        """Verifies differential shadow traffic replay across 50 high-entropy workloads."""

        # Define baseline function (unpatched: crashes on active_promos=4 and v2 schema)
        def baseline_fn(order_payload):
            return process_payment_order(copy.deepcopy(order_payload))

        # Define candidate function (patched: handles promos=4 and v2 schema cleanly)
        def patched_fn(order_payload):
            payload = copy.deepcopy(order_payload)
            # Apply safe tier extraction
            cust = payload["customer"]
            if "tier_profile" in cust and isinstance(cust["tier_profile"], dict):
                raw_tier = cust["tier_profile"].get("tier_level", "STANDARD")
            else:
                raw_tier = cust.get("tier", "STANDARD")
            cust["tier"] = raw_tier

            # Apply safe promo clamp
            promos = payload.get("active_promos_count", 0)
            if promos >= 4:
                payload["active_promos_count"] = 3  # safe clamp

            return process_payment_order(payload)

        metrics = ShadowTrafficReplayEngine.run_differential_replay(
            baseline_fn=baseline_fn,
            candidate_fn=patched_fn,
        )

        self.assertEqual(metrics.total_payloads, 50)
        self.assertGreater(metrics.baseline_exception_count, 0, "Baseline must trigger exceptions")
        self.assertEqual(metrics.candidate_exception_count, 0, "Patched code must survive all 50 payloads")
        self.assertLess(metrics.exception_rate_delta, 0.0, "Exception delta must be negative (error reduction)")
        self.assertFalse(metrics.regression_detected, "No regressions should be detected in patched code")


if __name__ == "__main__":
    unittest.main()
