"""Bounded checkpoint branch selection for test-time search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class BranchCandidate:
    branch_id: str
    score: float
    verified: bool
    cost: float
    payload: Any


class BranchSearch:
    def __init__(self, *, max_branches: int = 3) -> None:
        self.max_branches = max_branches

    def select(self, candidates: Iterable[BranchCandidate]) -> BranchCandidate | None:
        ranked = sorted(candidates, key=lambda item: (item.verified, item.score, -item.cost), reverse=True)
        return ranked[0] if ranked else None

    def evaluate(self, payloads: Iterable[Any], evaluator: Callable[[Any], BranchCandidate]) -> BranchCandidate | None:
        candidates = [evaluator(payload) for payload in list(payloads)[: self.max_branches]]
        return self.select(candidates)
