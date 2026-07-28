"""Model-agnostic execution loop for H0 through H4."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from adapters.base import ModelAdapter, ModelRequest
from memory.evidence import EvidenceLedger
from protocol.digest import sha256_digest
from protocol.events import Trace
from protocol.ir import require_valid_decision
from runtime.checkpoint import CheckpointManager
from runtime.context import ContextCompiler
from runtime.executor import ExecutionResult, SandboxedExecutor, ToolRegistry
from runtime.policy import AuthorityPolicy
from runtime.recovery import RecoveryManager
from runtime.state import HarnessState
from search.branch import BranchCandidate, BranchSearch
from traces.recorder import TraceRecorder
from improve.promotion import PromotionGate, Proposal, ProposalResult


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    prompt: str
    available_tools: tuple[str, ...]
    output_token_budget: int = 1800
    expected_kind: str | None = None
    expected_tool: str | None = None
    expected_arguments: Mapping[str, Any] | None = None
    split: str = "held_out"
    expected_tools: tuple[str, ...] = ()
    expected_actions: tuple[Mapping[str, Any], ...] = ()
    expected_files: Mapping[str, str] | None = None
    expected_result_contains: tuple[str, ...] = ()


@dataclass(frozen=True)
class HarnessConfig:
    variant: str = "H1"
    model_name: str = "unspecified"
    max_steps: int = 6
    authority: str = "sandbox"
    max_risk: str = "medium"
    approved_risks: frozenset[str] = frozenset()
    timeout_seconds: float = 5.0
    token_budget: int = 1800
    expose_contract_hints: bool = True
    include_tool_outputs: bool = False

    def __post_init__(self) -> None:
        if self.variant not in {"H0", "H1", "H2", "H3", "H4"}:
            raise ValueError("variant must be H0, H1, H2, H3, or H4")


@dataclass(frozen=True)
class RunResult:
    task_id: str
    variant: str
    protocol_valid: bool
    verified_success: bool
    abstained: bool
    steps: int
    state: HarnessState
    trace: Trace
    evidence: tuple[Mapping[str, Any], ...]
    metrics: Mapping[str, float]
    error: str | None = None

    @property
    def trace_jsonl(self) -> str:
        return self.trace.to_jsonl()


class Harness:
    """The harness owns execution, verification, and authority decisions."""

    def __init__(self, model: ModelAdapter, registry: ToolRegistry, *, config: HarnessConfig | None = None) -> None:
        self.model = model
        self.registry = registry
        self.config = config or HarnessConfig()
        # H0 is intentionally a weak control: it uses a permissive policy but
        # still only exposes registered tools, so the comparison remains safe.
        policy = AuthorityPolicy(
            authority="elevated" if self.config.variant == "H0" else self.config.authority,
            approved_risks=frozenset({"high", "critical"}) if self.config.variant == "H0" else self.config.approved_risks,
            max_risk="critical" if self.config.variant == "H0" else self.config.max_risk,
        )
        self.executor = SandboxedExecutor(registry, policy, timeout_seconds=self.config.timeout_seconds)
        self.context = ContextCompiler(token_budget=self.config.token_budget)
        self.recovery = RecoveryManager()
        self.branch_search = BranchSearch()
        self.promotion_gate = PromotionGate() if self.config.variant == "H4" else None

    def evaluate_proposal(self, proposal: Proposal, *, held_in, held_out, canary=None) -> ProposalResult:
        """Evaluate one bounded H4 proposal; protected surfaces stay immutable."""

        if self.promotion_gate is None:
            raise RuntimeError("proposal evaluation is only enabled for H4")
        return self.promotion_gate.evaluate(proposal, held_in=held_in, held_out=held_out, canary=canary)

    def _context(self, task: TaskRequest, state: HarnessState, ledger: EvidenceLedger, transcript: list[str], step: int):
        if self.config.variant == "H0":
            text = f"TASK: {task.prompt}\n" + "\n".join(transcript[-4:])
            from runtime.context import ContextBundle

            return ContextBundle(text, (text,), max(1, (len(text) + 3) // 4), ("transcript",))
        return self.context.compile(
            prompt=task.prompt,
            state=state,
            evidence=ledger,
            tool_descriptions=self.registry.descriptions(),
            available_tools=task.available_tools,
            transcript=transcript,
            progressive=self.config.variant in {"H2", "H3", "H4"},
            relevant_query=task.prompt,
        )

    def run(self, task: TaskRequest) -> RunResult:
        state = HarnessState(task.task_id, claims=(task.prompt,), authority=self.config.authority)
        recorder = TraceRecorder(task.task_id)
        ledger = EvidenceLedger()
        checkpoints = CheckpointManager()
        transcript: list[str] = []
        protocol_valid = True
        verified_success = False
        abstained = False
        error: str | None = None
        total_output_tokens = 0
        total_tool_ms = 0.0
        action_history: list[dict[str, Any]] = []
        required_tools = tuple(task.expected_tools or tuple(str(item.get("tool")) for item in task.expected_actions))

        step_budget = 1 if self.config.variant == "H0" else self.config.max_steps
        for step in range(step_budget):
            bundle = self._context(task, state, ledger, transcript, step)
            available_actions = tuple(dict.fromkeys((*task.available_tools, "observe", "abstain", "finish")))
            model_state = dict(state.as_dict())
            if self.config.expose_contract_hints:
                # These evaluator-owned hints are useful for the repair/product
                # condition, but research model-only runs can hide them to
                # prevent the evaluator from leaking the expected action.
                model_state.update({
                    "required_tools": list(required_tools),
                    "expected_tool": task.expected_tool,
                })
            request = ModelRequest(
                task_id=task.task_id,
                prompt=task.prompt,
                context=bundle.text,
                state=model_state,
                available_actions=available_actions,
                evidence=tuple(record.as_dict() for record in ledger.all()),
                authority=state.authority,
                budget={"tokens": max(0, task.output_token_budget - total_output_tokens), "seconds": int(self.config.timeout_seconds)},
                variant=self.config.variant,
                step=step,
                available_tools=task.available_tools,
            )
            recorder.record("decision_request", {"model_name": self.config.model_name, "harness_variant": self.config.variant, "state_digest": state.digest(), "available_actions": list(available_actions), "context_provenance": list(bundle.provenance), "context_tokens": bundle.estimated_tokens, "budget": dict(request.budget)})
            try:
                decision = require_valid_decision(self.model.decide(request))
                total_output_tokens += max(1, (len(str(decision)) + 3) // 4)
            except Exception as exc:  # model/provider failures stay inside the trace boundary
                protocol_valid = False
                error = f"protocol validation failed: {exc}"
                recorder.record("decision", {"valid": False, "error": str(exc)})
                recorder.record("trajectory_end", {"reason": "protocol_error", "verified_success": False})
                break
            recorder.record("decision", {"valid": True, "decision": decision})
            transcript.append(f"step={step} kind={decision['kind']}")
            state = state.update(
                facts=decision["state_update"]["facts"],
                assumptions=decision["state_update"]["assumptions"],
                open_questions=decision["state_update"]["open_questions"],
            )
            kind = decision["kind"]
            if kind == "act":
                result = self.executor.execute(decision, available_tools=task.available_tools)
                action_history.append({
                    "tool": result.tool,
                    "arguments": dict(decision["action"]["arguments"]),
                    "verified": bool(result.verified),
                })
                total_tool_ms += result.elapsed_ms
                recorder.record("policy_decision", {"tool": result.tool, "status": result.status, "reason": result.policy.reason if result.policy else result.error})
                recorder.record("tool_call", {"tool": result.tool, "arguments": decision["action"]["arguments"], "status": result.status, "error": result.error, "output": result.output})
                if result.output is not None:
                    recorder.record("observation", {"tool": result.tool, "output": result.output})
                evidence = ledger.add(
                    claim=f"{result.tool} execution completed",
                    evidence=[f"tool:{result.tool}", f"output:{sha256_digest(result.output)}"],
                    status="verified" if result.verified else "unverified",
                    source_trace=f"{task.task_id}:{self.config.variant}",
                )
                recorder.record("verification", {"tool": result.tool, "verified": result.verified, "evidence_id": evidence.evidence_id, "error": result.error})
                tool_facts = [f"tool {result.tool} returned {result.status}"]
                if self.config.include_tool_outputs and result.output is not None:
                    # This is intentionally labeled untrusted. It enables
                    # AgentDojo/ToolSandbox-style indirect-injection tests;
                    # the runtime verifier and authority policy remain the
                    # source of truth for success and permission.
                    tool_facts.append("UNTRUSTED_TOOL_OUTPUT=" + json.dumps(result.output, ensure_ascii=False, sort_keys=True))
                state = state.update(actions=[result.tool], facts=tool_facts, verified=[evidence.evidence_id] if result.verified else [], artifacts=[str(result.output.get("path"))] if isinstance(result.output, Mapping) and result.output.get("path") else [])
                if self.config.variant == "H0":
                    expected_tools_ok = not task.expected_tools or (len(task.expected_tools) == 1 and result.tool == task.expected_tools[0])
                    verified_success = bool(result.verified and (task.expected_tool is None or result.tool == task.expected_tool) and expected_tools_ok)
                    recorder.record("trajectory_end", {"reason": "h0_single_call", "verified_success": verified_success})
                    break
                if self.config.variant in {"H2", "H3", "H4"}:
                    checkpoint = checkpoints.save(state, len(recorder.trace.events), "post-tool")
                    selected = self.branch_search.select([] if not result.verified else [BranchCandidate(checkpoint.checkpoint_id, 1.0, True, result.elapsed_ms, checkpoint.checkpoint_id)])
                    recorder.record("checkpoint", {"checkpoint_id": checkpoint.checkpoint_id, "reason": checkpoint.reason, "state_digest": state.digest(), "selected_branch": selected.branch_id if selected else None})
                if not result.verified and result.error and self.config.variant in {"H2", "H3", "H4"}:
                    recovery = self.recovery.classify(error=result.error, attempts=step, verified=result.verified)
                    recorder.record("recovery", {"strategy": recovery.strategy, "reason": recovery.reason, "next_step": recovery.next_step})
                continue
            if kind == "observe":
                observation = decision["observation"]
                recorder.record("observation", {"request": observation["request"], "bounded_items": list(state.observed_facts[-observation["max_items"] :])})
                state = state.update(facts=[f"observed: {observation['request']}"])
                continue
            if kind == "abstain":
                abstained = True
                recorder.record("trajectory_end", {"reason": "abstain", "verified_success": task.expected_kind == "abstain"})
                verified_success = task.expected_kind == "abstain"
                break
            if kind == "finish":
                finish = decision["finish"]
                independent = ledger.contains_verified(finish["evidence"])
                expected_tools_ok = all(tool in state.executed_actions for tool in task.expected_tools)
                if task.expected_actions:
                    expected_action_contract = True
                    cursor = 0
                    for expected in task.expected_actions:
                        expected_tool = str(expected.get("tool"))
                        expected_arguments = dict(expected.get("arguments") or {})
                        match_index = next(
                            (
                                index
                                for index in range(cursor, len(action_history))
                                if action_history[index]["verified"]
                                and action_history[index]["tool"] == expected_tool
                                and action_history[index]["arguments"] == expected_arguments
                            ),
                            None,
                        )
                        if match_index is None:
                            expected_action_contract = False
                            break
                        cursor = match_index + 1
                elif task.expected_tool:
                    expected_action_contract = any(
                        item["verified"]
                        and item["tool"] == task.expected_tool
                        and (task.expected_arguments is None or item["arguments"] == dict(task.expected_arguments))
                        for item in action_history
                    )
                else:
                    expected_action_contract = True
                snapshot = self.registry.snapshot()
                expected_files_ok = True
                if task.expected_files is not None:
                    expected_files_ok = bool(snapshot is not None and all(
                        snapshot.get("files", {}).get(path) == content
                        for path, content in task.expected_files.items()
                    ))
                finish_result = str(finish.get("result", ""))
                expected_result_ok = all(marker in finish_result for marker in task.expected_result_contains)
                verified_success = bool(finish["verified"] and independent and expected_tools_ok and expected_action_contract and expected_files_ok and expected_result_ok)
                recorder.record("verification", {"finish": True, "independent_evidence": independent, "evidence_ids": finish["evidence"]})
                recorder.record("verification", {
                    "task_contract": True,
                    "expected_action_contract": expected_action_contract,
                    "expected_files": expected_files_ok,
                    "expected_tools": expected_tools_ok,
                    "expected_result": expected_result_ok,
                    "expected_result_contains": list(task.expected_result_contains),
                })
                if not independent and self.config.variant in {"H2", "H3", "H4"}:
                    # A premature finish is a recoverable model error in the
                    # advanced harness. Preserve the attempted claim in the
                    # trace, but do not terminate the run or treat it as
                    # progress. The next bounded request receives an explicit
                    # unresolved question through state, allowing a capable
                    # model to act and obtain verifier-backed evidence.
                    recorder.record("recovery", {"strategy": "repair", "reason": "finish rejected until independent verifier evidence exists", "next_step": step + 1})
                    state = state.update(open_questions=["finish rejected: independent verifier evidence is required before completion"])
                    transcript.append("finish rejected: independent verifier evidence is required")
                    error = "finish lacked independent verified evidence; recovery requested"
                    continue
                recorder.record("trajectory_end", {"reason": "finish", "verified_success": verified_success})
                if not verified_success:
                    error = "finish lacked independent verified evidence"
                break
        else:
            error = "step budget exhausted"
            recorder.record("trajectory_end", {"reason": "step_budget", "verified_success": False})
        metrics = {
            "output_tokens": float(total_output_tokens),
            "tool_time_ms": total_tool_ms,
            "context_requests": float(len(getattr(self.model, "requests", []))),
            "evidence_records": float(len(ledger.all())),
            "checkpoints": float(len(checkpoints.all())),
        }
        return RunResult(task.task_id, self.config.variant, protocol_valid, verified_success, abstained, len(recorder.trace.events), state, recorder.trace, tuple(record.as_dict() for record in ledger.all()), metrics, error)
