"""Checkpointed state snapshots for bounded branch/search experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from protocol.digest import sha256_digest
from .state import HarnessState


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    state: HarnessState
    trace_length: int
    reason: str


class CheckpointManager:
    def __init__(self, *, max_checkpoints: int = 32) -> None:
        self.max_checkpoints = max_checkpoints
        self._checkpoints: dict[str, Checkpoint] = {}

    def save(self, state: HarnessState, trace_length: int, reason: str) -> Checkpoint:
        checkpoint_id = sha256_digest({"state": state.as_dict(), "trace_length": trace_length, "reason": reason})
        checkpoint = Checkpoint(checkpoint_id, state.with_checkpoint(checkpoint_id), trace_length, reason)
        self._checkpoints[checkpoint_id] = checkpoint
        while len(self._checkpoints) > self.max_checkpoints:
            self._checkpoints.pop(next(iter(self._checkpoints)))
        return checkpoint

    def get(self, checkpoint_id: str) -> Checkpoint:
        return self._checkpoints[checkpoint_id]

    def all(self) -> tuple[Checkpoint, ...]:
        return tuple(self._checkpoints.values())
