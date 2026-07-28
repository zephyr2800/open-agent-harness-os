"""Authority and risk policy kept outside model-generated code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


AUTHORITY_ORDER = {"none": 0, "sandbox": 1, "user_confirmed": 2, "elevated": 3}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class PolicyDenied(PermissionError):
    pass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False


class AuthorityPolicy:
    """Deterministic policy; model output cannot increase authority."""

    def __init__(self, *, authority: str = "sandbox", approved_risks: set[str] | frozenset[str] = frozenset(), max_risk: str = "medium") -> None:
        if authority not in AUTHORITY_ORDER or max_risk not in RISK_ORDER:
            raise ValueError("unknown authority or risk level")
        self.authority = authority
        self.approved_risks = frozenset(approved_risks)
        self.max_risk = max_risk

    def decide(self, *, tool_name: str, risk: str, required_authority: str) -> PolicyDecision:
        if risk not in RISK_ORDER or required_authority not in AUTHORITY_ORDER:
            return PolicyDecision(False, "malformed policy metadata")
        if RISK_ORDER[risk] > RISK_ORDER[self.max_risk] and risk not in self.approved_risks:
            return PolicyDecision(False, f"risk {risk} exceeds policy maximum {self.max_risk}", risk in {"high", "critical"})
        if AUTHORITY_ORDER[self.authority] < AUTHORITY_ORDER[required_authority]:
            return PolicyDecision(False, f"authority {self.authority} is insufficient for {tool_name}", required_authority != "none")
        if risk in {"high", "critical"} and risk not in self.approved_risks:
            return PolicyDecision(False, f"approval required for {risk}-risk tool {tool_name}", True)
        return PolicyDecision(True, "policy permits action")
