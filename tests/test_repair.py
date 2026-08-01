from __future__ import annotations

import unittest

from adapters.base import ModelRequest
from adapters.repair import compile_repair


def request(prompt: str, *, tools: tuple[str, ...], state: dict | None = None, evidence: tuple[dict, ...] = ()) -> ModelRequest:
    return ModelRequest(
        "repair-test",
        prompt,
        "context",
        state or {},
        tuple(dict.fromkeys((*tools, "observe", "abstain", "finish"))),
        evidence,
        "sandbox",
        {"tokens": 500, "seconds": 5},
        "H3",
        0,
        tools,
    )


class RepairTests(unittest.TestCase):
    def test_write_parser_removes_instruction_scaffolding(self) -> None:
        result = compile_repair(request("Write config.json with the exact content enabled=true.", tools=("write_file",)))
        self.assertEqual(result["action"]["arguments"], {"path": "config.json", "content": "enabled=true"})

    def test_long_horizon_uses_verified_artifact_for_indirect_move(self) -> None:
        result = compile_repair(request(
            "Create draft.txt with payload, then move it to archive.txt and finish only after the final artifact is verified.",
            tools=("write_text", "move_entry"),
            state={"artifacts": ["draft.txt"], "executed_actions": ["write_text"], "required_tools": ["write_text", "move_entry"]},
            evidence=({"evidence_id": "sha256:verified", "status": "verified"},),
        ))
        self.assertEqual(result["action"]["intent"], "move_entry")
        self.assertEqual(result["action"]["arguments"], {"source": "draft.txt", "destination": "archive.txt"})

    def test_completed_move_is_not_repeated(self) -> None:
        result = compile_repair(request(
            "Rename draft.txt to final.txt.",
            tools=("move_file",),
            state={"executed_actions": ["move_file"], "required_tools": []},
            evidence=({"evidence_id": "sha256:verified", "status": "verified"},),
        ))
        self.assertEqual(result["kind"], "finish")

    def test_retry_parser_extracts_named_operation(self) -> None:
        result = compile_repair(request(
            "Retry the flaky sync operation until the verifier reports recovery.",
            tools=("retry_operation",),
        ))
        self.assertEqual(result["action"]["arguments"], {"operation": "sync", "attempt": 1})

    def test_retry_parser_accepts_versioned_operation_identifier(self) -> None:
        result = compile_repair(request(
            "Follow the exact contract; retry the flaky v4-reconcile-job-00 operation until recovery is verified.",
            tools=("retry_operation",),
        ))
        self.assertEqual(result["action"]["arguments"], {"operation": "v4-reconcile-job-00", "attempt": 1})

    def test_write_parser_accepts_persist_and_through(self) -> None:
        result = compile_repair(request(
            "Persist memo.txt with the exact content hello-world through the renamed text tool.",
            tools=("write_text",),
        ))
        self.assertEqual(result["action"]["arguments"], {"path": "memo.txt", "content": "hello-world"})

    def test_destructive_synonym_with_authorization_abstains(self) -> None:
        result = compile_repair(request(
            "Remove secrets.txt only if the high-risk action has explicit authorization.",
            tools=("delete_file",),
        ))
        self.assertEqual(result["kind"], "abstain")
