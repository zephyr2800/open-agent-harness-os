"""Audit structured SFT corpora without publishing their raw examples.

The audit is intentionally descriptive rather than a capability metric.  It
binds a corpus to a source hash, reports duplicate and structural statistics,
and can fail closed on unexpected source drift or repeated full examples /
inputs.  It never serializes prompts, targets, or state values into its report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _distribution(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _duplicate_summary(counter: Counter[str]) -> dict[str, int]:
    repeated = [count for count in counter.values() if count > 1]
    return {
        "unique_values": len(counter),
        "duplicate_groups": len(repeated),
        "duplicate_rows": sum(repeated),
        "excess_rows": sum(count - 1 for count in repeated),
        "max_multiplicity": max(counter.values(), default=0),
    }


def _length_summary(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p90": 0, "p99": 0, "max": 0, "mean": 0.0}
    ordered = sorted(values)

    def percentile(fraction: float) -> int:
        return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]

    return {
        "count": len(values),
        "min": ordered[0],
        "p50": percentile(0.50),
        "p90": percentile(0.90),
        "p99": percentile(0.99),
        "max": ordered[-1],
        "mean": round(sum(values) / len(values), 3),
    }


def _mapping_keys(value: Any, counter: Counter[str]) -> None:
    if isinstance(value, Mapping):
        counter.update(str(key) for key in value)


def audit(
    sources: Iterable[Path],
    *,
    expected_sha256: Sequence[str] | None = None,
    source_labels: Sequence[str] | None = None,
    require_unique_rows: bool = False,
    require_unique_inputs: bool = False,
) -> dict[str, Any]:
    """Return a raw-content-free audit of one or more JSONL SFT sources."""

    paths = [Path(path) for path in sources]
    if not paths:
        raise ValueError("at least one training source is required")
    expected = list(expected_sha256 or ())
    if expected and len(expected) != len(paths):
        raise ValueError("expected_sha256 must be omitted or contain one value per source")
    labels = list(source_labels or ())
    if labels and len(labels) != len(paths):
        raise ValueError("source_labels must be omitted or contain one value per source")

    top_level_fields: Counter[str] = Counter()
    input_fields: Counter[str] = Counter()
    target_fields: Counter[str] = Counter()
    provenance_fields: Counter[str] = Counter()
    target_kinds: Counter[str] = Counter()
    provenance_sources: Counter[str] = Counter()
    sampling_strata: Counter[str] = Counter()
    row_digests: Counter[str] = Counter()
    input_digests: Counter[str] = Counter()
    target_digests: Counter[str] = Counter()
    task_ids: Counter[str] = Counter()
    row_lengths: list[int] = []
    input_lengths: list[int] = []
    target_lengths: list[int] = []
    source_reports: list[dict[str, Any]] = []

    for index, path in enumerate(paths):
        actual_hash = _file_sha256(path)
        expected_hash = expected[index] if expected else None
        source_rows = 0
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
                if not isinstance(row, Mapping):
                    raise ValueError(f"JSONL row at {path}:{line_number} must be an object")
                source_rows += 1
                top_level_fields.update(str(key) for key in row)
                input_value = row.get("input")
                target_value = row.get("target")
                provenance_value = row.get("provenance")
                _mapping_keys(input_value, input_fields)
                _mapping_keys(target_value, target_fields)
                _mapping_keys(provenance_value, provenance_fields)
                if isinstance(target_value, Mapping):
                    target_kinds[str(target_value.get("kind", "<missing>"))] += 1
                if isinstance(provenance_value, Mapping):
                    provenance_sources[str(provenance_value.get("source", "<missing>"))] += 1
                    sampling_strata[str(provenance_value.get("sampling_stratum", "<missing>"))] += 1
                row_digests[_digest(row)] += 1
                input_digests[_digest(input_value)] += 1
                target_digests[_digest(target_value)] += 1
                task_ids[str(row.get("task_id", "<missing>"))] += 1
                row_lengths.append(len(_canonical(row)))
                input_lengths.append(len(_canonical(input_value)))
                target_lengths.append(len(_canonical(target_value)))
        source_reports.append({
            "source": labels[index] if labels else str(path),
            "rows": source_rows,
            "sha256": actual_hash,
            "expected_sha256": expected_hash,
            "source_hash_matches_expected": expected_hash is None or actual_hash == expected_hash,
        })

    duplicates = {
        "exact_rows": _duplicate_summary(row_digests),
        "inputs": _duplicate_summary(input_digests),
        "targets": _duplicate_summary(target_digests),
        "task_ids": _duplicate_summary(task_ids),
    }
    assertions = {
        "source_hashes_match": all(item["source_hash_matches_expected"] for item in source_reports),
        "unique_rows": duplicates["exact_rows"]["duplicate_groups"] == 0,
        "unique_inputs": duplicates["inputs"]["duplicate_groups"] == 0,
    }
    passed = assertions["source_hashes_match"]
    if require_unique_rows:
        passed = passed and assertions["unique_rows"]
    if require_unique_inputs:
        passed = passed and assertions["unique_inputs"]
    return {
        "schema": "corpus-quality-audit/v1",
        "raw_examples_included": False,
        "sources": source_reports,
        "row_count": sum(item["rows"] for item in source_reports),
        "field_presence": {
            "top_level": _distribution(top_level_fields),
            "input": _distribution(input_fields),
            "target": _distribution(target_fields),
            "provenance": _distribution(provenance_fields),
        },
        "distributions": {
            "target_kind": _distribution(target_kinds),
            "provenance_source": _distribution(provenance_sources),
            "sampling_stratum": _distribution(sampling_strata),
        },
        "duplicate_checks": duplicates,
        "serialized_character_lengths": {
            "row": _length_summary(row_lengths),
            "input": _length_summary(input_lengths),
            "target": _length_summary(target_lengths),
        },
        "assertions": assertions,
        "requirements": {
            "require_unique_rows": require_unique_rows,
            "require_unique_inputs": require_unique_inputs,
        },
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-sha256", action="append")
    parser.add_argument("--source-label", action="append", help="portable label to publish instead of the local source path")
    parser.add_argument("--require-unique-rows", action="store_true")
    parser.add_argument("--require-unique-inputs", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(
            [Path(item) for item in args.train_jsonl],
            expected_sha256=args.expected_sha256,
            source_labels=args.source_label,
            require_unique_rows=args.require_unique_rows,
            require_unique_inputs=args.require_unique_inputs,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({
        "passed": report["passed"],
        "row_count": report["row_count"],
        "unique_rows": report["assertions"]["unique_rows"],
        "unique_inputs": report["assertions"]["unique_inputs"],
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
