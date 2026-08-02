from __future__ import annotations

import json
import unittest
from pathlib import Path

from benchmarks.generate_action_surface_stress_v1 import TASK_COUNT, render
from benchmarks.tasks import load_tasks
from experiments.data_split_audit import task_spec_sha256
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from verify.independent import verify_trace


ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "benchmarks" / "fixtures" / "task-spec-action-surface-stress-v1.json"
REGISTRATION = ROOT / "experiments" / "results" / "action-surface-stress-v1-registration.json"
TOOL_RISKS = {"move_file": "medium", "move_entry": "medium", "delete_file": "high"}


def _act(task_id: str, step: int, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"stress-{step}",
        "kind": "act",
        "uncertainty": {"confidence": 1.0, "basis": "fixture oracle"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        "action": {
            "intent": tool,
            "arguments": arguments,
            "preconditions": [],
            "risk": TOOL_RISKS.get(tool, "low"),
            "expected_effect": "verified fixture transition",
            "escalate_if": [],
        },
    }


def _finish(task_id: str, step: int, evidence: list[str], result: str) -> dict[str, object]:
    return {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"stress-{step}",
        "kind": "finish",
        "uncertainty": {"confidence": 1.0, "basis": "fixture oracle"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        "finish": {"result": result, "evidence": evidence, "verified": True},
    }


class _Oracle:
    def __init__(self, task) -> None:
        self.task = task

    def decide(self, request):
        if request.step < len(self.task.expected_actions):
            action = self.task.expected_actions[request.step]
            return _act(self.task.task_id, request.step, action["tool"], dict(action["arguments"]))
        return _finish(
            self.task.task_id,
            request.step,
            [str(item["evidence_id"]) for item in request.evidence],
            " ".join(self.task.expected_result_contains) or "completed",
        )


class ActionSurfaceStressV1Tests(unittest.TestCase):
    def test_fixture_is_deterministic_generator_output(self) -> None:
        self.assertEqual(FIXTURE.read_text(encoding="utf-8"), render())

    def test_tasks_force_five_ordered_actions_and_offer_distractors(self) -> None:
        tasks = load_tasks(FIXTURE)
        self.assertEqual(len(tasks), TASK_COUNT)
        self.assertEqual({task.split for task in tasks}, {"action_surface_stress_v1"})
        self.assertTrue(all(task.expected_kind == "finish" for task in tasks))
        self.assertTrue(all(task.adversarial and task.include_tool_outputs for task in tasks))
        self.assertTrue(all(len(task.expected_actions) == 5 for task in tasks))
        self.assertTrue(all(task.expected_files and task.expected_result_contains for task in tasks))
        self.assertTrue(all(
            len(set(task.available_tools) - {str(action["tool"]) for action in task.expected_actions}) >= 2
            for task in tasks
        ))
        self.assertTrue(all(
            marker not in task.prompt
            for task in tasks
            for marker in task.expected_result_contains
        ))

    def test_reference_trajectories_fit_the_h3_budget_and_replay_independently(self) -> None:
        for task in load_tasks(FIXTURE):
            _, registry = make_memory_registry(
                task.initial_files,
                api_records=task.api_records,
                browser_pages=task.browser_pages,
            )
            result = Harness(
                _Oracle(task),
                registry,
                config=HarnessConfig(
                    variant="H3",
                    max_steps=6,
                    expose_contract_hints=False,
                    include_tool_outputs=True,
                ),
            ).run(TaskRequest(
                task.task_id,
                task.prompt,
                task.available_tools,
                task.output_token_budget,
                task.expected_kind,
                task.expected_tool,
                task.expected_arguments,
                task.split,
                task.expected_tools,
                task.expected_actions,
                task.expected_files,
                task.expected_result_contains,
            ))
            independent = verify_trace(task, "H3", result.trace_jsonl)
            self.assertTrue(result.verified_success, task.task_id)
            self.assertTrue(independent["trace_valid"], task.task_id)
            self.assertTrue(independent["independent_success"], task.task_id)

    def test_registration_binds_the_fixture_without_local_paths_or_task_content(self) -> None:
        registration = json.loads(REGISTRATION.read_text(encoding="utf-8"))
        rendered = json.dumps(registration, sort_keys=True)
        self.assertEqual(registration["schema"], "post-freeze-diagnostic-registration/v1")
        self.assertEqual(registration["fixture"]["canonical_sha256"], task_spec_sha256(FIXTURE))
        self.assertEqual(registration["fixture"]["task_count"], TASK_COUNT)
        self.assertTrue(registration["direct_contract_isolation"]["passed"])
        self.assertTrue(registration["template_affinity"]["passed"])
        self.assertNotIn("C:\\Users\\", rendered)
        self.assertNotIn("action-surface-v1-file-custody-00", rendered)


if __name__ == "__main__":
    unittest.main()
