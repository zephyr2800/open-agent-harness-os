from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from adapters.base import ModelRequest
from protocol.events import Trace, TraceFormatError
from protocol.ir import ActionValidationError, require_valid_decision
from traces.recorder import TraceRecorder
from adapters.http import LocalModelHTTPError, OpenAICompatibleAdapter


def valid_decision(task_id: str = "t1", kind: str = "abstain") -> dict:
    value = {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": "s1",
        "kind": kind,
        "uncertainty": {"confidence": 0.5, "basis": "test"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if kind == "abstain":
        value["abstention"] = {"reason": "safe stop", "alternatives": ["ask"]}
    return value


class ProtocolTests(unittest.TestCase):
    def test_project1_action_ir_shape_is_accepted(self) -> None:
        self.assertEqual(require_valid_decision(valid_decision())["schema"], "action-ir/v0")

    def test_malformed_action_ir_is_rejected(self) -> None:
        with self.assertRaises(ActionValidationError):
            require_valid_decision({"kind": "act"})

    def test_trace_parent_digest_detects_tampering(self) -> None:
        trace = Trace("t1")
        trace.append("decision_request", {"state_digest": "a"})
        trace.append("trajectory_end", {"verified_success": False})
        values = trace.as_dicts()
        values[0]["payload"]["state_digest"] = "tampered"
        with self.assertRaises(TraceFormatError):
            Trace.from_events(values)

    def test_trace_rejects_schema_or_first_parent_tampering(self) -> None:
        trace = Trace("t1")
        trace.append("trajectory_end", {"verified_success": False})
        values = trace.as_dicts()
        values[0]["schema"] = "wrong/v0"
        with self.assertRaises(TraceFormatError):
            Trace.from_events(values)
        values = trace.as_dicts()
        values[0]["parent_digest"] = "sha256:forged"
        with self.assertRaises(TraceFormatError):
            Trace.from_events(values)

    def test_trace_redacts_secret_values(self) -> None:
        recorder = TraceRecorder("t1")
        recorder.record("observation", {"text": "api_key=super-secret"})
        self.assertIn("[REDACTED]", recorder.jsonl())
        self.assertNotIn("super-secret", recorder.jsonl())

    def test_local_adapter_parses_json_and_rejects_non_json(self) -> None:
        parsed = OpenAICompatibleAdapter.parse_content("```json\n{" + '"schema":"action-ir/v0"' + "}\n```")
        self.assertEqual(parsed["schema"], "action-ir/v0")
        with self.assertRaises(LocalModelHTTPError):
            OpenAICompatibleAdapter.parse_content("not-json")

    def test_local_adapter_caps_socket_timeout_to_request_budget(self) -> None:
        seen: dict[str, float] = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": json.dumps(valid_decision("t1"))}}]}).encode()

        def fake_urlopen(request, timeout):
            seen["timeout"] = timeout
            return Response()

        request = ModelRequest("t1", "prompt", "context", {}, ("abstain",), (), "sandbox", {"tokens": 64, "seconds": 2}, "H1", 0)
        adapter = OpenAICompatibleAdapter("http://127.0.0.1:1", "test-model", timeout_seconds=30)
        with patch("urllib.request.urlopen", fake_urlopen):
            self.assertEqual(adapter.decide(request)["task_id"], "t1")
        self.assertEqual(seen["timeout"], 2.0)
