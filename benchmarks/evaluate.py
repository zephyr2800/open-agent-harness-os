"""Task-level evaluation with independent checks outside the model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from runtime.orchestrator import Harness, HarnessConfig, RunResult, TaskRequest
from tools.memory_workspace import make_memory_registry
from .tasks import Task


@dataclass(frozen=True)
class TaskOutcome:
    task_id: str
    split: str
    protocol_valid: bool
    verified_success: bool
    expected_kind: str
    kind_match: bool
    steps: int
    error: str | None
    metrics: dict[str, float]
    trace_jsonl: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Evaluation:
    variant: str
    model_name: str
    outcomes: tuple[TaskOutcome, ...]

    def summary(self) -> dict[str, float]:
        total = len(self.outcomes)
        return {
            "tasks": float(total),
            "protocol_valid_rate": sum(item.protocol_valid for item in self.outcomes) / total if total else 0.0,
            "verified_success_rate": sum(item.verified_success for item in self.outcomes) / total if total else 0.0,
            "kind_match_rate": sum(item.kind_match for item in self.outcomes) / total if total else 0.0,
            "mean_steps": sum(item.steps for item in self.outcomes) / total if total else 0.0,
        }

    def as_dict(self) -> dict[str, object]:
        return {"variant": self.variant, "model": self.model_name, "summary": self.summary(), "outcomes": [item.as_dict() for item in self.outcomes]}


def evaluate_tasks(tasks: Iterable[Task], *, model_factory: Callable[[Task, str], object], variant: str, model_name: str) -> Evaluation:
    outcomes: list[TaskOutcome] = []
    for task in tasks:
        workspace, registry = make_memory_registry(task.initial_files)
        del workspace  # state is inspected by the tool verifiers and remains in the registry closure
        model = model_factory(task, variant)
        harness = Harness(model, registry, config=HarnessConfig(variant=variant, model_name=model_name, max_steps=6))
        request = TaskRequest(
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
        )
        result: RunResult = harness.run(request)
        kind_match = (task.expected_kind == "abstain" and result.abstained) or (task.expected_kind == "finish" and result.verified_success)
        outcomes.append(TaskOutcome(task.task_id, task.split, result.protocol_valid, result.verified_success, task.expected_kind, kind_match, result.steps, result.error, dict(result.metrics), result.trace_jsonl))
    return Evaluation(variant, model_name, tuple(outcomes))
