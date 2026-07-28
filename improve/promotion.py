"""Bounded harness self-improvement with held-out regression protection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    surface: str
    description: str
    changes: Mapping[str, object]


@dataclass(frozen=True)
class ProposalResult:
    proposal_id: str
    held_in_before: float
    held_in_after: float
    held_out_before: float
    held_out_after: float
    promoted: bool
    reason: str


class PromotionGate:
    """Evaluator and protected surfaces remain outside proposal data."""

    PROTECTED = frozenset({"evaluator", "trace_recorder", "model_identity", "budget", "authority_boundary", "sandbox", "promotion_rules"})
    EDITABLE = frozenset({"context_rules", "tool_descriptions", "recovery_middleware", "routing_thresholds", "checkpoint_policy"})

    def evaluate(
        self,
        proposal: Proposal,
        *,
        held_in: Callable[[Proposal | None], float],
        held_out: Callable[[Proposal | None], float],
        canary: Callable[[Proposal], bool] | None = None,
    ) -> ProposalResult:
        if proposal.surface not in self.EDITABLE:
            raise ValueError(f"proposal surface is not editable: {proposal.surface}")
        if any(key in self.PROTECTED for key in proposal.changes):
            raise ValueError("proposal attempts to edit a protected surface")
        in_before = held_in(None)
        out_before = held_out(None)
        in_after = held_in(proposal)
        out_after = held_out(proposal)
        passed = in_after >= in_before and out_after >= out_before and (canary(proposal) if canary else True)
        reason = "held-in and held-out regression gates passed" if passed else "rejected by held-out or canary regression gate"
        return ProposalResult(proposal.proposal_id, in_before, in_after, out_before, out_after, passed, reason)
