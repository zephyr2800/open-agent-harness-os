"""Deterministic execution boundary with independent verifier callbacks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from protocol.ir import require_valid_decision
from .policy import AuthorityPolicy, PolicyDecision


Handler = Callable[[Mapping[str, Any]], Any]
Verifier = Callable[[Any], bool]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    risk: str
    handler: Handler
    verifier: Verifier
    description: str = ""
    required_authority: str = "sandbox"
    version: str = "1"
    schema: Mapping[str, Any] = field(default_factory=dict)
    examples: tuple[Mapping[str, Any], ...] = ()
    preconditions: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    rollback: Callable[[Mapping[str, Any]], Any] | None = None


@dataclass(frozen=True)
class ExecutionResult:
    tool: str
    status: str
    output: Any = None
    verified: bool = False
    policy: PolicyDecision | None = None
    error: str | None = None
    elapsed_ms: float = 0.0


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._snapshot_reader: Callable[[], Mapping[str, Any]] | None = None

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.name in self._tools:
            raise ValueError("tool names must be non-empty and unique")
        if spec.risk not in {"low", "medium", "high", "critical"}:
            raise ValueError("tool risk is invalid")
        self._tools[spec.name] = spec

    def set_snapshot_reader(self, reader: Callable[[], Mapping[str, Any]]) -> None:
        """Attach an evaluator-only state snapshot for deterministic fixtures."""

        self._snapshot_reader = reader

    def snapshot(self) -> Mapping[str, Any] | None:
        """Return benchmark state without exposing it to the model adapter."""

        return dict(self._snapshot_reader()) if self._snapshot_reader is not None else None

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def descriptions(self) -> dict[str, str]:
        return {name: spec.description for name, spec in self._tools.items()}

    def metadata(self, name: str) -> dict[str, Any]:
        spec = self._tools[name]
        return {
            "name": spec.name,
            "version": spec.version,
            "risk": spec.risk,
            "required_authority": spec.required_authority,
            "schema": dict(spec.schema),
            "examples": [dict(example) for example in spec.examples],
            "preconditions": list(spec.preconditions),
            "side_effects": list(spec.side_effects),
            "has_rollback": spec.rollback is not None,
        }


class SandboxedExecutor:
    def __init__(self, registry: ToolRegistry, policy: AuthorityPolicy, *, timeout_seconds: float = 5.0) -> None:
        self.registry = registry
        self.policy = policy
        self.timeout_seconds = timeout_seconds

    def execute(self, decision: Mapping[str, Any], *, available_tools: tuple[str, ...] = ()) -> ExecutionResult:
        require_valid_decision(dict(decision))
        if decision["kind"] != "act":
            raise ValueError("only act decisions may cross executor")
        action = decision["action"]
        name = action["intent"]
        if available_tools and name not in available_tools:
            return ExecutionResult(name, "denied", error=f"tool {name} is not available for this task")
        spec = self.registry.get(name)
        if spec is None:
            return ExecutionResult(name, "denied", error=f"tool {name} is not registered")
        if action["risk"] != spec.risk:
            return ExecutionResult(name, "denied", error=f"risk mismatch for {name}")
        policy = self.policy.decide(tool_name=name, risk=spec.risk, required_authority=spec.required_authority)
        if not policy.allowed:
            return ExecutionResult(name, "denied", policy=policy, error=policy.reason)
        import time

        started = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(spec.handler, action["arguments"])
                output = future.result(timeout=self.timeout_seconds)
            verified = bool(spec.verifier(output))
            return ExecutionResult(name, "verified" if verified else "unverified", output, verified, policy, elapsed_ms=(time.perf_counter() - started) * 1000)
        except FutureTimeout:
            return ExecutionResult(name, "error", policy=policy, error=f"tool timeout after {self.timeout_seconds}s", elapsed_ms=(time.perf_counter() - started) * 1000)
        except Exception as exc:  # boundary converts tool faults into observable state
            return ExecutionResult(name, "error", policy=policy, error=f"{type(exc).__name__}: {exc}", elapsed_ms=(time.perf_counter() - started) * 1000)
