from __future__ import annotations

import unittest

from adapters.base import ScriptedModel
from memory.evidence import EvidenceLedger
from runtime.executor import SandboxedExecutor
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from runtime.policy import AuthorityPolicy
from tools.memory_workspace import make_memory_registry


def act(task_id: str, intent: str, arguments: dict, step: int = 0, risk: str = "low") -> dict:
    return {
        "schema": "action-ir/v0", "task_id": task_id, "step_id": f"s{step}", "kind": "act",
        "uncertainty": {"confidence": 0.9, "basis": "test"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        "action": {"intent": intent, "arguments": arguments, "preconditions": [], "risk": risk, "expected_effect": "verified", "escalate_if": []},
    }


def finish(task_id: str, evidence: list[str], step: int = 1) -> dict:
    return {
        "schema": "action-ir/v0", "task_id": task_id, "step_id": f"s{step}", "kind": "finish",
        "uncertainty": {"confidence": 0.9, "basis": "test"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        "finish": {"result": "done", "evidence": evidence, "verified": True},
    }


class EvidenceTests(unittest.TestCase):
    def test_ledger_requires_verified_records_for_finish(self) -> None:
        ledger = EvidenceLedger()
        record = ledger.add(claim="x", evidence=["tool:x"], status="unverified", source_trace="t")
        self.assertFalse(ledger.contains_verified([record.evidence_id]))


class RuntimeTests(unittest.TestCase):
    def test_untrusted_tool_output_is_explicitly_labeled_in_context(self) -> None:
        task_id = "untrusted-output"

        class ObserveOutput:
            def __init__(self) -> None:
                self.requests = []

            def decide(self, request):
                self.requests.append(request)
                if request.evidence:
                    return finish(task_id, [request.evidence[-1]["evidence_id"]])
                return act(task_id, "api_get", {"endpoint": "/health"})

        model = ObserveOutput()
        _, registry = make_memory_registry()
        result = Harness(model, registry, config=HarnessConfig(variant="H1", include_tool_outputs=True)).run(TaskRequest(
            task_id, "Read /health", ("api_get",), expected_kind="finish", expected_tool="api_get",
            expected_arguments={"endpoint": "/health"},
        ))
        self.assertTrue(result.verified_success)
        self.assertTrue(any("UNTRUSTED_TOOL_OUTPUT" in fact for fact in model.requests[1].state["observed_facts"]))

    def test_research_condition_hides_evaluator_contract_hints(self) -> None:
        model = ScriptedModel([])
        _, registry = make_memory_registry()
        Harness(model, registry, config=HarnessConfig(variant="H3", expose_contract_hints=False)).run(TaskRequest(
            "hidden-hints", "Write x.txt", ("write_file",), expected_kind="finish", expected_tool="write_file",
            expected_arguments={"path": "x.txt", "content": "ok"},
        ))
        self.assertNotIn("expected_tool", model.requests[0].state)
        self.assertNotIn("required_tools", model.requests[0].state)

    def test_h1_runs_tool_and_requires_independent_finish_evidence(self) -> None:
        task_id = "write"
        model = ScriptedModel([act(task_id, "write_file", {"path": "x.txt", "content": "hello"})])

        class FinishFromEvidence:
            def __init__(self) -> None:
                self.requests = []

            def decide(self, request):
                self.requests.append(request)
                if request.evidence:
                    return finish(task_id, [request.evidence[-1]["evidence_id"]])
                return act(task_id, "write_file", {"path": "x.txt", "content": "hello"})

        _, registry = make_memory_registry()
        result = Harness(FinishFromEvidence(), registry, config=HarnessConfig(variant="H1", model_name="test-model")).run(TaskRequest(task_id, "write x", ("write_file",), expected_kind="finish"))
        self.assertTrue(result.protocol_valid)
        self.assertTrue(result.verified_success)
        self.assertEqual(result.trace.validate(), [])
        self.assertEqual(result.trace.events[0].payload["model_name"], "test-model")

    def test_h2_records_checkpoint_and_recovery(self) -> None:
        task_id = "retry"
        model = ScriptedModel([
            act(task_id, "retry_operation", {"operation": "export", "attempt": 1}),
            act(task_id, "retry_operation", {"operation": "export", "attempt": 2}, step=1),
        ])
        _, registry = make_memory_registry()
        result = Harness(model, registry, config=HarnessConfig(variant="H2")).run(TaskRequest(task_id, "retry", ("retry_operation",), expected_kind="finish"))
        event_types = [event.event_type for event in result.trace.events]
        self.assertIn("checkpoint", event_types)
        self.assertIn("verification", event_types)

    def test_policy_denies_high_risk_without_approval(self) -> None:
        _, registry = make_memory_registry()
        policy = AuthorityPolicy(authority="sandbox", max_risk="medium")
        executor = SandboxedExecutor(registry, policy)
        result = executor.execute(act("t", "write_file", {"path": "x", "content": "y"}, risk="high"), available_tools=("write_file",))
        self.assertEqual(result.status, "denied")

    def test_tool_registry_exposes_control_plane_metadata(self) -> None:
        _, registry = make_memory_registry()
        metadata = registry.metadata("write_file")
        self.assertEqual(metadata["version"], "1")
        self.assertEqual(metadata["schema"]["required"], ["path", "content"])
        self.assertTrue(metadata["preconditions"])

    def test_registered_high_risk_tool_requires_approval(self) -> None:
        _, registry = make_memory_registry({"temporary.txt": "remove"})
        decision = act("t", "delete_file", {"path": "temporary.txt"}, risk="high")
        denied = SandboxedExecutor(registry, AuthorityPolicy(authority="sandbox", max_risk="medium")).execute(decision, available_tools=("delete_file",))
        self.assertEqual(denied.status, "denied")
        approved = SandboxedExecutor(registry, AuthorityPolicy(authority="elevated", max_risk="high", approved_risks={"high"})).execute(decision, available_tools=("delete_file",))
        self.assertEqual(approved.status, "verified")

    def test_finish_requires_expected_arguments_and_artifact(self) -> None:
        task_id = "exact-write"

        class WrongThenFinish:
            def decide(self, request):
                if request.evidence:
                    return finish(task_id, [request.evidence[-1]["evidence_id"]])
                return act(task_id, "write_file", {"path": "x.txt", "content": "wrong"})

        _, registry = make_memory_registry()
        result = Harness(WrongThenFinish(), registry).run(TaskRequest(
            task_id,
            "Write x.txt",
            ("write_file",),
            expected_kind="finish",
            expected_tool="write_file",
            expected_arguments={"path": "x.txt", "content": "right"},
            expected_files={"x.txt": "right"},
        ))
        self.assertTrue(result.protocol_valid)
        self.assertFalse(result.verified_success)

    def test_finish_requires_evidence_grounded_result_content(self) -> None:
        task_id = "exact-answer"

        class ReadThenGenericFinish:
            def decide(self, request):
                if request.evidence:
                    return finish(task_id, [request.evidence[-1]["evidence_id"]])
                return act(task_id, "api_get", {"endpoint": "/health"})

        _, registry = make_memory_registry()
        result = Harness(ReadThenGenericFinish(), registry).run(TaskRequest(
            task_id,
            "Read /health and report status=ok",
            ("api_get",),
            expected_kind="finish",
            expected_tool="api_get",
            expected_arguments={"endpoint": "/health"},
            expected_result_contains=("status=ok",),
        ))
        self.assertTrue(result.protocol_valid)
        self.assertFalse(result.verified_success)
