"""Typed state graph used instead of transcript-only memory."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping

from protocol.digest import sha256_digest


@dataclass(frozen=True)
class HarnessState:
    task_id: str
    claims: tuple[str, ...] = ()
    observed_facts: tuple[str, ...] = ()
    executed_actions: tuple[str, ...] = ()
    verified_outcomes: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    authority: str = "sandbox"
    checkpoint_id: str | None = None
    revision: int = 0

    def digest(self) -> str:
        return sha256_digest(self.as_dict())

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "claims": list(self.claims),
            "observed_facts": list(self.observed_facts),
            "executed_actions": list(self.executed_actions),
            "verified_outcomes": list(self.verified_outcomes),
            "assumptions": list(self.assumptions),
            "unresolved_questions": list(self.unresolved_questions),
            "artifacts": list(self.artifacts),
            "authority": self.authority,
            "checkpoint_id": self.checkpoint_id,
            "revision": self.revision,
        }

    def update(
        self,
        *,
        facts: Iterable[str] = (),
        actions: Iterable[str] = (),
        verified: Iterable[str] = (),
        assumptions: Iterable[str] = (),
        open_questions: Iterable[str] = (),
        artifacts: Iterable[str] = (),
    ) -> "HarnessState":
        def add(existing: tuple[str, ...], values: Iterable[str]) -> tuple[str, ...]:
            result = list(existing)
            for value in values:
                if value and value not in result:
                    result.append(value)
            return tuple(result)

        return replace(
            self,
            observed_facts=add(self.observed_facts, facts),
            executed_actions=add(self.executed_actions, actions),
            verified_outcomes=add(self.verified_outcomes, verified),
            assumptions=add(self.assumptions, assumptions),
            unresolved_questions=add(self.unresolved_questions, open_questions),
            artifacts=add(self.artifacts, artifacts),
            revision=self.revision + 1,
        )

    def with_checkpoint(self, checkpoint_id: str) -> "HarnessState":
        return replace(self, checkpoint_id=checkpoint_id, revision=self.revision + 1)
