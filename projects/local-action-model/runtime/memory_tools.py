"""Deterministic in-memory tools with independent state verifiers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from .executor import ToolRegistry, ToolSpec


class ToolExecutionError(ValueError):
    """Raised when a fixture tool receives invalid arguments or state."""


def _path(args: Mapping[str, Any], field: str) -> str:
    value = args.get(field)
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in value.split("/"):
        raise ToolExecutionError(f"{field} must be a relative safe path")
    return value.replace("\\", "/")


@dataclass
class InMemoryWorkspace:
    files: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)

    def write_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        path = _path(args, "path")
        content = args.get("content")
        if not isinstance(content, str):
            raise ToolExecutionError("content must be a string")
        self.files[path] = content
        return {"path": path, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(), "exists": True}

    def verify_write(self, output: Any) -> bool:
        return isinstance(output, dict) and output.get("exists") is True and output.get("path") in self.files and output.get("sha256") == hashlib.sha256(self.files[output["path"]].encode("utf-8")).hexdigest()

    def read_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        path = _path(args, "path")
        if path not in self.files:
            raise ToolExecutionError(f"file does not exist: {path}")
        content = self.files[path]
        return {"path": path, "content": content, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}

    def verify_read(self, output: Any) -> bool:
        return isinstance(output, dict) and output.get("path") in self.files and output.get("content") == self.files[output["path"]] and output.get("sha256") == hashlib.sha256(output["content"].encode("utf-8")).hexdigest()

    def move_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        source = _path(args, "source")
        destination = _path(args, "destination")
        if source not in self.files:
            raise ToolExecutionError(f"file does not exist: {source}")
        if destination in self.files:
            raise ToolExecutionError(f"destination already exists: {destination}")
        self.files[destination] = self.files.pop(source)
        return {"source": source, "destination": destination, "source_exists": False, "destination_exists": True}

    def verify_move(self, output: Any) -> bool:
        return isinstance(output, dict) and output.get("source_exists") is False and output.get("destination_exists") is True and output.get("source") not in self.files and output.get("destination") in self.files

    def retry_operation(self, args: Mapping[str, Any]) -> dict[str, Any]:
        operation = args.get("operation")
        attempt = args.get("attempt")
        if not isinstance(operation, str) or not operation or not isinstance(attempt, int) or attempt < 1:
            raise ToolExecutionError("operation must be a name and attempt must be a positive integer")
        self.attempts[operation] = attempt
        return {"operation": operation, "attempt": attempt, "status": "recovered" if attempt >= 2 else "retry_requested"}

    def verify_retry(self, output: Any) -> bool:
        return isinstance(output, dict) and output.get("status") == "recovered" and self.attempts.get(output.get("operation")) == output.get("attempt")


def make_memory_registry(initial_files: Mapping[str, str] | None = None) -> tuple[InMemoryWorkspace, ToolRegistry]:
    workspace = InMemoryWorkspace(dict(initial_files or {}))
    registry = ToolRegistry()
    registry.register(ToolSpec("write_file", "low", workspace.write_file, workspace.verify_write))
    registry.register(ToolSpec("read_file", "low", workspace.read_file, workspace.verify_read))
    registry.register(ToolSpec("move_file", "medium", workspace.move_file, workspace.verify_move))
    registry.register(ToolSpec("retry_operation", "low", workspace.retry_operation, workspace.verify_retry))
    return workspace, registry
