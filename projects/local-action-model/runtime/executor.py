"""Tool registration, policy gating, and independent verification.

This module intentionally does not provide a general-purpose shell or file
writer. It defines the boundary that such tools must cross. A model can
request an intent, but only a registered tool with an explicit policy decision
may run, and a verifier must decide whether its result counts as successful.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from action_ir.validation import require_valid_decision


Handler = Callable[[Mapping[str, Any]], Any]
Verifier = Callable[[Any], bool]


class ExecutionDenied(PermissionError):
    """Raised when an action cannot cross the execution boundary."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    risk: str
    handler: Handler
    verifier: Verifier


@dataclass(frozen=True)
class ExecutionResult:
    tool: str
    status: str
    output: Any = None
    verified: bool = False
    denial_reason: str | None = None


class ToolRegistry:
    """Registry that requires explicit registration and risk approval."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.name in self._tools:
            raise ValueError("tool names must be non-empty and unique")
        if spec.risk not in {"low", "medium", "high", "critical"}:
            raise ValueError("tool risk must be low, medium, high, or critical")
        self._tools[spec.name] = spec

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def execute(self, decision: Mapping[str, Any], *, approved_risks: set[str] | frozenset[str] = frozenset()) -> ExecutionResult:
        """Execute one validated `act` decision through policy and verifier."""

        require_valid_decision(dict(decision))
        if decision["kind"] != "act":
            raise ExecutionDenied("only kind=act may be executed")
        action = decision["action"]
        name = action["intent"]
        spec = self._tools.get(name)
        if spec is None:
            raise ExecutionDenied(f"tool is not registered: {name}")
        if spec.risk != action["risk"]:
            raise ExecutionDenied(f"decision risk does not match registered tool risk for {name}")
        if spec.risk in {"high", "critical"} and spec.risk not in approved_risks:
            raise ExecutionDenied(f"approval required for {spec.risk}-risk tool: {name}")

        output = spec.handler(action["arguments"])
        verified = bool(spec.verifier(output))
        return ExecutionResult(tool=name, status="verified" if verified else "unverified", output=output, verified=verified)
