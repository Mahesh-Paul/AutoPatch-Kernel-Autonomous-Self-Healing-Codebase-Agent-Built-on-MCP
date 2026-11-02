"""Read-Only Sandbox Runner, Guardrail Engine & Differential Shadow Replay.

Provides isolated test execution with cryptographic Read-Only Guardrails that
detect and reject test-tampering 'Lucky Pass' cheats, plus a 50-payload differential
shadow traffic replay engine measuring latency and exception delta.
"""
from __future__ import annotations

import hashlib
import importlib
import math
import os
import random
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ==============================================================================
# Pydantic Schemas for Sandbox & Guardrail Results
# ==============================================================================

class ShadowTrafficMetrics(BaseModel):
    total_payloads: int = 50
    baseline_exception_count: int
    candidate_exception_count: int
    exception_rate_delta: float  # (candidate_errs - baseline_errs) / total
    baseline_avg_latency_ms: float
    candidate_avg_latency_ms: float
    latency_overhead_percent: float
    baseline_p99_latency_ms: float
    candidate_p99_latency_ms: float
    p99_latency_delta_ms: float
    regression_detected: bool


class SandboxRunResult(BaseModel):
    branch_or_worktree: str
    tests_passed: bool
    lucky_pass_blocked: bool
    violation_details: Optional[str] = None
    exit_code: int
    duration_ms: float
    stdout: str
    stderr: str
    shadow_replay_metrics: Optional[ShadowTrafficMetrics] = None
    tampered_test_files: List[str] = Field(default_factory=list)


# ==============================================================================
# Read-Only Test Guardrail & Sandbox Runner
# ==============================================================================

class SandboxRunner:
    """Executes tests and benchmarks under strict security guardrails."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()

    def _compute_directory_hashes(self, target_dir: Path) -> Dict[str, str]:
        """Calculates SHA-256 hashes for all files in the given directory."""
        hashes: Dict[str, str] = {}
        if not target_dir.exists():
            return hashes

        for p in target_dir.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                try:
                    content = p.read_bytes().replace(b"\r\n", b"\n")
                    rel = str(p.relative_to(target_dir))
                    hashes[rel] = hashlib.sha256(content).hexdigest()
                except Exception:
                    pass
        return hashes

    def _apply_permissions(self, target_dir: Path, make_readonly: bool):
        """Sets file permissions to read-only or read-write recursively."""
        if not target_dir.exists():
            return

        for p in target_dir.rglob("*"):
            if p.is_file():
                try:
                    if make_readonly:
                        # Read-only permission
                        os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
                    else:
                        # Restore write permissions
                        os.chmod(p, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP)
                except Exception:
                    pass

    def execute_with_guardrail(
        self,
        worktree_path: str | Path,
        test_command: Optional[str] = None,
        branch_name: str = "candidate_branch",
        reference_tests_dir: Optional[str | Path] = None,
    ) -> SandboxRunResult:
        """Executes candidate test suite while strictly enforcing Read-Only Test Guardrails.

        If any candidate patch attempts to modify, weaken, or delete existing test files,
        the run is immediately halted and marked as `LUCKY_PASS_BLOCKED`.
        """
        wt_dir = Path(worktree_path).resolve()

        # Determine candidate tests dir dynamically
        candidate_tests_dir = None
        for candidate_rel in ["target_app/tests", "tests", "test"]:
            p = wt_dir / candidate_rel
            if p.exists() and p.is_dir():
                candidate_tests_dir = p
                break
        if candidate_tests_dir is None:
            for p in wt_dir.rglob("test_*.py"):
                if ".autopatch" not in p.parts:
                    candidate_tests_dir = p.parent
                    break
        if candidate_tests_dir is None:
            candidate_tests_dir = wt_dir / "target_app" / "tests"

        # Determine reference golden test directory (from main workspace root if not provided)
        if reference_tests_dir:
            ref_dir = Path(reference_tests_dir).resolve()
        elif (self.workspace_root / "target_app" / "tests").exists():
            ref_dir = self.workspace_root / "target_app" / "tests"
        else:
            ref_dir = candidate_tests_dir

        # 1. Capture Golden Baseline Hashes of Unmodified Test Suite
        golden_hashes = self._compute_directory_hashes(ref_dir)

        # 2. Lock Test Files as Read-Only in Candidate Worktree
        self._apply_permissions(candidate_tests_dir, make_readonly=True)

        start_time = time.perf_counter()
        lucky_pass_blocked = False
        violation_details = None
        tampered_files: List[str] = []
        stdout = ""
        stderr = ""
        exit_code = 0

        if test_command:
            cmd = test_command
        elif (wt_dir / "target_app" / "tests").exists():
            cmd = f'"{sys.executable}" -m unittest discover -s target_app/tests'
        elif (wt_dir / "tests").exists():
            cmd = f'"{sys.executable}" -m pytest tests'
        else:
            cmd = f'"{sys.executable}" -m unittest discover'

        try:
            # 3. Check for Branch-Level Test Tampering against Golden Reference
            current_hashes = self._compute_directory_hashes(candidate_tests_dir)
            tampered_files = self._detect_tampering(golden_hashes, current_hashes)

            if tampered_files:
                lucky_pass_blocked = True
                violation_details = (
                    f"SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT: Candidate modified test files: {tampered_files}"
                )
                exit_code = 126  # Command invoked cannot execute / permission error
                stderr = violation_details
            else:
                # 4. Execute Test Suite in Subprocess
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{wt_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

                proc = subprocess.run(
                    cmd,
                    cwd=str(wt_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    timeout=30.0,
                    env=env,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode

                # 5. Post-Execution Tampering Check
                post_hashes = self._compute_directory_hashes(candidate_tests_dir)
                post_tampered = self._detect_tampering(golden_hashes, post_hashes)
                if post_tampered:
                    lucky_pass_blocked = True
                    tampered_files.extend(post_tampered)
                    violation_details = (
                        f"SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT: Test files tampered during execution: {tampered_files}"
                    )
                    exit_code = 126

        finally:
            # ALWAYS restore write permissions so OS cleanup never fails on Windows/Linux
            self._apply_permissions(candidate_tests_dir, make_readonly=False)

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        tests_passed = (exit_code == 0) and not lucky_pass_blocked

        return SandboxRunResult(
            branch_or_worktree=branch_name,
            tests_passed=tests_passed,
            lucky_pass_blocked=lucky_pass_blocked,
            violation_details=violation_details,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            tampered_test_files=tampered_files,
        )

    def _detect_tampering(
        self, baseline: Dict[str, str], current: Dict[str, str]
    ) -> List[str]:
        tampered: List[str] = []
        # Missing files
        for rel_path in baseline:
            if rel_path not in current:
                tampered.append(f"{rel_path} (DELETED)")
            elif baseline[rel_path] != current[rel_path]:
                tampered.append(f"{rel_path} (MODIFIED)")

        # Added new unexpected test files
        for rel_path in current:
            if rel_path not in baseline:
                tampered.append(f"{rel_path} (ADDED)")

        return tampered


# ==============================================================================
# Differential Shadow Traffic Replay Engine
# ==============================================================================

class ShadowTrafficReplayEngine:
    """Generates 50 synthetic high-entropy edge-case payloads and executes them

    differentially between baseline and candidate codebases to detect regressions,
    memory anomalies, and latency shifts.
    """

    @classmethod
    def generate_synthetic_payloads(cls, count: int = 50) -> List[Dict[str, Any]]:
        """Synthesizes high-entropy payment orders covering all boundary and schema conditions."""
        rng = random.Random(42)  # Deterministic seed for reproducible evaluation
        payloads: List[Dict[str, Any]] = []

        tiers = ["STANDARD", "SILVER", "GOLD", "PLATINUM"]
        jurisdictions = ["US-CA", "US-NY", "US-TX", "EU-DE", "GLOBAL-DEFAULT"]

        for i in range(count):
            order_id = f"SHADOW-ORD-{i + 1:04d}"
            tier = rng.choice(tiers)
            jurisdiction = rng.choice(jurisdictions)

            # Alternate between legacy and modern nested schema
            use_v2_schema = (i % 2 == 0)
            if use_v2_schema:
                customer = {
                    "customer_id": f"CUST-V2-{i:03d}",
                    "tier_profile": {
                        "tier_level": tier,
                        "loyalty_score": rng.randint(100, 1000),
                    },
                }
            else:
                customer = {
                    "customer_id": f"CUST-V1-{i:03d}",
                    "tier": tier,
                }

            # Boundary active promo counts: includes 0, 1, 2, 3, 4 (boundary crash), and >4
            if i % 5 == 0:
                active_promos = 4  # Crash condition in unpatched code!
            elif i % 7 == 0:
                active_promos = 6  # Overflow condition
            else:
                active_promos = rng.randint(0, 3)

            # Item generation
            num_items = rng.randint(1, 5)
            items = []
            for j in range(num_items):
                items.append({
                    "sku": f"SKU-{j:02d}",
                    "price": round(rng.uniform(5.0, 350.0), 2),
                    "quantity": rng.randint(1, 4),
                })

            payloads.append({
                "order_id": order_id,
                "customer": customer,
                "items": items,
                "active_promos_count": active_promos,
                "jurisdiction": jurisdiction,
            })

        return payloads

    @classmethod
    def run_differential_replay(
        cls,
        baseline_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        candidate_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> ShadowTrafficMetrics:
        """Executes side-by-side replay, measuring exception rates and p99 latency deltas."""
        workload = payloads or cls.generate_synthetic_payloads(count=50)

        baseline_latencies: List[float] = []
        candidate_latencies: List[float] = []
        baseline_exceptions = 0
        candidate_exceptions = 0

        for payload in workload:
            # Baseline execution
            t0 = time.perf_counter()
            try:
                baseline_fn(payload)
            except Exception:
                baseline_exceptions += 1
            t1 = time.perf_counter()
            baseline_latencies.append((t1 - t0) * 1000.0)

            # Candidate execution
            t2 = time.perf_counter()
            try:
                candidate_fn(payload)
            except Exception:
                candidate_exceptions += 1
            t3 = time.perf_counter()
            candidate_latencies.append((t3 - t2) * 1000.0)

        total = len(workload)
        base_avg = sum(baseline_latencies) / total
        cand_avg = sum(candidate_latencies) / total

        # Compute P99 latency
        baseline_latencies.sort()
        candidate_latencies.sort()
        p99_idx = int(math.ceil(0.99 * total)) - 1
        base_p99 = baseline_latencies[p99_idx]
        cand_p99 = candidate_latencies[p99_idx]

        p99_delta = round(cand_p99 - base_p99, 4)
        latency_overhead_pct = round(((cand_avg - base_avg) / (base_avg or 0.0001)) * 100.0, 2)
        exception_delta = round((candidate_exceptions - baseline_exceptions) / total, 4)

        # Regression is detected if candidate has MORE exceptions or massive latency spike
        regression = (candidate_exceptions > baseline_exceptions) or (latency_overhead_pct > 250.0)

        return ShadowTrafficMetrics(
            total_payloads=total,
            baseline_exception_count=baseline_exceptions,
            candidate_exception_count=candidate_exceptions,
            exception_rate_delta=exception_delta,
            baseline_avg_latency_ms=round(base_avg, 4),
            candidate_avg_latency_ms=round(cand_avg, 4),
            latency_overhead_percent=latency_overhead_pct,
            baseline_p99_latency_ms=round(base_p99, 4),
            candidate_p99_latency_ms=round(cand_p99, 4),
            p99_latency_delta_ms=p99_delta,
            regression_detected=regression,
        )
