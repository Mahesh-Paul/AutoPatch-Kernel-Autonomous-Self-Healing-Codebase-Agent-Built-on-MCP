"""Trajectory Memory Store (.autopatch/memory.json).

Maintains a persistent record of attempted repair strategies, compiler errors,
and failure modes so subsequent agent reasoning cycles never repeat dead-end hypotheses.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TrajectoryRecord(BaseModel):
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
    """Manages reading and writing to .autopatch/memory.json with atomic persistence."""

    def __init__(self, memory_path: Optional[str | Path] = None):
        self.memory_path = Path(memory_path or (Path(os.getcwd()) / ".autopatch" / "memory.json")).resolve()
        self.records: List[TrajectoryRecord] = []
        self._load()

    def _load(self):
        if self.memory_path.exists():
            try:
                content = self.memory_path.read_text(encoding="utf-8")
                data = json.loads(content)
                self.records = [TrajectoryRecord.model_validate(r) for r in data]
            except Exception:
                self.records = []
        else:
            self.records = []

    def save(self):
        """Persists memory store to disk atomically."""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [r.model_dump() for r in self.records]
        temp_file = self.memory_path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        temp_file.replace(self.memory_path)

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
        """Records an execution outcome into persistent trajectory memory."""
        traj_id = f"TRAJ-{strategy_id[:8].upper()}-{int(time.time() * 1000) % 100000}"

        if not lessons_learned:
            if verdict == "LUCKY_PASS_BLOCKED":
                lessons_learned = "Attempting to modify existing test assertions is caught by Read-Only Sandbox Guardrail. Modify implementation code instead."
            elif verdict == "PASSED":
                lessons_learned = "Surgical multi-file AST bounds and backward-compatible tier schema successfully heal the crash without regressions."
            else:
                lessons_learned = "Defensive exception suppression without root-cause schema resolution leads to high latency or functional failure."

        record = TrajectoryRecord(
            trajectory_id=traj_id,
            strategy_id=strategy_id,
            hypothesis_name=hypothesis_name,
            worktree_name=worktree_name,
            verdict=verdict,
            files_modified=files_modified,
            error_summary=error_summary,
            lessons_learned=lessons_learned,
        )

        self.records.append(record)
        self.save()
        return record

    def get_failed_strategies(self) -> List[str]:
        """Returns IDs of strategies that failed execution."""
        return [r.strategy_id for r in self.records if r.verdict != "PASSED"]

    def is_known_dead_end(self, strategy_id: str) -> bool:
        """Checks if a strategy has already failed in the past."""
        return strategy_id in self.get_failed_strategies()

