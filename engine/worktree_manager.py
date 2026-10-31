"""Parallel Git Worktree Manager & Multi-Agent Race Orchestrator.

Spawns and manages 3 concurrent isolated Git worktrees (.autopatch/worktrees/)
using native `git worktree add` commands with thread-safe locking and executes
competing repair hypotheses under the Read-Only Sandbox Guardrail.
"""
from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from engine.critic_agent import CriticEvaluation, MuseWonderCritic
from engine.memory_store import TrajectoryMemoryStore, TrajectoryRecord
from engine.meta_model_router import MetaModelRouter, ModelPatchCandidate
from mcp_server.ast_graph_mcp import ASTSubGraphResponse, SyscallTelemetry
from sandbox.sandbox_runner import SandboxRunResult, SandboxRunner, ShadowTrafficMetrics, ShadowTrafficReplayEngine


def _remove_readonly(func, path, excinfo):
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _safe_rmtree(target: Path):
    if not target.exists():
        return
    try:
        shutil.rmtree(target, onerror=_remove_readonly)
    except Exception:
        pass


class WorktreeExecutionOutcome(BaseModel):
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
    total_candidates: int
    outcomes: List[WorktreeExecutionOutcome]
    winner_outcome: Optional[WorktreeExecutionOutcome] = None
    total_race_duration_ms: float = 0.0


class WorktreeManager:
    """Thread-safe orchestrator for isolated parallel Git worktree execution."""

    def __init__(self, workspace_root: Optional[str | Path] = None):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.worktree_base_dir = self.workspace_root / ".autopatch" / "worktrees"
        self.git_lock = threading.Lock()
        self.sandbox_runner = SandboxRunner(str(self.workspace_root))
        self.memory_store = TrajectoryMemoryStore()
        self.meta_router = MetaModelRouter()

    def _run_git_command(self, args: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
        """Runs git command safely under git_lock to avoid index.lock contention."""
        with self.git_lock:
            cmd = ["git"] + args
            res = subprocess.run(
                cmd,
                cwd=str(cwd or self.workspace_root),
                capture_output=True,
                text=True,
            )
            return res.returncode, res.stdout, res.stderr

    def create_isolated_worktree(self, worktree_name: str) -> Path:
        """Creates or reuses an isolated Git worktree under .autopatch/worktrees/<name>."""
        wt_path = (self.worktree_base_dir / worktree_name).resolve()
        branch_name = f"autopatch/{worktree_name}"

        # Clean up existing worktree if present
        if wt_path.exists():
            self._run_git_command(["worktree", "remove", "--force", str(wt_path)])
            if wt_path.exists():
                _safe_rmtree(wt_path)

        self._run_git_command(["branch", "-D", branch_name])
        self.worktree_base_dir.mkdir(parents=True, exist_ok=True)

        # Create new worktree branched from HEAD
        code, out, err = self._run_git_command(
            ["worktree", "add", "-B", branch_name, str(wt_path), "HEAD"]
        )

        if code != 0 or not wt_path.exists():
            # Fallback to isolated directory copy if git worktree fails (e.g. sandbox permissions)
            if not wt_path.exists():
                shutil.copytree(
                    self.workspace_root,
                    wt_path,
                    ignore=shutil.ignore_patterns(".git", ".autopatch", "__pycache__"),
                )

        return wt_path

    def apply_patch_candidate(self, worktree_path: Path, candidate: ModelPatchCandidate):
        """Applies candidate file patches to the target worktree."""
        for patch in candidate.patches:
            target_file = worktree_path / patch.relative_path
            target_file.parent.mkdir(parents=True, exist_ok=True)

            if target_file.exists():
                content = target_file.read_text(encoding="utf-8")
                if patch.original_snippet in content:
                    new_content = content.replace(patch.original_snippet, patch.patched_snippet, 1)
                    target_file.write_text(new_content, encoding="utf-8")
                else:
                    # Append or write if exact snippet not found
                    target_file.write_text(patch.patched_snippet, encoding="utf-8")
            else:
                target_file.write_text(patch.patched_snippet, encoding="utf-8")

    def execute_single_candidate(
        self,
        candidate: ModelPatchCandidate,
    ) -> WorktreeExecutionOutcome:
        """Executes a single candidate hypothesis from setup through Critic, Sandbox, and Memory."""
        start_time = time.perf_counter()

        # 1. Muse Wonder Critic Gate
        critic_eval = MuseWonderCritic.evaluate_candidate(candidate, allow_adversarial_probes=True)
        if not critic_eval.is_approved:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            record = self.memory_store.record_trajectory(
                strategy_id=candidate.strategy_id,
                hypothesis_name=candidate.hypothesis_name,
                worktree_name=candidate.target_worktree,
                verdict="CRITIC_REJECTED",
                files_modified=[p.relative_path for p in candidate.patches],
                error_summary=critic_eval.critique_notes,
            )
            return WorktreeExecutionOutcome(
                strategy_id=candidate.strategy_id,
                hypothesis_name=candidate.hypothesis_name,
                worktree_name=candidate.target_worktree,
                worktree_path="",
                critic_evaluation=critic_eval,
                trajectory_record=record,
                is_disqualified=True,
                disqualification_reason=f"CRITIC_REJECTED: {critic_eval.critique_notes}",
                execution_duration_ms=duration_ms,
            )

        # 2. Setup Isolated Worktree
        wt_path = self.create_isolated_worktree(candidate.target_worktree)

        # 3. Apply Patches
        self.apply_patch_candidate(wt_path, candidate)

        # 4. Execute under Read-Only Sandbox Guardrail
        sandbox_res = self.sandbox_runner.execute_with_guardrail(
            worktree_path=wt_path,
            branch_name=candidate.target_worktree,
            reference_tests_dir=self.workspace_root / "target_app" / "tests",
        )

        is_disqualified = False
        disqual_reason = None
        verdict = "PASSED" if sandbox_res.tests_passed else "FAILED_TESTS"

        if sandbox_res.lucky_pass_blocked:
            is_disqualified = True
            disqual_reason = "SECURITY_VIOLATION: LUCKY_PASS_ATTEMPT: Candidate modified test assertions."
            verdict = "LUCKY_PASS_BLOCKED"
        elif not sandbox_res.tests_passed:
            is_disqualified = True
            disqual_reason = f"TESTS_FAILED: Exit code {sandbox_res.exit_code}"

        # 5. Record Trajectory in Memory Store
        record = self.memory_store.record_trajectory(
            strategy_id=candidate.strategy_id,
            hypothesis_name=candidate.hypothesis_name,
            worktree_name=candidate.target_worktree,
            verdict=verdict,  # type: ignore
            files_modified=[p.relative_path for p in candidate.patches],
            error_summary=disqual_reason or sandbox_res.stderr or None,
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return WorktreeExecutionOutcome(
            strategy_id=candidate.strategy_id,
            hypothesis_name=candidate.hypothesis_name,
            worktree_name=candidate.target_worktree,
            worktree_path=str(wt_path),
            critic_evaluation=critic_eval,
            sandbox_result=sandbox_res,
            trajectory_record=record,
            is_disqualified=is_disqualified,
            disqualification_reason=disqual_reason,
            execution_duration_ms=duration_ms,
        )

    def race_competing_hypotheses(
        self,
        ast_subgraph: ASTSubGraphResponse,
        telemetry: SyscallTelemetry,
    ) -> WorktreeTournamentRaceResult:
        """Launches 3 concurrent candidate worktrees via ThreadPoolExecutor."""
        total_start = time.perf_counter()

        # Generate candidates via Meta Model Router
        candidates = self.meta_router.synthesize_competing_hypotheses(ast_subgraph, telemetry)

        outcomes: List[WorktreeExecutionOutcome] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_candidate = {
                executor.submit(self.execute_single_candidate, c): c for c in candidates
            }
            for future in concurrent.futures.as_completed(future_to_candidate):
                try:
                    outcome = future.result()
                    outcomes.append(outcome)
                except Exception as ex:
                    c = future_to_candidate[future]
                    outcomes.append(
                        WorktreeExecutionOutcome(
                            strategy_id=c.strategy_id,
                            hypothesis_name=c.hypothesis_name,
                            worktree_name=c.target_worktree,
                            worktree_path="",
                            critic_evaluation=CriticEvaluation(
                                is_approved=False,
                                critic_score=0.0,
                                critique_notes=str(ex),
                                syntax_valid=False,
                                security_clean=False,
                            ),
                            is_disqualified=True,
                            disqualification_reason=str(ex),
                        )
                    )

        # Sort outcomes to preserve canonical order (A, B, C)
        order_map = {
            "worktree_a_refactor": 0,
            "worktree_b_adapter": 1,
            "worktree_c_guard": 2,
        }
        outcomes.sort(key=lambda o: order_map.get(o.worktree_name, 99))

        winner = next((o for o in outcomes if not o.is_disqualified and o.sandbox_result and o.sandbox_result.tests_passed), None)
        total_duration = round((time.perf_counter() - total_start) * 1000.0, 2)

        return WorktreeTournamentRaceResult(
            total_candidates=len(candidates),
            outcomes=outcomes,
            winner_outcome=winner,
            total_race_duration_ms=total_duration,
        )

