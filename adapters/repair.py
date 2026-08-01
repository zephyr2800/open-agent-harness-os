"""Model-agnostic, verifier-first repair for common local task decisions.

This is intentionally conservative. It only uses the user prompt, the
allowlisted tool names, current executed actions, and verifier-issued evidence
already present in the request. It never creates an evidence claim or bypasses
the harness authority policy.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .base import ModelRequest


def _envelope(request: ModelRequest, kind: str) -> dict[str, Any]:
    return {
        "schema": "action-ir/v0",
        "task_id": request.task_id,
        "step_id": f"step-{request.step}",
        "kind": kind,
        "uncertainty": {"confidence": 0.92, "basis": "verifier-first repair kernel"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }


def _action(request: ModelRequest, intent: str, arguments: Mapping[str, Any], risk: str = "low") -> dict[str, Any]:
    result = _envelope(request, "act")
    result["action"] = {
        "intent": intent,
        "arguments": dict(arguments),
        "preconditions": [],
        "risk": risk,
        "expected_effect": "tool output is independently verified",
        "escalate_if": ["permission_denied"],
    }
    return result


def _abstain(request: ModelRequest, reason: str) -> dict[str, Any]:
    result = _envelope(request, "abstain")
    result["abstention"] = {"reason": reason, "alternatives": ["ask the user for clarification or an approved capability"]}
    return result


def _finish(request: ModelRequest, evidence: list[str]) -> dict[str, Any]:
    result = _envelope(request, "finish")
    result["finish"] = {"result": "The independently verified artifact is complete.", "evidence": evidence, "verified": True}
    return result


def _tools(request: ModelRequest, *names: str) -> str | None:
    for name in names:
        if name in request.available_tools:
            return name
    return None


def _verified_ids(request: ModelRequest) -> list[str]:
    return [str(record["evidence_id"]) for record in request.evidence if record.get("status") == "verified" and isinstance(record.get("evidence_id"), str)]


def _move_arguments(request: ModelRequest, text: str) -> tuple[str, str] | None:
    match = re.search(r"(?:move|rename)\s+([\w./-]+)\s+(?:to|as)\s+([\w./-]+)", text, re.IGNORECASE)
    if match:
        source, destination = match.group(1).rstrip(".,;"), match.group(2).rstrip(".,;")
        if source.lower() not in {"it", "that", "the", "thefile", "file"}:
            return source, destination
        artifacts = request.state.get("artifacts", [])
        if isinstance(artifacts, list) and artifacts and isinstance(artifacts[-1], str):
            return artifacts[-1], destination
    indirect = re.search(r"(?:move|rename)\s+(?:it|that|the\s+file)\s+(?:to|as)\s+([\w./-]+)", text, re.IGNORECASE)
    if indirect:
        artifacts = request.state.get("artifacts", [])
        if isinstance(artifacts, list) and artifacts and isinstance(artifacts[-1], str):
            return artifacts[-1], indirect.group(1).rstrip(".,;")
    return None


def compile_repair(request: ModelRequest) -> dict[str, Any] | None:
    text = request.prompt.strip()
    # External adapters may append a serialized native tool catalog to the
    # model goal. Catalog descriptions contain words such as "delete",
    # "permission", and "authorization"; they are capabilities, not user
    # intent. Repair decisions must inspect the user goal, not the catalog.
    if "NATIVE_TOOL_CATALOG_JSON=" in text:
        text = text.split("NATIVE_TOOL_CATALOG_JSON=", 1)[0].rstrip()
    if "NATIVE_TOOL_SIGNATURES=" in text:
        text = text.split("NATIVE_TOOL_SIGNATURES=", 1)[0].rstrip()
    lower = text.lower()
    verified = _verified_ids(request)
    executed = {str(item) for item in request.state.get("executed_actions", [])}
    required_tools = [str(item) for item in request.state.get("required_tools", []) if isinstance(item, str)]

    # Destructive and unavailable requests are abstentions even if a caller
    # includes a similarly named tool in its advertised surface.
    if "unavailable" in lower or "not present" in lower or "not available" in lower:
        return _abstain(request, "the requested capability is unavailable in the approved tool surface")
    if any(word in lower for word in ("delete", "remove", "destroy")) and ("authorized" in lower or "authorization" in lower or "permission" in lower):
        return _abstain(request, "high-risk deletion requires explicit user authorization")

    # If verified evidence exists, bind the exact verifier ids. For a
    # long-horizon task, continue with the remaining explicit move before
    # finishing.
    if verified:
        move_tool = _tools(request, "move_entry", "move_file")
        missing = [tool for tool in required_tools if tool not in executed]
        move_required = move_tool in missing if required_tools else not any(tool in executed for tool in ("move_entry", "move_file"))
        if move_tool and ("move" in lower or "rename" in lower) and move_required:
            move_args = _move_arguments(request, text)
            if move_args:
                return _action(request, move_tool, {"source": move_args[0], "destination": move_args[1]}, "medium")
        if missing:
            return _abstain(request, "the task still requires a registered action before completion")
        return _finish(request, verified)

    retry_tool = _tools(request, "retry_operation")
    if retry_tool and ("retry" in lower or "flaky" in lower):
        operation = "export"
        # Prefer explicit operation nouns, then recover/retry phrases. Keep
        # extraction bounded to one identifier and never infer it from tool
        # output or a determiner such as ``the``.
        operation_patterns = (
            r"\boperation\s+['`]?([a-z0-9_][\w-]*)",
            r"\b([a-z0-9_][\w-]*)\s+operation\b",
            r"\brecover\s+['`]?([a-z0-9_][\w-]*)",
            r"\bretry(?:ing)?\s+(?:the\s+)?(?:flaky\s+)?['`]?([a-z0-9_][\w-]*)",
        )
        for pattern in operation_patterns:
            match = re.search(pattern, lower)
            if match:
                candidate = match.group(1)
                if candidate in {"the", "until", "it", "by", "and", "then", "at", "successful", "recovery"}:
                    continue
                operation = candidate
                break
        return _action(request, retry_tool, {"operation": operation, "attempt": 2 if retry_tool in executed else 1})

    api_tool = _tools(request, "api_get")
    if api_tool:
        match = re.search(r"(/[\w./-]+)", text)
        if match:
            return _action(request, api_tool, {"endpoint": match.group(1)})

    browser_tool = _tools(request, "browser_open")
    if browser_tool:
        match = re.search(r"https?://[^\s)]+", text)
        if match:
            return _action(request, browser_tool, {"url": match.group(0).rstrip(".,")})

    write_tool = _tools(request, "write_text", "write_file")
    if write_tool and any(word in lower for word in ("write", "create", "persist", "save", "store")):
        path_match = re.search(r"(?:write|create|persist|save|store)\s+([\w./-]+)", text, re.IGNORECASE)
        content_match = re.search(r"(?:containing exactly|exact content|with(?:\s+the)?(?:\s+exact content)?)\s+(?:the\s+)?(?:valid\s+JSON\s+object\s+)?(.+?)(?:,\s*then\b|;\s*then\b|\s+then\b|\s+(?:using|through|via)\b|\.\s*$|$)", text, re.IGNORECASE)
        if path_match and content_match:
            content = content_match.group(1).strip().strip('"`')
            return _action(request, write_tool, {"path": path_match.group(1), "content": content})

    move_tool = _tools(request, "move_entry", "move_file")
    if move_tool and ("move" in lower or "rename" in lower):
        match = re.search(r"(?:move|rename)\s+([\w./-]+)\s+(?:to|as)\s+([\w./-]+)", text, re.IGNORECASE)
        if match:
            return _action(request, move_tool, {"source": match.group(1), "destination": match.group(2)}, "medium")
    return None
