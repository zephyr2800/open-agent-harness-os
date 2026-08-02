"""Deterministic runtime-source records for local evaluation manifests.

The native benchmark launchers load policy code from mutable local directories.
This module fingerprints the executable Python source tree, excluding tests,
documentation, caches, and generated work artifacts. It is a local consistency
boundary, not a replacement for signed provenance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "python-source-tree/v1"
_EXCLUDED_PARTS = frozenset({".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist", "docs", "tests", "work"})
_SOURCE_FILE_NAMES = frozenset({"pyproject.toml"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"source tree must not contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in _EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".py" or path.name in _SOURCE_FILE_NAMES:
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def record_source_tree(root: str | Path) -> dict[str, Any]:
    """Return a stable content digest for executable source below ``root``."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise ValueError(f"source tree root is not a directory: {root_path}")
    files = [
        {
            "path": path.relative_to(root_path).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in _source_files(root_path)
    ]
    if not files:
        raise ValueError(f"source tree has no executable Python files: {root_path}")
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema": SCHEMA,
        "root": str(root_path),
        "file_count": len(files),
        "files": files,
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def verify_source_tree_record(
    value: Mapping[str, Any] | object,
    *,
    field: str,
    expected_root: str | Path | None = None,
) -> dict[str, Any]:
    """Fail closed when a recorded runtime source tree no longer matches disk."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    if value.get("schema") != SCHEMA:
        raise ValueError(f"{field}.schema must be {SCHEMA}")
    root_value = value.get("root")
    if not isinstance(root_value, str) or not root_value:
        raise ValueError(f"{field}.root must be a non-empty path")
    recorded_root = Path(root_value).expanduser().resolve()
    if expected_root is not None and recorded_root != Path(expected_root).expanduser().resolve():
        raise ValueError(f"{field}.root does not match the adapter command source root")
    recorded = {
        "schema": value.get("schema"),
        "root": str(recorded_root),
        "file_count": value.get("file_count"),
        "files": value.get("files"),
        "sha256": value.get("sha256"),
    }
    current = record_source_tree(recorded_root)
    if recorded["file_count"] != current["file_count"] or recorded["files"] != current["files"]:
        raise ValueError(f"{field} does not match the current source tree")
    if recorded["sha256"] != current["sha256"]:
        raise ValueError(f"{field}.sha256 does not match the current source tree")
    return current
