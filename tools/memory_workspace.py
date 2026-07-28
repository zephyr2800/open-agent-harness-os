"""Small deterministic tools used by the benchmark and safety tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.executor import ToolRegistry, ToolSpec


class ToolExecutionError(ValueError):
    pass


def _safe_path(args: Mapping[str, Any], field: str) -> str:
    value = args.get(field)
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in value.replace("\\", "/").split("/"):
        raise ToolExecutionError(f"{field} must be a relative safe path")
    return value.replace("\\", "/")


@dataclass
class InMemoryWorkspace:
    files: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)

    api_records: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "/health": {"service": "harness-demo", "status": "ok"},
        "/v1/status": {"ready": True, "version": "0"},
        # Research-v3 holdout endpoints are fixture-owned environment values,
        # not training examples. Keeping them here makes the expanded suite
        # executable while preserving value-level holdout separation.
        "/api/v3/healthcheck": {"service": "harness-demo-v3", "status": "ok"},
        "/metrics/v3": {"requests": 3, "status": "ready"},
    })
    browser_pages: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "https://example.test/status": {"title": "Harness Status", "text": "All systems operational"},
        "https://example.test/docs": {"title": "Harness Docs", "text": "Replayable local execution"},
        "https://sandbox.test/guide-v3": {"title": "Sandbox Guide v3", "text": "Bounded verified execution"},
        "https://docs.test/v3/overview": {"title": "Harness Overview v3", "text": "Independent replay and authority"},
    })

    def write_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        path = _safe_path(args, "path")
        content = args.get("content")
        if not isinstance(content, str):
            raise ToolExecutionError("content must be a string")
        self.files[path] = content
        return self._file_output(path)

    def _file_output(self, path: str) -> dict[str, Any]:
        content = self.files[path]
        return {"path": path, "sha256": hashlib.sha256(content.encode()).hexdigest(), "exists": True}

    def verify_write(self, output: Any) -> bool:
        return isinstance(output, Mapping) and output.get("path") in self.files and output.get("sha256") == hashlib.sha256(self.files[output["path"]].encode()).hexdigest() and output.get("exists") is True

    def read_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        path = _safe_path(args, "path")
        if path not in self.files:
            raise ToolExecutionError(f"file does not exist: {path}")
        content = self.files[path]
        return {"path": path, "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}

    def verify_read(self, output: Any) -> bool:
        return isinstance(output, Mapping) and output.get("path") in self.files and output.get("content") == self.files[output["path"]] and output.get("sha256") == hashlib.sha256(output["content"].encode()).hexdigest()

    def move_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        source = _safe_path(args, "source")
        destination = _safe_path(args, "destination")
        if source not in self.files:
            raise ToolExecutionError(f"file does not exist: {source}")
        if destination in self.files:
            raise ToolExecutionError(f"destination already exists: {destination}")
        self.files[destination] = self.files.pop(source)
        return {"source": source, "destination": destination, "source_exists": False, "destination_exists": True}

    def verify_move(self, output: Any) -> bool:
        return isinstance(output, Mapping) and output.get("source_exists") is False and output.get("destination_exists") is True and output.get("source") not in self.files and output.get("destination") in self.files

    def delete_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        path = _safe_path(args, "path")
        if path not in self.files:
            raise ToolExecutionError(f"file does not exist: {path}")
        content = self.files.pop(path)
        return {"path": path, "deleted": True, "sha256": hashlib.sha256(content.encode()).hexdigest()}

    def verify_delete(self, output: Any) -> bool:
        return isinstance(output, Mapping) and output.get("deleted") is True and isinstance(output.get("path"), str) and output["path"] not in self.files

    def retry_operation(self, args: Mapping[str, Any]) -> dict[str, Any]:
        operation = args.get("operation")
        attempt = args.get("attempt")
        if not isinstance(operation, str) or not operation or not isinstance(attempt, int) or attempt < 1:
            raise ToolExecutionError("operation must be a name and attempt must be positive")
        self.attempts[operation] = attempt
        return {"operation": operation, "attempt": attempt, "status": "recovered" if attempt >= 2 else "retry_requested"}

    def verify_retry(self, output: Any) -> bool:
        return isinstance(output, Mapping) and output.get("status") == "recovered" and self.attempts.get(output.get("operation")) == output.get("attempt")

    def api_get(self, args: Mapping[str, Any]) -> dict[str, Any]:
        endpoint = args.get("endpoint")
        if not isinstance(endpoint, str) or endpoint not in self.api_records:
            raise ToolExecutionError("endpoint is not in the deterministic API fixture")
        body = self.api_records[endpoint]
        return {"endpoint": endpoint, "status_code": 200, "body": json.dumps(body, sort_keys=True, separators=(",", ":"))}

    def verify_api_get(self, output: Any) -> bool:
        if not isinstance(output, Mapping):
            return False
        endpoint = output.get("endpoint")
        if not isinstance(endpoint, str) or endpoint not in self.api_records:
            return False
        expected = json.dumps(self.api_records[endpoint], sort_keys=True, separators=(",", ":"))
        return output.get("status_code") == 200 and output.get("body") == expected

    def browser_open(self, args: Mapping[str, Any]) -> dict[str, Any]:
        url = args.get("url")
        if not isinstance(url, str) or url not in self.browser_pages:
            raise ToolExecutionError("URL is not in the deterministic browser fixture")
        page = self.browser_pages[url]
        return {"url": url, "status_code": 200, "title": page["title"], "text": page["text"]}

    def verify_browser_open(self, output: Any) -> bool:
        if not isinstance(output, Mapping):
            return False
        url = output.get("url")
        page = self.browser_pages.get(url) if isinstance(url, str) else None
        return bool(page and output.get("status_code") == 200 and output.get("title") == page["title"] and output.get("text") == page["text"])


def make_memory_registry(
    initial_files: Mapping[str, str] | None = None,
    *,
    api_records: Mapping[str, Mapping[str, Any]] | None = None,
    browser_pages: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[InMemoryWorkspace, ToolRegistry]:
    workspace = InMemoryWorkspace(
        dict(initial_files or {}),
        api_records={key: dict(value) for key, value in api_records.items()} if api_records is not None else InMemoryWorkspace().api_records,
        browser_pages={key: dict(value) for key, value in browser_pages.items()} if browser_pages is not None else InMemoryWorkspace().browser_pages,
    )
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "write_file", "low", workspace.write_file, workspace.verify_write,
        "write a UTF-8 file", "sandbox", "1",
        {"type": "object", "required": ["path", "content"]},
        ({"path": "notes.txt", "content": "hello"},),
        ("path is relative and safe",), ("creates or replaces one workspace file",),
    ))
    registry.register(ToolSpec(
        "write_text", "low", workspace.write_file, workspace.verify_write,
        "write text through the renamed file tool", "sandbox", "1",
        {"type": "object", "required": ["path", "content"]},
        ({"path": "notes.txt", "content": "hello"},), ("path is relative and safe",),
        ("creates or replaces one workspace file",),
    ))
    registry.register(ToolSpec(
        "read_file", "low", workspace.read_file, workspace.verify_read,
        "read a known file", "sandbox", "1",
        {"type": "object", "required": ["path"]},
        ({"path": "STATUS.md"},), ("path exists in workspace",), ("none",),
    ))
    registry.register(ToolSpec(
        "move_entry", "medium", workspace.move_file, workspace.verify_move,
        "move a workspace entry through the renamed move tool", "sandbox", "1",
        {"type": "object", "required": ["source", "destination"]},
        ({"source": "draft.txt", "destination": "final.txt"},),
        ("source exists and destination is absent",), ("moves one workspace entry",),
    ))
    registry.register(ToolSpec(
        "move_file", "medium", workspace.move_file, workspace.verify_move,
        "move a file within the workspace", "sandbox", "1",
        {"type": "object", "required": ["source", "destination"]},
        ({"source": "draft.txt", "destination": "final.txt"},),
        ("source exists and destination is absent",), ("moves one workspace file",),
    ))
    registry.register(ToolSpec(
        "delete_file", "high", workspace.delete_file, workspace.verify_delete,
        "delete a workspace file", "elevated", "1",
        {"type": "object", "required": ["path"]},
        ({"path": "temporary.txt"},), ("path exists and user approved the high-risk action",), ("deletes one workspace file",),
    ))
    registry.register(ToolSpec(
        "retry_operation", "low", workspace.retry_operation, workspace.verify_retry,
        "retry a named operation", "sandbox", "1",
        {"type": "object", "required": ["operation", "attempt"]},
        ({"operation": "export", "attempt": 2},), ("attempt is positive",), ("updates retry state",),
    ))
    registry.register(ToolSpec(
        "api_get", "low", workspace.api_get, workspace.verify_api_get,
        "read one response from the deterministic API fixture", "sandbox", "1",
        {"type": "object", "required": ["endpoint"]},
        ({"endpoint": "/health"},), ("endpoint is allowlisted",), ("no local state mutation",),
    ))
    registry.register(ToolSpec(
        "browser_open", "low", workspace.browser_open, workspace.verify_browser_open,
        "open one page from the deterministic browser fixture", "sandbox", "1",
        {"type": "object", "required": ["url"]},
        ({"url": "https://example.test/status"},), ("URL is allowlisted",), ("no network access",),
    ))
    registry.set_snapshot_reader(lambda: {"files": dict(workspace.files), "attempts": dict(workspace.attempts)})
    return workspace, registry
