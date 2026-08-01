"""Fail closed when an SFT corpus contains frozen evaluation contracts.

The check is intentionally lexical and conservative: if a held-out task ID,
action argument, expected file, endpoint, browser page, or response marker
appears in a training row, the corpus is not independent of that fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


_GENERIC_VALUES = frozenset(
    {
        "abstain",
        "api_get",
        "browser_open",
        "delete_file",
        "finish",
        "move_file",
        "observe",
        "retry_operation",
        "write_file",
    }
)


# These fixture names and hashes define the immutable audit surface used by
# promotion and verifier-backed RL.  The promotion matrix itself measures only
# the three promotion slices, but training must be disjoint from the exact
# payload and external diagnostic contracts as well.
REQUIRED_FROZEN_FIXTURE_HASHES = {
    "task-spec-research-v4.json": "9c4e3a4f643c21056dd8fe5437ffe180054cf7f96ad02f572910eb298369bfda",
    "task-spec-industry-proxy-v1.json": "c5c0e843f2edc27cdb10b2a2b5d394d5d64373d558f072f4cb0f49001c10cb5e",
    "task-spec-industry-proxy-v2.json": "eb4d071facde6b94e632d68b01caf43e3ae8f7cb456b504e52c38453304d1d6c",
    "task-spec-exact-payload-holdout-v1.json": "0d63bfab581a696528bf3d92bb89e13e64f57b573446f2be5799660f7c3f0cc0",
    "task-spec-external-bar-lite-v1.json": "8d1d852b4cd181079effd7023df13655406de73ddfd6a65329ec6597adf6cae3",
    "task-spec-external-bar-lite-v2.json": "e6c2d7a34fc4317ed116ab882df1f9c6cd363aa60e9f7067329334b9491d785e",
}

# Very short strings are common JSON noise.  Three-to-seven character
# contract values remain useful (for example, a short filename or endpoint),
# so they are checked as exact JSON strings rather than loose substrings.  One
# and two character values are deliberately not markers: their false-positive
# rate makes them unsuitable evidence of contract leakage.
_SHORT_MARKER_MIN_LENGTH = 3
_LONG_MARKER_MIN_LENGTH = 8


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _add_markers(
    markers: set[tuple[str, str]],
    kind: str,
    value: Any,
    *,
    include_short: bool = False,
) -> None:
    for text in _strings(value):
        normalized = text.strip()
        if not normalized or normalized.casefold() in _GENERIC_VALUES:
            continue
        if len(normalized) >= _LONG_MARKER_MIN_LENGTH:
            markers.add((kind, normalized))
        elif include_short and len(normalized) >= _SHORT_MARKER_MIN_LENGTH:
            markers.add((f"{kind}_short_exact", normalized))


def _add_mapping_keys(markers: set[tuple[str, str]], kind: str, value: Any) -> None:
    """Record contract-bearing mapping keys, including short paths/URLs.

    Schema keys such as ``path`` and ``content`` are intentionally excluded by
    calling this only for expected-file, API-record, and browser-page maps.
    Those maps use their keys as task-specific filenames, endpoints, or page
    identifiers rather than generic Action-IR field names.
    """

    if isinstance(value, dict):
        _add_markers(markers, kind, list(value), include_short=True)


def _task_markers(task: dict[str, Any]) -> set[tuple[str, str]]:
    task_id = str(task.get("task_id") or task.get("id") or "<unknown>")
    markers: set[tuple[str, str]] = set()
    _add_markers(markers, "task_id", task_id)
    _add_markers(markers, "prompt", task.get("prompt"))
    _add_markers(markers, "expected_arguments", task.get("expected_arguments", {}), include_short=True)
    for action in task.get("expected_actions") or []:
        if isinstance(action, dict):
            _add_markers(markers, "expected_action_arguments", action.get("arguments", {}), include_short=True)
    expected_files = task.get("expected_files", {})
    api_records = task.get("api_records", {})
    browser_pages = task.get("browser_pages", {})
    _add_markers(markers, "expected_files", expected_files, include_short=True)
    _add_mapping_keys(markers, "expected_file_key", expected_files)
    _add_markers(markers, "api_records", api_records, include_short=True)
    _add_mapping_keys(markers, "api_record_key", api_records)
    _add_markers(markers, "browser_pages", browser_pages, include_short=True)
    _add_mapping_keys(markers, "browser_page_key", browser_pages)
    _add_markers(markers, "expected_result_contains", task.get("expected_result_contains", []), include_short=True)
    return markers


def _marker_occurs_in_train(kind: str, value: str, train_text: str) -> bool:
    if kind.endswith("_short_exact"):
        return json.dumps(value, ensure_ascii=False) in train_text
    return value in train_text


def required_fixture_gate(fixtures: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Validate that an audit covered the complete pinned fixture set."""

    observed: dict[str, list[str]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        name = Path(str(fixture.get("path", ""))).name
        if name:
            observed.setdefault(name, []).append(str(fixture.get("sha256") or ""))
    missing = sorted(name for name in REQUIRED_FROZEN_FIXTURE_HASHES if name not in observed)
    duplicates = sorted(name for name, values in observed.items() if len(values) != 1)
    mismatches = [
        {
            "name": name,
            "expected_sha256": expected,
            "actual_sha256": observed.get(name, [None])[0],
        }
        for name, expected in REQUIRED_FROZEN_FIXTURE_HASHES.items()
        if name in observed and (len(observed[name]) != 1 or observed[name][0] != expected)
    ]
    return {
        "required_fixture_hashes": REQUIRED_FROZEN_FIXTURE_HASHES,
        "present_fixture_names": sorted(observed),
        "extra_fixture_names": sorted(name for name in observed if name not in REQUIRED_FROZEN_FIXTURE_HASHES),
        "missing_fixture_names": missing,
        "duplicate_fixture_names": duplicates,
        "hash_mismatches": mismatches,
        "passed": not missing and not duplicates and not mismatches,
    }


def _normalise_training_sources(value: Any) -> list[dict[str, Any]] | None:
    """Return auditable training-source records or ``None`` when malformed."""

    items = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
    if not items:
        return None
    sources: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            return None
        path = item.get("path")
        digest = item.get("sha256")
        rows = item.get("rows")
        if not isinstance(path, str) or not path or not isinstance(digest, str) or not digest or type(rows) is not int or rows <= 0:
            return None
        sources.append({"path": path, "sha256": digest, "rows": rows})
    return sources


def _source_fingerprints(sources: Any) -> list[list[Any]]:
    normalised = _normalise_training_sources(sources)
    return [[digest, rows] for digest, rows in sorted(
        (item["sha256"], int(item["rows"])) for item in (normalised or [])
    )]


def validate_required_audit_manifest(path: Path) -> dict[str, Any]:
    """Fail closed unless a persisted audit proves complete clean isolation."""

    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": _sha256(path) if path.is_file() else None,
        "schema_valid": False,
        "no_overlaps": False,
        "training_sources_present": False,
        "training_sources": [],
        "fixture_gate": required_fixture_gate([]),
        "passed": False,
    }
    if not path.is_file():
        return result
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    if not isinstance(report, dict):
        return result
    fixtures = report.get("fixtures")
    train = report.get("train")
    fixture_gate = required_fixture_gate(fixtures if isinstance(fixtures, list) else [])
    training_sources = _normalise_training_sources(train)
    training_sources_present = training_sources is not None
    schema_valid = report.get("schema") == "train-holdout-audit/v1"
    no_overlaps = report.get("passed") is True and report.get("overlap_count") == 0
    result.update({
        "schema_valid": schema_valid,
        "no_overlaps": no_overlaps,
        "training_sources_present": training_sources_present,
        "training_sources": training_sources or [],
        "fixture_gate": fixture_gate,
        "passed": bool(schema_valid and no_overlaps and training_sources_present and fixture_gate["passed"]),
    })
    return result


def validate_checkpoint_training_binding(checkpoint: Path, audit_gate: dict[str, Any]) -> dict[str, Any]:
    """Require a merged checkpoint to prove it trained on the audited bytes."""

    merge_manifest_path = checkpoint / "merge_manifest.json"
    training_manifest_path = checkpoint / "training_manifest.json"
    result: dict[str, Any] = {
        "checkpoint": str(checkpoint),
        "exists": checkpoint.is_dir(),
        "audit_passed": audit_gate.get("passed") is True,
        "merge_manifest": str(merge_manifest_path),
        "training_manifest": str(training_manifest_path),
        "merge_schema_valid": False,
        "training_manifest_hash_matches": False,
        "training_sources_match_audit": False,
        "merge_sources_match_training_manifest": False,
        "audit_source_fingerprints": _source_fingerprints(audit_gate.get("training_sources")),
        "training_source_fingerprints": [],
        "passed": False,
    }
    if not checkpoint.is_dir() or not merge_manifest_path.is_file() or not training_manifest_path.is_file():
        return result
    try:
        merge = json.loads(merge_manifest_path.read_text(encoding="utf-8"))
        training = json.loads(training_manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    if not isinstance(merge, dict) or not isinstance(training, dict):
        return result
    audit_sources = _normalise_training_sources(audit_gate.get("training_sources"))
    training_sources = _normalise_training_sources(training.get("training_data"))
    merge_sources = _normalise_training_sources(merge.get("training_data"))
    audit_fingerprints = _source_fingerprints(audit_sources)
    training_fingerprints = _source_fingerprints(training_sources)
    merge_fingerprints = _source_fingerprints(merge_sources)
    training_manifest_hash_matches = (
        merge.get("training_manifest") == "training_manifest.json"
        and merge.get("training_manifest_sha256") == _sha256(training_manifest_path)
    )
    result.update({
        "merge_schema_valid": merge.get("schema") == "merged-lora-checkpoint/v2",
        "training_manifest_hash_matches": training_manifest_hash_matches,
        "training_sources_match_audit": bool(audit_fingerprints and training_fingerprints == audit_fingerprints),
        "merge_sources_match_training_manifest": bool(training_fingerprints and merge_fingerprints == training_fingerprints),
        "training_source_fingerprints": training_fingerprints,
    })
    result["passed"] = bool(
        result["audit_passed"]
        and result["merge_schema_valid"]
        and result["training_manifest_hash_matches"]
        and result["training_sources_match_audit"]
        and result["merge_sources_match_training_manifest"]
    )
    return result


def audit(train_jsonl: list[Path], task_specs: list[Path]) -> dict[str, Any]:
    """Return an immutable, JSON-serializable summary of train/holdout overlap."""

    train_text = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for path in train_jsonl
        for row in _read_jsonl(path)
    )
    fixtures: list[dict[str, Any]] = []
    marker_sources: dict[tuple[str, str], set[str]] = {}
    for path in task_specs:
        document = json.loads(path.read_text(encoding="utf-8"))
        tasks = document.get("tasks", []) if isinstance(document, dict) else document
        fixtures.append({"path": str(path), "sha256": _sha256(path), "tasks": len(tasks)})
        for task in tasks:
            task_id = str(task.get("task_id") or task.get("id") or "<unknown>")
            for marker in _task_markers(task):
                marker_sources.setdefault(marker, set()).add(task_id)

    overlaps = [
        {
            "kind": kind,
            "value": value,
            "task_ids": sorted(marker_sources[(kind, value)]),
        }
        for kind, value in sorted(marker_sources)
        if _marker_occurs_in_train(kind, value, train_text)
    ]
    required_gate = required_fixture_gate(fixtures)
    return {
        "schema": "train-holdout-audit/v1",
        "passed": not overlaps,
        "train": [
            {"path": str(path), "sha256": _sha256(path), "rows": len(_read_jsonl(path))}
            for path in train_jsonl
        ],
        "fixtures": fixtures,
        "marker_count": len(marker_sources),
        "overlap_count": len(overlaps),
        "overlaps": overlaps,
        "required_fixture_gate": required_gate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", action="append", type=Path, required=True)
    parser.add_argument("--task-spec", action="append", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--fail-on-overlap", action="store_true")
    parser.add_argument(
        "--require-required-fixtures",
        action="store_true",
        help="also fail unless every pinned promotion/RL fixture is audited at its fixed hash",
    )
    args = parser.parse_args()

    report = audit(args.train_jsonl, args.task_spec)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    failed_overlap = args.fail_on_overlap and not report["passed"]
    failed_fixture_gate = args.require_required_fixtures and not report["required_fixture_gate"]["passed"]
    return 2 if failed_overlap or failed_fixture_gate else 0


if __name__ == "__main__":
    raise SystemExit(main())
