"""Trajectory Memory Store (.autopatch/memory.json).

Maintains a persistent, append-only history of evaluated repair hypotheses, compiler
diagnostics, and security guardrail traps. Prevents multi-agent reasoning loops from
repeating proven dead-end mutations or adversarial test tampering strategies.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TrajectoryRecord(BaseModel):
    """Immutable audit entry capturing a single hypothesis trial in the worktree tournament."""
    trajectory_id: str
    strategy_id: str
    hypothesis_name: str
    worktree_name: str
    verdict: Literal["PASSED", "LUCKY_PASS_BLOCKED", "FAILED_TESTS", "CRITIC_REJECTED"]
    files_modified: List[str]
    error_summary: Optional[str] = None
    lessons_learned: str
    timestamp_unix: float = Field(default_factory=time.time)


class TrajectoryMemoryStore:
    """Manages reading and writing to `.autopatch/memory.json` with POSIX-compliant atomic persistence."""

    def __init__(self, memory_path: Optional[str | Path] = None):
        self.memory_path = Path(
            memory_path or (Path(os.getcwd()) / ".autopatch" / "memory.json")
        ).resolve()
        self.records: List[TrajectoryRecord] = []
        self._load_persisted_state()

    def _load_persisted_state(self) -> None:
        """Hydrates past trajectory records from disk or initializes an empty buffer."""
        if self.memory_path.exists():
            try:
                raw_json_buffer = self.memory_path.read_text(encoding="utf-8")
                raw_memory_payload = json.loads(raw_json_buffer)
                self.records = [
                    TrajectoryRecord.model_validate(trajectory_entry)
                    for trajectory_entry in raw_memory_payload
                ]
            except Exception:
                self.records = []
        else:
            self.records = []

    def save(self) -> None:
        """Flushes in-memory trajectories to disk using atomic temporary file renaming.
        
        Writing directly to memory.json can corrupt the file if a process is killed mid-write.
        Writing to .tmp and replacing atomically guarantees transaction durability.
        """
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        serialized_trajectory_manifest = [
            trajectory_entry.model_dump() for trajectory_entry in self.records
        ]
        atomic_swap_filepath = self.memory_path.with_suffix(".tmp")
        atomic_swap_filepath.write_text(
            json.dumps(serialized_trajectory_manifest, indent=2), encoding="utf-8"
        )
        atomic_swap_filepath.replace(self.memory_path)

    def record_trajectory(
        self,
        strategy_id: str,
        hypothesis_name: str,
        worktree_name: str,
        verdict: Literal["PASSED", "LUCKY_PASS_BLOCKED", "FAILED_TESTS", "CRITIC_REJECTED"],
        files_modified: List[str],
        error_summary: Optional[str] = None,
        lessons_learned: Optional[str] = None,
    ) -> TrajectoryRecord:
        """Appends a new hypothesis execution result into persistent trajectory memory."""
        synthesized_trajectory_id = (
            f"TRAJ-{strategy_id[:8].upper()}-{int(time.time() * 1000) % 100000}"
        )

        if not lessons_learned:
            if verdict == "LUCKY_PASS_BLOCKED":
                lessons_learned = (
                    "Attempting to modify existing test assertions is caught by Read-Only Sandbox Guardrail. "
                    "Modify implementation code instead."
                )
            elif verdict == "PASSED":
                lessons_learned = (
                    "Surgical multi-file AST bounds and backward-compatible tier schema successfully "
                    "heal the crash without regressions."
                )
            else:
                lessons_learned = (
                    "Defensive exception suppression without root-cause schema resolution leads to high latency "
                    "or functional failure."
                )

        logged_record = TrajectoryRecord(
            trajectory_id=synthesized_trajectory_id,
            strategy_id=strategy_id,
            hypothesis_name=hypothesis_name,
            worktree_name=worktree_name,
            verdict=verdict,
            files_modified=files_modified,
            error_summary=error_summary,
            lessons_learned=lessons_learned,
        )

        self.records.append(logged_record)
        self.save()
        return logged_record

    def get_failed_strategies(self) -> List[str]:
        """Returns strategy IDs that resulted in non-passing execution verdicts."""
        return [
            persisted_entry.strategy_id
            for persisted_entry in self.records
            if persisted_entry.verdict != "PASSED"
        ]

    def is_known_dead_end(self, target_strategy_id: str) -> bool:
        """Determines if a candidate strategy was already marked as a failed dead end in past iterations."""
        return target_strategy_id in self.get_failed_strategies()
