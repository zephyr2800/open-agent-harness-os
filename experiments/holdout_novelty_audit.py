"""Measure lexical template affinity between SFT data and held-out task prompts.

This complements ``data_split_audit``.  The split audit rejects direct task
contracts and marker leakage.  This audit deliberately normalizes paths and
number-bearing identifiers, then measures the closest token-set overlap between
each held-out prompt and a training goal.  It is a transparent warning about
template affinity, not a claim to measure semantic novelty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from experiments.data_split_audit import task_spec_sha256


SCHEMA = "holdout-novelty-audit/v1"
DEFAULT_MAX_NORMALIZED_TOKEN_JACCARD = 0.55
DEFAULT_MAX_HIGH_AFFINITY_RATE = 0.05
_PATH_RE = re.compile(r"\b[a-z0-9_./-]+\.(?:cfg|csv|dat|json|log|md|txt)\b", re.IGNORECASE)
_NUMBERED_IDENTIFIER_RE = re.compile(r"\b(?:[a-z]+[_-]?)*\d+(?:[_-]?[a-z0-9]+)*\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"<path>|<id>|[a-z]+")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _task_rows(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    tasks = document.get("tasks", []) if isinstance(document, dict) else document
    if not isinstance(tasks, list):
        raise ValueError(f"task spec has no task list: {path}")
    if not all(isinstance(task, dict) for task in tasks):
        raise ValueError(f"task spec contains a non-object task: {path}")
    return tasks


def _training_goal(row: dict[str, Any]) -> str:
    payload = row.get("input")
    if isinstance(payload, dict):
        for key in ("goal", "prompt"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    for key in ("goal", "prompt"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _normalize_tokens(value: str) -> frozenset[str]:
    """Remove direct identifiers while retaining natural-language templates."""

    normalized = _PATH_RE.sub("<path>", value.casefold())
    normalized = _NUMBERED_IDENTIFIER_RE.sub("<id>", normalized)
    return frozenset(_TOKEN_RE.findall(normalized))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _source_records(paths: list[Path]) -> tuple[list[dict[str, Any]], list[tuple[str, frozenset[str]]]]:
    records: list[dict[str, Any]] = []
    goals: list[tuple[str, frozenset[str]]] = []
    for path in paths:
        rows = _read_jsonl(path)
        records.append({"path": str(path), "sha256": _sha256(path), "rows": len(rows)})
        for index, row in enumerate(rows):
            task_id = str(row.get("task_id") or row.get("id") or f"{path.name}:{index}")
            tokens = _normalize_tokens(_training_goal(row))
            if tokens:
                goals.append((task_id, tokens))
    return records, goals


def _validate_thresholds(*, max_normalized_token_jaccard: float, max_high_affinity_rate: float) -> None:
    if not 0.0 <= max_normalized_token_jaccard <= 1.0:
        raise ValueError("max_normalized_token_jaccard must be between zero and one")
    if not 0.0 <= max_high_affinity_rate <= 1.0:
        raise ValueError("max_high_affinity_rate must be between zero and one")


def audit(
    train_jsonl: list[Path],
    task_specs: list[Path],
    *,
    max_normalized_token_jaccard: float = DEFAULT_MAX_NORMALIZED_TOKEN_JACCARD,
    max_high_affinity_rate: float = DEFAULT_MAX_HIGH_AFFINITY_RATE,
) -> dict[str, Any]:
    """Return a deterministic prompt-template-affinity report."""

    _validate_thresholds(
        max_normalized_token_jaccard=max_normalized_token_jaccard,
        max_high_affinity_rate=max_high_affinity_rate,
    )
    train, goals = _source_records(train_jsonl)
    if not goals:
        raise ValueError("training JSONL contains no usable goal or prompt text")

    specs: list[dict[str, Any]] = []
    all_tasks = 0
    all_high_affinity = 0
    all_missing_prompt = 0
    all_scores: list[float] = []
    for path in task_specs:
        rows = _task_rows(path)
        task_records: list[dict[str, Any]] = []
        for index, task in enumerate(rows):
            task_id = str(task.get("task_id") or task.get("id") or f"{path.name}:{index}")
            prompt = task.get("prompt")
            tokens = _normalize_tokens(prompt) if isinstance(prompt, str) else frozenset()
            if not tokens:
                task_records.append({
                    "task_id": task_id,
                    "max_normalized_token_jaccard": None,
                    "nearest_training_task_id": None,
                    "high_affinity": True,
                    "missing_prompt": True,
                })
                continue
            score, nearest_task_id = max(
                ((_jaccard(tokens, train_tokens), train_task_id) for train_task_id, train_tokens in goals),
                default=(0.0, None),
            )
            task_records.append({
                "task_id": task_id,
                "max_normalized_token_jaccard": round(score, 6),
                "nearest_training_task_id": nearest_task_id,
                "high_affinity": score > max_normalized_token_jaccard,
                "missing_prompt": False,
            })
        scores = [record["max_normalized_token_jaccard"] for record in task_records if record["max_normalized_token_jaccard"] is not None]
        high_affinity = sum(bool(record["high_affinity"]) for record in task_records)
        missing_prompt = sum(bool(record["missing_prompt"]) for record in task_records)
        task_count = len(task_records)
        high_affinity_rate = high_affinity / task_count if task_count else 1.0
        specs.append({
            "path": str(path),
            "sha256": task_spec_sha256(path),
            "tasks": task_count,
            "mean_max_normalized_token_jaccard": round(sum(scores) / len(scores), 6) if scores else None,
            "max_normalized_token_jaccard": max(scores) if scores else None,
            "high_affinity_tasks": high_affinity,
            "high_affinity_rate": high_affinity_rate,
            "missing_prompt_tasks": missing_prompt,
            "passed": bool(task_count and not missing_prompt and high_affinity_rate <= max_high_affinity_rate),
            "task_records": task_records,
        })
        all_tasks += task_count
        all_high_affinity += high_affinity
        all_missing_prompt += missing_prompt
        all_scores.extend(scores)

    high_affinity_rate = all_high_affinity / all_tasks if all_tasks else 1.0
    return {
        "schema": SCHEMA,
        "purpose": "lexical template-affinity measurement; not a semantic-novelty claim",
        "thresholds": {
            "max_normalized_token_jaccard": max_normalized_token_jaccard,
            "max_high_affinity_rate": max_high_affinity_rate,
        },
        "train": train,
        "training_goal_count": len(goals),
        "task_specs": specs,
        "task_count": all_tasks,
        "high_affinity_tasks": all_high_affinity,
        "high_affinity_rate": high_affinity_rate,
        "missing_prompt_tasks": all_missing_prompt,
        "mean_max_normalized_token_jaccard": round(sum(all_scores) / len(all_scores), 6) if all_scores else None,
        "max_normalized_token_jaccard": max(all_scores) if all_scores else None,
        "passed": bool(all_tasks and not all_missing_prompt and all(spec["passed"] for spec in specs)),
    }


def _source_fingerprints(sources: Any) -> list[list[Any]]:
    if not isinstance(sources, list):
        return []
    fingerprints: list[list[Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            return []
        digest = source.get("sha256")
        rows = source.get("rows")
        if not isinstance(digest, str) or not digest or type(rows) is not int or rows <= 0:
            return []
        fingerprints.append([digest, rows])
    return sorted(fingerprints)


def validate_manifest(
    path: Path,
    *,
    expected_training_sources: list[dict[str, Any]],
    expected_task_spec_hashes: dict[str, str],
) -> dict[str, Any]:
    """Fail closed unless a passing novelty report binds to the exact inputs."""

    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": _sha256(path) if path.is_file() else None,
        "schema_valid": False,
        "report_passed": False,
        "training_sources_match": False,
        "task_specs_match": False,
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
    observed_hashes: dict[str, list[str]] = {}
    specs = report.get("task_specs")
    if isinstance(specs, list):
        for spec in specs:
            if isinstance(spec, dict):
                name = Path(str(spec.get("path") or "")).name
                digest = spec.get("sha256")
                if name and isinstance(digest, str):
                    observed_hashes.setdefault(name, []).append(digest)
    task_specs_match = (
        set(observed_hashes) == set(expected_task_spec_hashes)
        and all(values == [expected_task_spec_hashes[name]] for name, values in observed_hashes.items())
    )
    training_sources_match = _source_fingerprints(report.get("train")) == _source_fingerprints(expected_training_sources)
    result.update({
        "schema_valid": report.get("schema") == SCHEMA,
        "report_passed": report.get("passed") is True,
        "training_sources_match": training_sources_match,
        "task_specs_match": task_specs_match,
    })
    result["passed"] = bool(
        result["schema_valid"]
        and result["report_passed"]
        and result["training_sources_match"]
        and result["task_specs_match"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", action="append", type=Path, required=True)
    parser.add_argument("--task-spec", action="append", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--max-normalized-token-jaccard", type=float, default=DEFAULT_MAX_NORMALIZED_TOKEN_JACCARD)
    parser.add_argument("--max-high-affinity-rate", type=float, default=DEFAULT_MAX_HIGH_AFFINITY_RATE)
    parser.add_argument("--fail-on-affinity", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(
            args.train_jsonl,
            args.task_spec,
            max_normalized_token_jaccard=args.max_normalized_token_jaccard,
            max_high_affinity_rate=args.max_high_affinity_rate,
        )
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 2 if args.fail_on_affinity and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
