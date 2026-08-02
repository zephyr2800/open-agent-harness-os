"""Create and verify content-bound local checkpoint identity manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "checkpoint-identity/v1"
_WEIGHT_SUFFIXES = frozenset({".bin", ".safetensors"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"checkpoint must not contain symlinks: {path}")
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _canonical_files(files: list[dict[str, Any]]) -> bytes:
    return json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def record_checkpoint_identity(
    checkpoint: str | Path,
    *,
    model_id: str,
    revision: str | None,
) -> dict[str, Any]:
    """Fingerprint every local checkpoint file before a claim-eligible run."""

    if not isinstance(model_id, str) or not model_id:
        raise ValueError("model_id must be a non-empty string")
    if revision is not None and not isinstance(revision, str):
        raise ValueError("revision must be a string or null")
    root = Path(checkpoint).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"checkpoint root is not a directory: {root}")
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in _checkpoint_files(root)
    ]
    if not files:
        raise ValueError(f"checkpoint has no files: {root}")
    if not any(Path(item["path"]).suffix.lower() in _WEIGHT_SUFFIXES for item in files):
        raise ValueError(f"checkpoint has no recognized weight file: {root}")
    return {
        "schema": SCHEMA,
        "model_id": model_id,
        "revision": revision,
        "checkpoint_root": str(root),
        "file_count": len(files),
        "files": files,
        "sha256": hashlib.sha256(_canonical_files(files)).hexdigest(),
    }


def manifest_sha256(path: str | Path) -> str:
    manifest = Path(path).expanduser().resolve()
    if not manifest.is_file():
        raise ValueError(f"checkpoint identity manifest is not a file: {manifest}")
    return _sha256(manifest)


def verify_checkpoint_identity_manifest(
    manifest_path: str | Path,
    *,
    model_id: str,
    revision: str | None,
    checkpoint_path: str | Path,
) -> dict[str, Any]:
    """Fail closed unless a manifest still describes the loaded local checkpoint."""

    manifest = Path(manifest_path).expanduser().resolve()
    if not manifest.is_file():
        raise ValueError(f"checkpoint identity manifest is not a file: {manifest}")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"checkpoint identity manifest is not valid JSON: {manifest}") from exc
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        raise ValueError(f"checkpoint identity manifest must use {SCHEMA}: {manifest}")
    root = Path(checkpoint_path).expanduser().resolve()
    expected = record_checkpoint_identity(root, model_id=model_id, revision=revision)
    expected_fields = ("schema", "model_id", "revision", "checkpoint_root", "file_count", "files", "sha256")
    if any(payload.get(field) != expected[field] for field in expected_fields):
        raise ValueError(f"checkpoint identity manifest does not match the current checkpoint: {manifest}")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    identity = record_checkpoint_identity(
        args.checkpoint,
        model_id=args.model_id,
        revision=args.revision,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": identity["schema"],
        "file_count": identity["file_count"],
        "sha256": identity["sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
