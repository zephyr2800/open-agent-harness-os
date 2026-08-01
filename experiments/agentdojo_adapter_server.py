"""OpenAI-compatible, loopback-only bridge for native AgentDojo evaluations.

AgentDojo speaks OpenAI Chat Completions with native function calls while the
local policy emits Action IR.  This adapter preserves that boundary without
claiming that a translated run is a model-only result: every local record
contains the harness variant, repair setting, and evidence-first setting.

The module deliberately has no AgentDojo dependency.  Install and pin the
official benchmark separately, then point it at this local endpoint.  That
keeps the benchmark environment and its native grader authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping

from adapters.base import ModelRequest
from adapters.project1_transformers import Project1TransformersAdapter


REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AdapterConfig:
    """Explicit configuration recorded with every adapter decision."""

    project1_root: Path
    harness_root: Path
    model_checkpoint: str
    model_revision: str
    host: str
    port: int
    log_path: Path
    max_new_tokens: int
    seed: int
    quantization: str | None
    compact_tool_catalog: bool
    compact_context: bool
    enable_repair: bool
    enable_evidence_first_guard: bool
    harness_variant: str


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif item.get("type") == "image_url":
                    parts.append("[image omitted]")
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _message_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)
    if hasattr(message, "model_dump"):
        value = message.model_dump()
        return dict(value) if isinstance(value, Mapping) else {}
    try:
        value = dict(message)
    except (TypeError, ValueError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _tool_catalog(tools: Any, *, compact: bool) -> tuple[list[str], str]:
    """Return native tool names and a prompt-safe catalog representation."""

    names: list[str] = []
    descriptions: list[dict[str, Any]] = []
    if not isinstance(tools, list):
        return names, "[]"
    for raw_item in tools:
        item = _message_dict(raw_item)
        function = _message_dict(item.get("function"))
        name = function.get("name")
        if not isinstance(name, str) or not name:
            continue
        names.append(name)
        parameters = function.get("parameters", {})
        if compact and isinstance(parameters, Mapping):
            properties = parameters.get("properties", {})
            compact_properties: dict[str, Any] = {}
            if isinstance(properties, Mapping):
                for property_name, raw_schema in properties.items():
                    schema = _message_dict(raw_schema)
                    reduced: dict[str, Any] = {}
                    if isinstance(schema.get("type"), str):
                        reduced["type"] = schema["type"]
                    if isinstance(schema.get("enum"), list):
                        reduced["enum"] = schema["enum"]
                    compact_properties[str(property_name)] = reduced
            descriptions.append(
                {
                    "name": name,
                    "parameters": {
                        "required": list(parameters.get("required", [])),
                        "properties": compact_properties,
                    },
                }
            )
        else:
            descriptions.append(
                {
                    "name": name,
                    "description": function.get("description", ""),
                    "parameters": parameters,
                }
            )
    return list(dict.fromkeys(names)), json.dumps(descriptions, ensure_ascii=False, sort_keys=True)


def _history(
    messages: list[dict[str, Any]], *, compact_context: bool
) -> tuple[list[str], list[dict[str, Any]], list[str], dict[str, str]]:
    """Convert native tool history into provenance-tagged, untrusted evidence."""

    executed: list[str] = []
    evidence: list[dict[str, Any]] = []
    untrusted: list[str] = []
    call_names: dict[str, str] = {}
    evidence_index = 0
    limit = 3_000 if compact_context else 12_000
    for message in messages:
        role = message.get("role")
        if role == "assistant":
            calls = message.get("tool_calls")
            for raw_call in calls if isinstance(calls, list) else []:
                call = _message_dict(raw_call)
                call_id = str(call.get("id") or f"unknown-call-{len(call_names)}")
                function = _message_dict(call.get("function"))
                name = function.get("name")
                if isinstance(name, str) and name:
                    executed.append(name)
                    call_names[call_id] = name
        elif role == "tool":
            call_id = str(message.get("tool_call_id") or f"tool-result-{evidence_index}")
            name = str(message.get("name") or call_names.get(call_id) or "unknown_tool")
            raw = _content_text(message.get("content"))
            if len(raw) > limit:
                if compact_context:
                    half = max(1, (limit - 32) // 2)
                    raw = raw[:half] + "...[head-tail-truncated]..." + raw[-half:]
                else:
                    raw = raw[:limit] + "...[truncated]"
            evidence_id = f"agentdojo-evidence-{evidence_index}"
            evidence_index += 1
            evidence.append(
                {
                    "evidence_id": evidence_id,
                    "status": "verified",
                    "source": "agentdojo-native-tool-result",
                    "tool": name,
                    "tool_call_id": call_id,
                    "summary": raw[:2_000],
                }
            )
            # Tool output may contain prompt injection.  Its provenance is
            # known, but its instructions never confer model authority.
            untrusted.append(f"UNTRUSTED_TOOL_OUTPUT[{name}][{call_id}]={raw}")
    return executed, evidence, untrusted, call_names


def _goal(messages: list[dict[str, Any]], catalog: str) -> str:
    parts: list[str] = []
    for message in messages:
        if message.get("role") not in {"system", "user"}:
            continue
        text = _content_text(message.get("content"))
        if text:
            parts.append(f"{str(message.get('role')).upper()}: {text}")
    parts.append("NATIVE_TOOL_CATALOG_JSON=" + catalog)
    return "\n\n".join(parts)


def _user_goal(messages: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        _content_text(message.get("content"))
        for message in messages
        if message.get("role") == "user" and _content_text(message.get("content"))
    )


def _request_id(messages: list[dict[str, Any]]) -> str:
    seed = "\n".join(
        _content_text(message.get("content"))
        for message in messages
        if message.get("role") in {"system", "user"}
    )
    return "agentdojo-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _query_from_email_goal(goal: str) -> str:
    patterns = (
        r"\b(?:about|regarding)\s+(?:the\s+)?([a-z][a-z0-9 -]{2,48}?)(?=\s+(?:with|based|from|on|and)\b|[.,]|$)",
        r"\bfor\s+(?:the\s+)?([a-z][a-z0-9 -]{2,48}?)(?=\s+(?:with|based|from|on|and)\b|[.,]|$)",
        r"\bthe\s+([a-z][a-z0-9 -]{2,40}?)(?=\s+(?:with|based|from|on|and)\b|[.,]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, goal, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _evidence_first_guard(
    user_goal: str,
    tool_names: list[str],
    decision: Mapping[str, Any] | None,
    task_id: str,
    step: int,
    evidence_count: int,
) -> dict[str, Any] | None:
    """Narrow, opt-in guard for email-derived consequential actions.

    It is intentionally a harness ablation, never a hidden default.  It only
    chooses the registered `search_emails` lookup when a task explicitly asks
    for an action based on email evidence and none has been observed.
    """

    lower = user_goal.lower()
    if evidence_count or "email" not in lower or "search_emails" not in tool_names:
        return None
    dependent = any(
        phrase in lower
        for phrase in ("based on", "from the email", "from emails", "based on the emails")
    )
    if not dependent:
        return None
    action = decision.get("action") if isinstance(decision, Mapping) and decision.get("kind") == "act" else {}
    intent = action.get("intent") if isinstance(action, Mapping) else None
    consequential = {
        "create_calendar_event",
        "send_email",
        "create_file",
        "share_file",
        "delete_file",
        "cancel_calendar_event",
        "reschedule_calendar_event",
        "add_calendar_event_participants",
    }
    if intent == "search_emails":
        return None
    if intent not in consequential and intent not in {"search_calendar_events", "get_day_calendar_events", None}:
        return None
    return {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"step-{step}",
        "kind": "act",
        "uncertainty": {"confidence": 0.93, "basis": "evidence-first dependency guard"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        "action": {
            "intent": "search_emails",
            "arguments": {"query": _query_from_email_goal(user_goal)},
            "preconditions": [],
            "risk": "low",
            "expected_effect": "retrieve the source email before consequential execution",
            "escalate_if": ["no_matching_email", "permission_denied"],
        },
    }


class AdapterRuntime:
    """Stateful local policy runtime, deliberately separated from HTTP glue."""

    def __init__(
        self,
        config: AdapterConfig,
        *,
        policy_factory: Callable[..., Any] = Project1TransformersAdapter,
    ) -> None:
        self.config = config
        self.policy_factory = policy_factory
        self.policy: Any = None
        self.request_counter = 0
        self.log_lock = Lock()

    def _write_log(self, record: Mapping[str, Any]) -> None:
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_lock:
            with self.config.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=repr) + "\n")

    def _policy(self) -> Any:
        if self.policy is None:
            if not self.config.model_checkpoint:
                raise RuntimeError("--model-checkpoint or ACTION_MODEL_CHECKPOINT is required before serving decisions")
            self.policy = self.policy_factory(
                self.config.project1_root,
                model_id=self.config.model_checkpoint,
                revision=self.config.model_revision,
                device_map="auto",
                max_new_tokens=self.config.max_new_tokens,
                seed=self.config.seed,
                do_sample=False,
                quantization=self.config.quantization,
                stop_on_complete_json=True,
                enable_repair=self.config.enable_repair,
            )
        return self.policy

    def completion(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        raw_messages = payload.get("messages", [])
        if not isinstance(raw_messages, list):
            raise ValueError("messages must be a list")
        messages = [_message_dict(item) for item in raw_messages]
        tool_names, catalog = _tool_catalog(payload.get("tools", []), compact=self.config.compact_tool_catalog)
        task_id = _request_id(messages)
        executed, evidence, untrusted, _ = _history(messages, compact_context=self.config.compact_context)
        user_goal = _user_goal(messages)
        context = _goal(messages, catalog)
        request = ModelRequest(
            task_id=task_id,
            prompt=context,
            context=context,
            state={
                "executed_actions": executed,
                "verified_evidence": [str(item["evidence_id"]) for item in evidence],
                "evidence_records": evidence,
                "facts": untrusted,
                "assumptions": [],
                "open_questions": [],
                "available_actions": list(dict.fromkeys([*tool_names, "observe", "abstain", "finish"])),
                "authority": "sandbox",
                "harness_step": len(executed),
                "harness_variant": self.config.harness_variant,
                "untrusted_tool_outputs": untrusted,
            },
            available_actions=tuple(dict.fromkeys([*tool_names, "observe", "abstain", "finish"])),
            evidence=tuple(evidence),
            authority="sandbox",
            budget={"tokens": int(payload.get("max_tokens") or self.config.max_new_tokens), "steps": 20},
            variant=self.config.harness_variant,
            step=len(executed),
            available_tools=tuple(tool_names),
        )
        self.request_counter += 1
        policy = None
        guard_decision: dict[str, Any] | None = None
        started = time.perf_counter()
        try:
            policy = self._policy()
            try:
                decision = dict(policy.decide(request))
            except Exception:
                if not self.config.enable_evidence_first_guard:
                    raise
                guard_decision = _evidence_first_guard(
                    user_goal, tool_names, None, task_id, len(executed), len(evidence)
                )
                if guard_decision is None:
                    raise
                decision = guard_decision
            else:
                if self.config.enable_evidence_first_guard:
                    guard_decision = _evidence_first_guard(
                        user_goal, tool_names, decision, task_id, len(executed), len(evidence)
                    )
                    if guard_decision is not None:
                        decision = guard_decision
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            self._write_log(
                {
                    "schema": "agentdojo-adapter-record/v1",
                    "request_index": self.request_counter,
                    "task_id": task_id,
                    "request": dict(payload),
                    "action_ir": decision,
                    "adapter_guard": "evidence_first_dependency_guard" if guard_decision else None,
                    "elapsed_ms": elapsed_ms,
                    "model_checkpoint": self.config.model_checkpoint,
                    "model_revision": self.config.model_revision,
                    "harness_variant": self.config.harness_variant,
                    "enable_repair": self.config.enable_repair,
                    "enable_evidence_first_guard": self.config.enable_evidence_first_guard,
                    "raw_model_output": getattr(getattr(policy, "policy", None), "last_raw_text", None),
                }
            )
        except Exception as exc:
            self._write_log(
                {
                    "schema": "agentdojo-adapter-record/v1",
                    "request_index": self.request_counter,
                    "task_id": task_id,
                    "request": dict(payload),
                    "error": repr(exc),
                    "model_checkpoint": self.config.model_checkpoint,
                    "harness_variant": self.config.harness_variant,
                }
            )
            raise

        message: dict[str, Any] = {"role": "assistant", "content": None}
        finish_reason = "stop"
        kind = decision.get("kind")
        if kind == "act":
            action = decision.get("action") or {}
            intent = action.get("intent") if isinstance(action, Mapping) else None
            arguments = action.get("arguments") if isinstance(action, Mapping) else None
            if isinstance(intent, str) and intent in tool_names and isinstance(arguments, Mapping):
                message["tool_calls"] = [
                    {
                        "id": f"call-local-{self.request_counter}",
                        "type": "function",
                        "function": {"name": intent, "arguments": json.dumps(dict(arguments), ensure_ascii=False)},
                    }
                ]
                finish_reason = "tool_calls"
            else:
                message["content"] = json.dumps({"action_ir": decision}, ensure_ascii=False)
        elif kind == "finish":
            message["content"] = str((decision.get("finish") or {}).get("result") or "finished")
        elif kind == "abstain":
            message["content"] = str((decision.get("abstention") or {}).get("reason") or "abstained")
        elif kind == "observe":
            message["content"] = str((decision.get("observation") or {}).get("request") or "observation requested")
        else:
            message["content"] = json.dumps({"error": "invalid Action IR kind", "action_ir": decision})
        return {
            "id": f"chatcmpl-local-action-{self.request_counter}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": str(payload.get("model") or "local-action-policy"),
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


class Handler(BaseHTTPRequestHandler):
    """Minimal endpoint compatible with the AgentDojo OpenAI client."""

    protocol_version = "HTTP/1.1"
    runtime: AdapterRuntime | None = None

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: Mapping[str, Any]) -> None:
        raw = json.dumps(dict(body), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        runtime = self.runtime
        if self.path == "/health" and runtime is not None:
            self._send(
                200,
                {
                    "status": "ok",
                    "model_checkpoint_configured": bool(runtime.config.model_checkpoint),
                    "model_loaded": runtime.policy is not None,
                    "harness_variant": runtime.config.harness_variant,
                },
            )
            return
        if self.path.rstrip("/") == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": "local-action-policy", "object": "model", "owned_by": "local"}]})
            return
        self._send(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:  # noqa: N802
        runtime = self.runtime
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send(404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        if runtime is None:
            self._send(503, {"error": {"message": "adapter is not configured", "type": "server_error"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("request body must be a JSON object")
            self._send(200, runtime.completion(payload))
        except Exception:
            self._send(500, {"error": {"message": "adapter execution failed; inspect the configured local log", "type": "server_error"}})


def build_config(argv: list[str] | None = None) -> AdapterConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-checkpoint", default=os.environ.get("ACTION_MODEL_CHECKPOINT", ""))
    parser.add_argument("--model-revision", default=os.environ.get("ACTION_MODEL_REVISION", "main"))
    parser.add_argument("--project1-root", default=os.environ.get("ACTION_MODEL_ROOT", str(REPO_ROOT / "projects" / "local-action-model")))
    parser.add_argument("--harness-root", default=os.environ.get("HARNESS_ROOT", str(REPO_ROOT)))
    parser.add_argument("--host", default=os.environ.get("AGENTDOJO_ADAPTER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AGENTDOJO_ADAPTER_PORT", "8089")))
    parser.add_argument("--log", default=os.environ.get("AGENTDOJO_ADAPTER_LOG", str(REPO_ROOT / "work" / "external" / "agentdojo-adapter.jsonl")))
    parser.add_argument("--max-new-tokens", type=int, default=int(os.environ.get("ACTION_MODEL_MAX_NEW_TOKENS", "256")))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("ACTION_MODEL_SEED", "0")))
    parser.add_argument("--quantization", default=os.environ.get("ACTION_MODEL_QUANTIZATION") or None)
    parser.add_argument("--compact-tool-catalog", action=argparse.BooleanOptionalAction, default=_env_flag("ACTION_MODEL_COMPACT_TOOL_CATALOG"))
    parser.add_argument("--compact-context", action=argparse.BooleanOptionalAction, default=_env_flag("ACTION_MODEL_COMPACT_CONTEXT"))
    parser.add_argument("--enable-repair", action=argparse.BooleanOptionalAction, default=_env_flag("ACTION_MODEL_ENABLE_REPAIR"))
    parser.add_argument("--enable-evidence-first-guard", action=argparse.BooleanOptionalAction, default=_env_flag("ACTION_MODEL_ENABLE_EVIDENCE_FIRST_GUARD"))
    parser.add_argument("--harness-variant", default=os.environ.get("AGENTDOJO_HARNESS_VARIANT", "H3-agentdojo-openai-compat"))
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error("the AgentDojo adapter is loopback-only; use 127.0.0.1, ::1, or localhost")
    return AdapterConfig(
        project1_root=Path(args.project1_root).expanduser().resolve(),
        harness_root=Path(args.harness_root).expanduser().resolve(),
        model_checkpoint=str(args.model_checkpoint),
        model_revision=str(args.model_revision),
        host=str(args.host),
        port=int(args.port),
        log_path=Path(args.log).expanduser().resolve(),
        max_new_tokens=int(args.max_new_tokens),
        seed=int(args.seed),
        quantization=str(args.quantization) if args.quantization else None,
        compact_tool_catalog=bool(args.compact_tool_catalog),
        compact_context=bool(args.compact_context),
        enable_repair=bool(args.enable_repair),
        enable_evidence_first_guard=bool(args.enable_evidence_first_guard),
        harness_variant=str(args.harness_variant),
    )


def main(argv: list[str] | None = None) -> int:
    config = build_config(argv)
    Handler.runtime = AdapterRuntime(config)
    server = ThreadingHTTPServer((config.host, config.port), Handler)
    print(json.dumps({"status": "listening", "host": config.host, "port": config.port, "harness_variant": config.harness_variant}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
