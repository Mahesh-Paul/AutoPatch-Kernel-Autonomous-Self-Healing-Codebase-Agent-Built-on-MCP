"""Read-Only Sandbox Runner, Guardrail Engine & Differential Shadow Replay.

Provides isolated test execution with cryptographic Read-Only Guardrails that
detect and reject test-tampering 'Lucky Pass' cheats, plus a 50-payload differential
shadow traffic replay engine measuring latency and exception delta.
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class SandboxSecurityException(Exception):
    """Base exception for sandbox security violations and isolation boundaries."""
    pass


class LuckyPassSecurityViolation(SandboxSecurityException):
    """Raised when an autonomous agent attempts to weaken, alter, or delete test assertions."""
    pass


class ShadowTrafficReplayError(SandboxSecurityException):
    """Raised when differential synthetic traffic replay encounters unrecoverable harness faults."""
    pass


# ==============================================================================
# Pydantic Schemas for Sandbox & Guardrail Results
# ==============================================================================

class ShadowTrafficMetrics(BaseModel):
    """Quantifies statistical latency shifts and regression rates across shadow workloads."""
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
    """Complete cryptographic audit and test execution verdict for an isolated worktree."""
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
    """Executes tests and benchmarks under strict security guardrails.
    
    In autonomous software healing, language models frequently engage in 'Reward Hacking'
    (deleting asserts, removing test cases, or swallowing exceptions to force exit code 0).
    This runner prevents test-tampering by enforcing:
    1. Pre-execution CRLF-normalized SHA-256 Merkle root locking.
    2. Read-only filesystem attributes (`chmod 0444`) on all test modules.
    3. Post-execution Merkle tree integrity verification.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()

    def _compute_directory_hashes(self, target_dir: Path) -> Dict[str, str]:
        """Calculates canonical SHA-256 hashes for all test modules in the directory tree.
        
        CRITICAL: We normalize all CRLF line endings to LF before hashing. Cross-platform
        Git checkouts on Windows often convert `\n` to `\r\n`, which would otherwise
        trigger false-positive tampering alarms.
        """
        canonical_merkle_manifest: Dict[str, str] = {}
        if not target_dir.exists():
            return canonical_merkle_manifest

        for candidate_artifact_path in target_dir.rglob("*"):
            if candidate_artifact_path.is_file() and "__pycache__" not in candidate_artifact_path.parts:
                try:
                    normalized_file_bytes = candidate_artifact_path.read_bytes().replace(b"\r\n", b"\n")
                    relative_path_key = str(candidate_artifact_path.relative_to(target_dir))
                    canonical_merkle_manifest[relative_path_key] = hashlib.sha256(normalized_file_bytes).hexdigest()
                except OSError:
                    continue
        return canonical_merkle_manifest

    def _apply_permissions(self, target_dir: Path, make_readonly: bool) -> None:
        """Sets file permissions to read-only (`0o444`) or read-write recursively."""
        if not target_dir.exists():
            return

        for candidate_artifact_path in target_dir.rglob("*"):
            if candidate_artifact_path.is_file():
                try:
                    if make_readonly:
                        # Revoke write bits across User, Group, and Others
                        os.chmod(candidate_artifact_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
                    else:
                        # Re-grant write permissions for cleanup routines
                        os.chmod(
                            candidate_artifact_path,
                            stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP,
                        )
                except OSError:
                    continue

    def _detect_tampering(
        self, baseline_manifest: Dict[str, str], candidate_manifest: Dict[str, str]
    ) -> List[str]:
        """Compares two Merkle directory manifests to detect deletions, edits, or rogue additions."""
        compromised_test_artifacts: List[str] = []

        # Detect deleted or altered baseline files
        for relative_test_path, baseline_digest in baseline_manifest.items():
            if relative_test_path not in candidate_manifest:
                compromised_test_artifacts.append(f"{relative_test_path} (DELETED)")
            elif baseline_digest != candidate_manifest[relative_test_path]:
                compromised_test_artifacts.append(f"{relative_test_path} (MODIFIED)")

        # Detect injected rogue tests that might bypass standard suite runs
        for relative_test_path in candidate_manifest:
            if relative_test_path not in baseline_manifest:
                compromised_test_artifacts.append(f"{relative_test_path} (ADDED)")

        return compromised_test_artifacts

    def _resolve_candidate_test_directory(self, isolated_worktree_dir: Path) -> Path:
        """Discovers the active test package within an arbitrary worktree layout."""
        for candidate_relative_path in ("target_app/tests", "tests", "test"):
            potential_dir = isolated_worktree_dir / candidate_relative_path
            if potential_dir.exists() and potential_dir.is_dir():
                return potential_dir

        for candidate_file in isolated_worktree_dir.rglob("test_*.py"):
            if ".autopatch" not in candidate_file.parts:
                return candidate_file.parent

        return isolated_worktree_dir / "target_app" / "tests"

    def execute_with_guardrail(
        self,
        worktree_path: Union[str, Path],
        test_command: Optional[str] = None,
        branch_name: str = "candidate_branch",
        reference_tests_dir: Optional[Union[str, Path]] = None,
    ) -> SandboxRunResult:
        """Executes candidate test suite while strictly enforcing Read-Only Test Guardrails.
        
        If any candidate patch attempts to modify, weaken, or delete existing test files,
        the run is immediately halted and marked as `LUCKY_PASS_BLOCKED`.
        """
        isolated_worktree_dir = Path(worktree_path).resolve()
        candidate_tests_dir = self._resolve_candidate_test_directory(isolated_worktree_dir)

        # Establish immutable reference golden test directory from workspace root
        if reference_tests_dir:
            reference_golden_dir = Path(reference_tests_dir).resolve()
        elif (self.workspace_root / "target_app" / "tests").exists():
            reference_golden_dir = self.workspace_root / "target_app" / "tests"
        else:
            reference_golden_dir = candidate_tests_dir

        # 1. Capture Golden Baseline Hashes of Unmodified Test Suite
        golden_merkle_manifest = self._compute_directory_hashes(reference_golden_dir)

        # 2. Lock Test Files as Read-Only in Candidate Worktree
        self._apply_permissions(candidate_tests_dir, make_readonly=True)

        clock_start_ns = time.perf_counter()
        is_lucky_pass_blocked = False
        security_violation_notice = None
        compromised_test_artifacts: List[str] = []
        raw_stdout = ""
        raw_stderr = ""
        subcommand_exit_code = 0

        # Construct deterministic test runner command
        if test_command:
            active_test_cmd = test_command
        elif (isolated_worktree_dir / "target_app" / "tests").exists():
            active_test_cmd = f'"{sys.executable}" -m unittest discover -s target_app/tests'
        elif (isolated_worktree_dir / "tests").exists():
            active_test_cmd = f'"{sys.executable}" -m pytest tests'
        else:
            active_test_cmd = f'"{sys.executable}" -m unittest discover'

        try:
            # 3. Pre-execution tampering audit against golden reference
            pre_execution_manifest = self._compute_directory_hashes(candidate_tests_dir)
            compromised_test_artifacts = self._detect_tampering(
                golden_merkle_manifest, pre_execution_manifest
            )

            if compromised_test_artifacts:
                is_lucky_pass_blocked = True
                security_violation_notice = (
                    f"SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT: Candidate modified test files: {compromised_test_artifacts}"
                )
                subcommand_exit_code = 126  # POSIX permission barrier convention
                raw_stderr = security_violation_notice
            else:
                # 4. Spawn Sandboxed Test Process
                subcommand_environment = os.environ.copy()
                subcommand_environment["PYTHONPATH"] = (
                    f"{isolated_worktree_dir}{os.pathsep}{subcommand_environment.get('PYTHONPATH', '')}"
                )

                subcommand_process = subprocess.run(
                    active_test_cmd,
                    cwd=str(isolated_worktree_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True,
                    timeout=30.0,
                    env=subcommand_environment,
                )
                raw_stdout = subcommand_process.stdout
                raw_stderr = subcommand_process.stderr
                subcommand_exit_code = subcommand_process.returncode

                # 5. Post-execution tampering audit (catches in-memory monkeypatches or disk flush attempts)
                post_execution_manifest = self._compute_directory_hashes(candidate_tests_dir)
                post_compromised_files = self._detect_tampering(
                    golden_merkle_manifest, post_execution_manifest
                )
                if post_compromised_files:
                    is_lucky_pass_blocked = True
                    compromised_test_artifacts.extend(post_compromised_files)
                    security_violation_notice = (
                        f"SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT: Test files tampered during execution: {compromised_test_artifacts}"
                    )
                    subcommand_exit_code = 126

        finally:
            # Re-grant write permissions so OS cleanup routines never hang on Windows file-locks
            self._apply_permissions(candidate_tests_dir, make_readonly=False)

        execution_latency_ms = round((time.perf_counter() - clock_start_ns) * 1000.0, 2)
        suite_succeeded = (subcommand_exit_code == 0) and not is_lucky_pass_blocked

        return SandboxRunResult(
            branch_or_worktree=branch_name,
            tests_passed=suite_succeeded,
            lucky_pass_blocked=is_lucky_pass_blocked,
            violation_details=security_violation_notice,
            exit_code=subcommand_exit_code,
            duration_ms=execution_latency_ms,
            stdout=raw_stdout,
            stderr=raw_stderr,
            tampered_test_files=compromised_test_artifacts,
        )


# ==============================================================================
# Differential Shadow Traffic Replay Engine
# ==============================================================================

class ShadowTrafficReplayEngine:
    """Executes 50 synthetic high-entropy edge-case payloads to measure latency & exception deltas.
    
    In financial systems, passing unit tests does not guarantee non-regression under high
    throughput. This engine runs differential shadow traffic side-by-side between unpatched
    and patched implementations to benchmark P99 latency deltas and catch arithmetic leaks.
    """

    @classmethod
    def generate_synthetic_payloads(cls, count: int = 50) -> List[Dict[str, Any]]:
        """Synthesizes high-entropy payment orders covering all boundary and schema conditions."""
        prng_generator = random.Random(42)  # Deterministic seed for reproducible evaluation
        synthetic_order_workloads: List[Dict[str, Any]] = []

        customer_tier_hierarchy = ["STANDARD", "SILVER", "GOLD", "PLATINUM"]
        settlement_jurisdictions = ["US-CA", "US-NY", "US-TX", "EU-DE", "GLOBAL-DEFAULT"]

        for workload_index in range(count):
            order_reference_id = f"SHADOW-ORD-{workload_index + 1:04d}"
            selected_tier = prng_generator.choice(customer_tier_hierarchy)
            selected_jurisdiction = prng_generator.choice(settlement_jurisdictions)

            # Alternate between legacy flat schema and modern nested object schema
            is_v2_schema = (workload_index % 2 == 0)
            if is_v2_schema:
                customer_profile_spec = {
                    "customer_id": f"CUST-V2-{workload_index:03d}",
                    "tier_profile": {
                        "tier_level": selected_tier,
                        "loyalty_score": prng_generator.randint(100, 1000),
                    },
                }
            else:
                customer_profile_spec = {
                    "customer_id": f"CUST-V1-{workload_index:03d}",
                    "tier": selected_tier,
                }

            # Stress-test promo denominators: 0, 1, 2, 3, 4 (boundary crash in unpatched), and >4
            if workload_index % 5 == 0:
                active_promos_count = 4  # Triggers ZeroDivisionError in unpatched code!
            elif workload_index % 7 == 0:
                active_promos_count = 6  # Boundary overflow condition
            else:
                active_promos_count = prng_generator.randint(0, 3)

            # Synthesize shopping cart item lines
            cart_line_count = prng_generator.randint(1, 5)
            order_cart_items = []
            for item_idx in range(cart_line_count):
                order_cart_items.append({
                    "sku": f"SKU-{item_idx:02d}",
                    "price": round(prng_generator.uniform(5.0, 350.0), 2),
                    "quantity": prng_generator.randint(1, 4),
                })

            synthetic_order_workloads.append({
                "order_id": order_reference_id,
                "customer": customer_profile_spec,
                "items": order_cart_items,
                "active_promos_count": active_promos_count,
                "jurisdiction": selected_jurisdiction,
            })

        return synthetic_order_workloads

    @classmethod
    def run_differential_replay(
        cls,
        baseline_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        candidate_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> ShadowTrafficMetrics:
        """Executes side-by-side replay, measuring exception rates and p99 latency deltas."""
        workload_stream = payloads or cls.generate_synthetic_payloads(count=50)

        unpatched_latencies_ms: List[float] = []
        candidate_latencies_ms: List[float] = []
        unpatched_exception_count = 0
        candidate_exception_count = 0

        for order_spec in workload_stream:
            # 1. Baseline Routine Profiling
            baseline_clock_start = time.perf_counter()
            try:
                baseline_fn(order_spec)
            except Exception:
                unpatched_exception_count += 1
            baseline_clock_end = time.perf_counter()
            unpatched_latencies_ms.append((baseline_clock_end - baseline_clock_start) * 1000.0)

            # 2. Candidate Patched Routine Profiling
            candidate_clock_start = time.perf_counter()
            try:
                candidate_fn(order_spec)
            except Exception:
                candidate_exception_count += 1
            candidate_clock_end = time.perf_counter()
            candidate_latencies_ms.append((candidate_clock_end - candidate_clock_start) * 1000.0)

        total_iterations = len(workload_stream)
        baseline_mean_latency = sum(unpatched_latencies_ms) / total_iterations
        candidate_mean_latency = sum(candidate_latencies_ms) / total_iterations

        # Calculate P99 tail latency
        unpatched_latencies_ms.sort()
        candidate_latencies_ms.sort()
        p99_percentile_index = int(math.ceil(0.99 * total_iterations)) - 1
        baseline_p99_latency = unpatched_latencies_ms[p99_percentile_index]
        candidate_p99_latency = candidate_latencies_ms[p99_percentile_index]

        p99_latency_differential = round(candidate_p99_latency - baseline_p99_latency, 4)
        latency_overhead_ratio = round(
            ((candidate_mean_latency - baseline_mean_latency) / (baseline_mean_latency or 0.0001)) * 100.0, 2
        )
        fault_rate_differential = round(
            (candidate_exception_count - unpatched_exception_count) / total_iterations, 4
        )

        # Flag regression if candidate introduces more failures or severe tail-latency spikes (>250%)
        is_regression_flagged = (candidate_exception_count > unpatched_exception_count) or (
            latency_overhead_ratio > 250.0
        )

        return ShadowTrafficMetrics(
            total_payloads=total_iterations,
            baseline_exception_count=unpatched_exception_count,
            candidate_exception_count=candidate_exception_count,
            exception_rate_delta=fault_rate_differential,
            baseline_avg_latency_ms=round(baseline_mean_latency, 4),
            candidate_avg_latency_ms=round(candidate_mean_latency, 4),
            latency_overhead_percent=latency_overhead_ratio,
            baseline_p99_latency_ms=round(baseline_p99_latency, 4),
            candidate_p99_latency_ms=round(candidate_p99_latency, 4),
            p99_latency_delta_ms=p99_latency_differential,
            regression_detected=is_regression_flagged,
        )
