"""Bounded, content-addressed trace retention for the local product."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from traces.replay import load_jsonl

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_STORE_LOCK = threading.RLock()


class TraceStore:
    def __init__(self, root: str | Path, *, max_trace_bytes: int = 1_000_000, max_files: int = 1_000) -> None:
        self.root = Path(root).resolve()
        if not 1 <= max_trace_bytes <= 10_000_000:
            raise ValueError("max_trace_bytes must be between 1 and 10,000,000")
        if not 1 <= max_files <= 10_000:
            raise ValueError("max_files must be between 1 and 10,000")
        self.max_trace_bytes = max_trace_bytes
        self.max_files = max_files

    def _path(self, digest: str) -> Path:
        if not _DIGEST.fullmatch(digest):
            raise ValueError("trace digest must be a lowercase SHA-256 hex string")
        return self.root / f"trace-{digest}.jsonl"

    def save(self, trace_jsonl: str) -> dict[str, Any]:
        encoded = trace_jsonl.encode("utf-8")
        if len(encoded) > self.max_trace_bytes:
            raise ValueError("trace exceeds configured retention size")
        trace = load_jsonl(trace_jsonl.splitlines())
        issues = trace.validate(require_end=True)
        if issues:
            raise ValueError("cannot retain invalid trace: " + "; ".join(issues))
        digest = hashlib.sha256(encoded).hexdigest()
        with _STORE_LOCK:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self._path(digest)
            if not path.exists():
                # Publish only after the complete trace is flushed. This keeps
                # readers from observing a partial JSONL file during concurrent
                # HTTP-server writes.
                temporary: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=self.root,
                        prefix=".trace-",
                        suffix=".tmp",
                        delete=False,
                    ) as handle:
                        temporary = Path(handle.name)
                        handle.write(encoded)
                        handle.flush()
                        os.fsync(handle.fileno())
                    temporary.replace(path)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
            self._enforce_retention()
        return {"digest": digest, "path": str(path), "bytes": len(encoded), "events": len(trace.events)}

    def read(self, digest: str) -> str:
        path = self._path(digest)
        if not path.is_file() or path.resolve().parent != self.root:
            raise FileNotFoundError("trace not found")
        return path.read_text(encoding="utf-8")

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        result = []
        for path in sorted(self.root.glob("trace-*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
            digest = path.stem.removeprefix("trace-")
            if _DIGEST.fullmatch(digest):
                result.append({"digest": digest, "path": str(path), "bytes": path.stat().st_size})
        return result

    def _enforce_retention(self) -> None:
        for item in self.list()[self.max_files :]:
            Path(item["path"]).unlink(missing_ok=True)
