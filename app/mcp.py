"""Minimal MCP stdio server for the local verification kernel.

The server exposes the harness as model-controlled MCP tools while keeping
authorization, execution, verification, and trace replay inside the runtime.
It intentionally has no network listener and uses newline-delimited JSON-RPC
messages on stdin/stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping

from app.service import run_action
from tools.memory_workspace import make_memory_registry
from traces.replay import load_jsonl


PROTOCOL_VERSION = "2025-06-18"


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _result(request_id: Any, value: Mapping[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": dict(value)}


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "harness_run",
            "description": "Run one bounded registered-tool action and return independently verified status plus a replayable trace.",
            "inputSchema": {
                "type": "object",
                "required": ["task_id", "prompt", "tool", "arguments"],
                "properties": {
                    "task_id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                    "variant": {"type": "string", "enum": ["H0", "H1", "H2", "H3", "H4"]},
                    "initial_files": {"type": "object", "additionalProperties": {"type": "string"}},
                    "max_steps": {"type": "integer", "minimum": 1, "maximum": 8},
                },
            },
        },
        {
            "name": "harness_tools",
            "description": "List registered tools, risk levels, authority requirements, schemas, and verifier metadata.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "harness_replay",
            "description": "Validate a harness JSONL trace without executing tools or calling a model.",
            "inputSchema": {"type": "object", "required": ["trace_jsonl"], "properties": {"trace_jsonl": {"type": "string"}}},
        },
    ]


def dispatch(message: Mapping[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "method is required") if "id" in message else None
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _result(request_id, {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "open-agent-harness-os", "version": "0.1.5"}})
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": _tools()})
    if method != "tools/call":
        return _error(request_id, -32601, f"method not found: {method}") if "id" in message else None
    params = message.get("params")
    if not isinstance(params, Mapping) or not isinstance(params.get("name"), str):
        return _error(request_id, -32602, "tools/call requires params.name")
    name = params["name"]
    arguments = params.get("arguments") if isinstance(params.get("arguments"), Mapping) else {}
    try:
        if name == "harness_tools":
            _, registry = make_memory_registry()
            value = {"schema": "open-agent-harness-mcp/v1", "tools": [registry.metadata(tool) for tool in registry.names()]}
        elif name == "harness_replay":
            trace = load_jsonl(str(arguments.get("trace_jsonl", "")).splitlines())
            issues = trace.validate(require_end=True)
            value = {"schema": "open-agent-harness-mcp/v1", "valid": not issues, "events": len(trace.events), "issues": issues}
        elif name == "harness_run":
            required = ("task_id", "prompt", "tool", "arguments")
            if any(field not in arguments for field in required):
                raise ValueError("harness_run requires task_id, prompt, tool, and arguments")
            value = run_action(
                str(arguments["task_id"]),
                str(arguments["prompt"]),
                str(arguments["tool"]),
                arguments["arguments"] if isinstance(arguments["arguments"], Mapping) else {},
                variant=str(arguments.get("variant", "H1")),
                initial_files=arguments.get("initial_files") if isinstance(arguments.get("initial_files"), Mapping) else None,
                max_steps=int(arguments.get("max_steps", 4)),
            )
        else:
            return _error(request_id, -32602, f"unknown harness tool: {name}")
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return _result(request_id, {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False})
    except Exception as exc:
        return _result(request_id, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True})


def serve_stdio(input_stream: Any = None, output_stream: Any = None) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for line in input_stream:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = dispatch(message)
            if response is not None:
                output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                output_stream.flush()
        except Exception as exc:
            output_stream.write(json.dumps(_error(None, -32700, f"parse error: {exc}"), separators=(",", ":")) + "\n")
            output_stream.flush()
    return 0
