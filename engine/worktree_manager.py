"""Parallel Git Worktree Manager & Multi-Agent Hypothesis Race Orchestrator.

Spawns and orchestrates concurrent, completely isolated Git worktrees within
`.autopatch/worktrees/` using native `git worktree add` commands under fine-grained
thread locks. Executes speculative repair candidates against the Read-Only Sandbox
Guardrail, recording structured trajectory records to the memory substrate.
"""
from __future__ import annotations

import concurrent.futures
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from engine.critic_agent import CriticEvaluation, MuseWonderCritic
from engine.memory_store import TrajectoryMemoryStore, TrajectoryRecord
from engine.meta_model_router import MetaModelRouter, ModelPatchCandidate
from mcp_server.ast_graph_mcp import ASTSubGraphResponse, SyscallTelemetry
from sandbox.sandbox_runner import (
    SandboxRunResult,
    SandboxRunner,
    ShadowTrafficMetrics,
    ShadowTrafficReplayEngine,
)


class WorktreeLifecycleException(RuntimeError):
    """Raised when git worktree instantiation, branch locking, or filesystem cleanup fails."""
    pass


def _force_unlock_and_unlink(operation_func: Callable[[str], Any], filesystem_path: str, exception_context: Any) -> None:
    """Error handler for shutil.rmtree on Windows to strip FILE_ATTRIBUTE_READONLY bit and retry."""
    try:
        os.chmod(filesystem_path, stat.S_IWRITE | stat.S_IREAD)
        operation_func(filesystem_path)
    except Exception:
        # Suppress secondary cleanup exceptions to prevent unhandled aborts during worktree cycling
        pass


def _safely_purge_worktree_tree(target_worktree_directory: Path) -> None:
    """Recursively removes a worktree directory hierarchy, clearing lock attributes safely."""
    if not target_worktree_directory.exists():
        return
    try:
        shutil.rmtree(target_worktree_directory, onerror=_force_unlock_and_unlink)
    except Exception:
        pass


class WorktreeExecutionOutcome(BaseModel):
    """Encapsulates the full execution lifecycle and verification outcomes of a single candidate worktree."""
    strategy_id: str
    hypothesis_name: str
    worktree_name: str
    worktree_path: str
    critic_evaluation: CriticEvaluation
    sandbox_result: Optional[SandboxRunResult] = None
    trajectory_record: Optional[TrajectoryRecord] = None
    shadow_metrics: Optional[ShadowTrafficMetrics] = None
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None
    execution_duration_ms: float = 0.0


class WorktreeTournamentRaceResult(BaseModel):
    """Aggregate outcomes across all parallel worktree candidates executed during a tournament round."""
    total_candidates: int
    outcomes: List[WorktreeExecutionOutcome]
    winner_outcome: Optional[WorktreeExecutionOutcome] = None
    total_race_duration_ms: float = 0.0


class WorktreeManager:
    """Thread-safe orchestrator managing isolated parallel Git worktree branch lifecycles."""

    def __init__(self, workspace_root: Optional[str | Path] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.worktree_base_dir = self.workspace_root / ".autopatch" / "worktrees"
        self.git_index_mutex = threading.Lock()
        self.sandbox_runner = SandboxRunner(str(self.workspace_root))
        self.memory_store = TrajectoryMemoryStore()
        self.meta_router = MetaModelRouter()

    def _execute_git_operation(
        self,
        command_arguments: List[str],
        execution_cwd: Optional[Path] = None,
    ) -> Tuple[int, str, str]:
        """Runs a Git CLI command safely guarded by a mutex to eliminate git index.lock contention.
        
        Git cannot safely modify its index across multiple concurrent child processes in the same repo.
        Serializing git worktree creations via `self.git_index_mutex` guarantees collision-free branching.
        """
        with self.git_index_mutex:
            cli_invocation = ["git"] + command_arguments
            git_process = subprocess.run(
                cli_invocation,
                cwd=str(execution_cwd or self.workspace_root),
                capture_output=True,
                text=True,
            )
            return git_process.returncode, git_process.stdout, git_process.stderr

    def create_isolated_worktree(self, target_worktree_slug: str) -> Path:
        """Provisions an isolated Git worktree under `.autopatch/worktrees/<slug>` branched from HEAD."""
        isolated_worktree_dir = (self.worktree_base_dir / target_worktree_slug).resolve()
        speculative_branch_ref = f"autopatch/{target_worktree_slug}"

        # Clean up stale worktree or filesystem residual from preceding runs
        if isolated_worktree_dir.exists():
            self._execute_git_operation(["worktree", "remove", "--force", str(isolated_worktree_dir)])
            if isolated_worktree_dir.exists():
                _safely_purge_worktree_tree(isolated_worktree_dir)

        self._execute_git_operation(["branch", "-D", speculative_branch_ref])
        self.worktree_base_dir.mkdir(parents=True, exist_ok=True)

        # Checkout fresh speculative worktree at current HEAD commit
        exit_code, stdout_msg, stderr_msg = self._execute_git_operation(
            ["worktree", "add", "-B", speculative_branch_ref, str(isolated_worktree_dir), "HEAD"]
        )

        if exit_code != 0 or not isolated_worktree_dir.exists():
            # Fallback for environments where git worktree is restricted (e.g. restrictive container sandbox)
            if not isolated_worktree_dir.exists():
                shutil.copytree(
                    self.workspace_root,
                    isolated_worktree_dir,
                    ignore=shutil.ignore_patterns(".git", ".autopatch", "__pycache__", ".pytest_cache"),
                )

        return isolated_worktree_dir

    @staticmethod
    def _resolve_tests_dir(repository_root: Path) -> Path:
        """Locates the canonical test directory within the target codebase dynamically."""
        for standard_test_path in ["target_app/tests", "tests", "test"]:
            resolved_candidate = repository_root / standard_test_path
            if resolved_candidate.exists() and resolved_candidate.is_dir():
                return resolved_candidate
        for python_test_file in repository_root.rglob("test_*.py"):
            if ".autopatch" not in python_test_file.parts:
                return python_test_file.parent
        return repository_root / "target_app" / "tests"

    def apply_patch_candidate(self, isolated_worktree_dir: Path, candidate_patch_spec: ModelPatchCandidate) -> None:
        """Applies candidate source mutations into the isolated worktree filesystem."""
        for file_patch in candidate_patch_spec.patches:
            destination_target_file = isolated_worktree_dir / file_patch.relative_path
            if not destination_target_file.exists():
                file_basename = Path(file_patch.relative_path).name
                discovered_matches = [
                    matched_file
                    for matched_file in isolated_worktree_dir.rglob(file_basename)
                    if ".autopatch" not in matched_file.parts
                ]
                if discovered_matches:
                    destination_target_file = discovered_matches[0]

            destination_target_file.parent.mkdir(parents=True, exist_ok=True)

            if destination_target_file.exists():
                baseline_source_content = destination_target_file.read_text(encoding="utf-8")
                if file_patch.original_snippet in baseline_source_content:
                    mutated_source = baseline_source_content.replace(
                        file_patch.original_snippet, file_patch.patched_snippet, 1
                    )
                    destination_target_file.write_text(mutated_source, encoding="utf-8")
                else:
                    # In extreme structural rewrites, replace file contents directly
                    destination_target_file.write_text(file_patch.patched_snippet, encoding="utf-8")
            else:
                destination_target_file.write_text(file_patch.patched_snippet, encoding="utf-8")

    def execute_single_candidate(
        self,
        candidate_patch_spec: ModelPatchCandidate,
    ) -> WorktreeExecutionOutcome:
        """Executes candidate verification from Muse Wonder Critic pre-check through Sandbox test evaluation."""
        hypothesis_execution_timer_start = time.perf_counter()

        # 1. Muse Wonder Critic Pre-flight Filter
        critic_evaluation = MuseWonderCritic.evaluate_candidate(
            candidate_patch_spec, allow_adversarial_probes=True
        )
        if not critic_evaluation.is_approved:
            elapsed_critic_ms = round((time.perf_counter() - hypothesis_execution_timer_start) * 1000.0, 2)
            logged_trajectory = self.memory_store.record_trajectory(
                strategy_id=candidate_patch_spec.strategy_id,
                hypothesis_name=candidate_patch_spec.hypothesis_name,
                worktree_name=candidate_patch_spec.target_worktree,
                verdict="CRITIC_REJECTED",
                files_modified=[patch_entry.relative_path for patch_entry in candidate_patch_spec.patches],
                error_summary=critic_evaluation.critique_notes,
            )
            return WorktreeExecutionOutcome(
                strategy_id=candidate_patch_spec.strategy_id,
                hypothesis_name=candidate_patch_spec.hypothesis_name,
                worktree_name=candidate_patch_spec.target_worktree,
                worktree_path="",
                critic_evaluation=critic_evaluation,
                trajectory_record=logged_trajectory,
                is_disqualified=True,
                disqualification_reason=f"CRITIC_REJECTED: {critic_evaluation.critique_notes}",
                execution_duration_ms=elapsed_critic_ms,
            )

        # 2. Allocate Isolated Speculative Worktree
        active_worktree_path = self.create_isolated_worktree(candidate_patch_spec.target_worktree)

        # 3. Inject Candidate Patch Mutations
        self.apply_patch_candidate(active_worktree_path, candidate_patch_spec)

        # 4. Execute Test Suite under Cryptographic Read-Only Sandbox Guardrail
        canonical_test_directory = self._resolve_tests_dir(self.workspace_root)
        sandbox_execution_verdict = self.sandbox_runner.execute_with_guardrail(
            worktree_path=active_worktree_path,
            branch_name=candidate_patch_spec.target_worktree,
            reference_tests_dir=canonical_test_directory,
        )

        is_disqualified = False
        rejection_rationale = None
        verdict_status = "PASSED" if sandbox_execution_verdict.tests_passed else "FAILED_TESTS"

        if sandbox_execution_verdict.lucky_pass_blocked:
            is_disqualified = True
            rejection_rationale = "SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT: Candidate modified test assertions."
            verdict_status = "LUCKY_PASS_BLOCKED"
        elif not sandbox_execution_verdict.tests_passed:
            is_disqualified = True
            rejection_rationale = f"TESTS_FAILED: Exit code {sandbox_execution_verdict.exit_code}"

        # 5. Persist Trajectory Telemetry in Memory Engine
        logged_trajectory = self.memory_store.record_trajectory(
            strategy_id=candidate_patch_spec.strategy_id,
            hypothesis_name=candidate_patch_spec.hypothesis_name,
            worktree_name=candidate_patch_spec.target_worktree,
            verdict=verdict_status,  # type: ignore
            files_modified=[patch_entry.relative_path for patch_entry in candidate_patch_spec.patches],
            error_summary=rejection_rationale or sandbox_execution_verdict.stderr or None,
        )

        total_candidate_duration_ms = round(
            (time.perf_counter() - hypothesis_execution_timer_start) * 1000.0, 2
        )

        return WorktreeExecutionOutcome(
            strategy_id=candidate_patch_spec.strategy_id,
            hypothesis_name=candidate_patch_spec.hypothesis_name,
            worktree_name=candidate_patch_spec.target_worktree,
            worktree_path=str(active_worktree_path),
            critic_evaluation=critic_evaluation,
            sandbox_result=sandbox_execution_verdict,
            trajectory_record=logged_trajectory,
            is_disqualified=is_disqualified,
            disqualification_reason=rejection_rationale,
            execution_duration_ms=total_candidate_duration_ms,
        )

    def race_competing_hypotheses(
        self,
        ast_subgraph: ASTSubGraphResponse,
        telemetry: SyscallTelemetry,
    ) -> WorktreeTournamentRaceResult:
        """Dispatches 3 competing candidate worktrees concurrently across thread workers."""
        race_clock_start = time.perf_counter()

        # Synthesize 3 distinct repair strategies via Meta Model Router
        candidate_patch_set = self.meta_router.synthesize_competing_hypotheses(ast_subgraph, telemetry)

        collected_outcomes: List[WorktreeExecutionOutcome] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as race_pool:
            future_to_candidate_map = {
                race_pool.submit(self.execute_single_candidate, patch_candidate): patch_candidate
                for patch_candidate in candidate_patch_set
            }
            for completed_future in concurrent.futures.as_completed(future_to_candidate_map):
                try:
                    candidate_outcome = completed_future.result()
                    collected_outcomes.append(candidate_outcome)
                except Exception as thread_dispatch_exception:
                    faulty_candidate = future_to_candidate_map[completed_future]
                    collected_outcomes.append(
                        WorktreeExecutionOutcome(
                            strategy_id=faulty_candidate.strategy_id,
                            hypothesis_name=faulty_candidate.hypothesis_name,
                            worktree_name=faulty_candidate.target_worktree,
                            worktree_path="",
                            critic_evaluation=CriticEvaluation(
                                is_approved=False,
                                critic_score=0.0,
                                critique_notes=str(thread_dispatch_exception),
                                syntax_valid=False,
                                security_clean=False,
                            ),
                            is_disqualified=True,
                            disqualification_reason=str(thread_dispatch_exception),
                        )
                    )

        # Canonical sort ordering: worktree_a (Winner), worktree_b (Lucky pass), worktree_c (Brute force)
        canonical_display_order = {
            "worktree_a_refactor": 0,
            "worktree_b_adapter": 1,
            "worktree_c_guard": 2,
        }
        collected_outcomes.sort(key=lambda outcome: canonical_display_order.get(outcome.worktree_name, 99))

        tournament_winner = next(
            (
                outcome
                for outcome in collected_outcomes
                if not outcome.is_disqualified
                and outcome.sandbox_result
                and outcome.sandbox_result.tests_passed
            ),
            None,
        )
        total_race_elapsed_ms = round((time.perf_counter() - race_clock_start) * 1000.0, 2)

        return WorktreeTournamentRaceResult(
            total_candidates=len(candidate_patch_set),
            outcomes=collected_outcomes,
            winner_outcome=tournament_winner,
            total_race_duration_ms=total_race_elapsed_ms,
        )
