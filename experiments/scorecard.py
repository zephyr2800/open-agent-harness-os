"""Produce a claim-safe scorecard for model-harness evaluation runs.

The scorecard keeps the unit of analysis explicit: a model, harness, task
suite, and execution budget form one configuration.  It reports micro and
macro family scores, process integrity, safety, and efficiency separately so
that an easy aggregate cannot hide a catastrophic family failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping


SCHEMA = "agent-eval-scorecard/v1"
SUITE_KINDS = frozenset({"local_fixture", "external_native"})
_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_OBSERVED_BOOLEAN_METRICS = (
    "protocol_valid",
    "trace_valid",
    "runtime_replay_agreement",
    "unsafe_attempt",
    "false_completion",
)


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total))) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _rate(rows: list[Mapping[str, Any]], key: str) -> float:
    return sum(bool(row.get(key)) for row in rows) / len(rows) if rows else 0.0


def _observed_rate(rows: Iterable[Mapping[str, Any]], key: str) -> float | None:
    values = list(rows)
    if not values or _coverage(values, key) < 1.0:
        return None
    return _rate(values, key)


def _coverage(rows: Iterable[Mapping[str, Any]], key: str) -> float:
    values = list(rows)
    if not values:
        return 0.0
    return sum(key in row.get("_observed_metrics", ()) for row in values) / len(values)


def _family_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        family = str(row.get("family", "unspecified"))
        groups.setdefault(family, []).append(row)
    result: dict[str, dict[str, Any]] = {}
    for family, group in sorted(groups.items()):
        total = len(group)
        successes = sum(bool(row.get("verified_success")) for row in group)
        low, high = _wilson(successes, total)
        result[family] = {
            "tasks": total,
            "verified_successes": successes,
            "verified_success_rate": successes / total if total else 0.0,
            "protocol_valid_rate": _observed_rate(group, "protocol_valid"),
            "trace_valid_rate": _observed_rate(group, "trace_valid"),
            "runtime_replay_agreement": _observed_rate(group, "runtime_replay_agreement"),
            "unsafe_attempt_rate": _observed_rate(group, "unsafe_attempt"),
            "false_completion_rate": _observed_rate(group, "false_completion"),
            "wilson_95_low": low,
            "wilson_95_high": high,
            "metric_coverage": {key: _coverage(group, key) for key in _OBSERVED_BOOLEAN_METRICS},
        }
    return result


def _normalise_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        row = dict(raw)
        if not row.get("task_id"):
            raise ValueError(f"row {index} is missing task_id")
        if "verified_success" not in row:
            raise ValueError(f"row {index} is missing verified_success")
        observed = {key for key in _OBSERVED_BOOLEAN_METRICS if key in row and row[key] is not None}
        independent = row.get("independent")
        if isinstance(independent, Mapping):
            if row.get("trace_valid") is None and "trace_valid" in independent:
                row["trace_valid"] = independent["trace_valid"]
                observed.add("trace_valid")
            if row.get("runtime_replay_agreement") is None and "matches_runtime" in independent:
                row["runtime_replay_agreement"] = independent["matches_runtime"]
                observed.add("runtime_replay_agreement")
        row["_observed_metrics"] = tuple(sorted(observed))
        normalised.append(row)
    return normalised


def _observed_false(row: Mapping[str, Any], key: str) -> bool:
    return key in row.get("_observed_metrics", ()) and not bool(row.get(key))


def _validate_external_provenance(
    *,
    values: list[dict[str, Any]],
    suite_commit: str | None,
    native_metric: str | None,
    native_metric_value: int | float | None,
    native_report_sha256: str | None,
    native_report_path: str | Path | None,
    native_grader: str | None,
    native_environment: Mapping[str, Any] | None,
) -> None:
    """Require enough native evidence to make an external claim auditable.

    The scorecard cannot authenticate an external runner's identity by itself,
    but it does require a real local report file and verifies its SHA-256
    before accepting the external label. The grader identity, environment,
    and native numeric metric remain explicit handoff metadata.
    """

    if not values:
        raise ValueError("external_native scorecards require at least one task row")
    if not suite_commit or not _GIT_COMMIT_RE.fullmatch(str(suite_commit)):
        raise ValueError("external_native scorecards require a hexadecimal suite_commit")
    if not native_metric:
        raise ValueError("external_native scorecards require native_metric")
    if isinstance(native_metric_value, bool) or not isinstance(native_metric_value, (int, float)) or not math.isfinite(float(native_metric_value)):
        raise ValueError("external_native scorecards require a finite numeric native_metric_value")
    if not native_report_sha256 or not _SHA256_RE.fullmatch(str(native_report_sha256)):
        raise ValueError("external_native scorecards require a SHA-256 native_report_sha256")
    if not native_report_path:
        raise ValueError("external_native scorecards require native_report_path")
    report_path = Path(native_report_path)
    if not report_path.is_file():
        raise ValueError("external_native native_report_path does not exist")
    actual_report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if actual_report_sha256 != str(native_report_sha256).lower():
        raise ValueError("native_report_sha256 does not match native_report_path")
    if not native_grader:
        raise ValueError("external_native scorecards require native_grader")
    if not isinstance(native_environment, Mapping) or not all(native_environment.get(key) for key in ("runner", "runtime", "platform")):
        raise ValueError("external_native scorecards require runner, runtime, and platform environment metadata")


def build_scorecard(
    rows: Iterable[Mapping[str, Any]],
    *,
    suite: str,
    suite_kind: str,
    model: str,
    harness: str,
    seed: int | str | None = None,
    suite_version: str | None = None,
    suite_commit: str | None = None,
    native_metric: str | None = None,
    native_metric_value: int | float | None = None,
    native_report_sha256: str | None = None,
    native_report_path: str | Path | None = None,
    native_grader: str | None = None,
    native_environment: Mapping[str, Any] | None = None,
    native_run_complete: bool | None = None,
    task_spec_sha256: str | None = None,
    execution_budget: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a portable scorecard and reject ambiguous external claims."""

    if suite_kind not in SUITE_KINDS:
        raise ValueError(f"suite_kind must be one of {sorted(SUITE_KINDS)}")
    values = _normalise_rows(rows)
    if execution_budget is not None and not isinstance(execution_budget, Mapping):
        raise ValueError("execution_budget must be a mapping")
    if runtime is not None and not isinstance(runtime, Mapping):
        raise ValueError("runtime must be a mapping")
    if native_run_complete is not None and not isinstance(native_run_complete, bool):
        raise ValueError("native_run_complete must be a boolean when supplied")
    if suite_kind == "external_native" and native_run_complete is False:
        raise ValueError("external_native scorecards cannot use an incomplete native run")
    if suite_kind == "external_native":
        _validate_external_provenance(
            values=values,
            suite_commit=suite_commit,
            native_metric=native_metric,
            native_metric_value=native_metric_value,
            native_report_sha256=native_report_sha256,
            native_report_path=native_report_path,
            native_grader=native_grader,
            native_environment=native_environment,
        )
    families = _family_summary(values)
    adversarial = [row for row in values if bool(row.get("adversarial"))]
    safe_abstain = [
        row
        for row in adversarial
        if (bool(row.get("abstained")) or bool(row.get("safe_abstain")))
        and bool(row.get("verified_success"))
        and _observed_false(row, "unsafe_attempt")
        and _observed_false(row, "false_completion")
    ]
    output_tokens = [float(row["metrics"]["output_tokens"]) for row in values if isinstance(row.get("metrics"), Mapping) and "output_tokens" in row["metrics"]]
    elapsed = [float(row["elapsed_seconds"]) for row in values if isinstance(row.get("elapsed_seconds"), (int, float))]
    family_rates = [float(item["verified_success_rate"]) for item in families.values()]
    total = len(values)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "suite": suite,
        "suite_kind": suite_kind,
        "suite_version": suite_version,
        "suite_commit": suite_commit,
        "native_metric": native_metric,
        "native_metric_value": native_metric_value,
        "native_report_sha256": native_report_sha256,
        "native_grader": native_grader,
        "native_environment": dict(native_environment or {}),
        "native_run_complete": native_run_complete,
        "task_spec_sha256": task_spec_sha256,
        "model": model,
        "harness": harness,
        "seed": seed,
        "execution_budget": dict(execution_budget or {}),
        "runtime": dict(runtime or {}),
        "task_runs": total,
        "verified_successes": sum(bool(row.get("verified_success")) for row in values),
        "verified_success_rate": _rate(values, "verified_success"),
        "macro_family_success_rate": mean(family_rates) if family_rates else 0.0,
        "protocol_valid_rate": _observed_rate(values, "protocol_valid"),
        "trace_valid_rate": _observed_rate(values, "trace_valid"),
        "runtime_replay_agreement": _observed_rate(values, "runtime_replay_agreement"),
        "unsafe_attempt_rate": _observed_rate(values, "unsafe_attempt"),
        "false_completion_rate": _observed_rate(values, "false_completion"),
        "metric_coverage": {key: _coverage(values, key) for key in _OBSERVED_BOOLEAN_METRICS},
        "metric_coverage_note": (
            "Rates are null when coverage is below 1.0; an unobserved metric must not be interpreted as a measured zero."
        ),
        "adversarial_task_runs": len(adversarial),
        "safe_abstain_rate": len(safe_abstain) / len(adversarial) if adversarial else 0.0,
        "mean_output_tokens": mean(output_tokens) if output_tokens else None,
        "mean_elapsed_seconds": mean(elapsed) if elapsed else None,
        "by_family": families,
        "claim_boundary": (
            "native external-suite result; report the suite's native metric"
            if suite_kind == "external_native"
            else "local fixture/proxy result; do not describe as an external benchmark score"
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="JSON report containing a rows array")
    parser.add_argument("--output", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--suite-kind", choices=sorted(SUITE_KINDS), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--seed")
    parser.add_argument("--suite-version")
    parser.add_argument("--suite-commit")
    parser.add_argument("--native-metric")
    parser.add_argument("--native-metric-value", type=float)
    parser.add_argument("--native-report", help="native runner JSON/report to hash")
    parser.add_argument("--native-report-sha256")
    parser.add_argument("--native-grader")
    parser.add_argument("--native-environment-json", help="JSON object with runner, runtime, and platform")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if not isinstance(report, Mapping) or not isinstance(report.get("rows"), list):
        raise SystemExit("report must be a JSON object containing rows")
    native_report_sha256 = args.native_report_sha256
    if args.native_report:
        native_report_path = Path(args.native_report)
        if not native_report_path.is_file():
            raise SystemExit(f"native report does not exist: {native_report_path}")
        computed_hash = hashlib.sha256(native_report_path.read_bytes()).hexdigest()
        if native_report_sha256 and native_report_sha256.lower() != computed_hash:
            raise SystemExit("--native-report-sha256 does not match --native-report")
        native_report_sha256 = computed_hash
    try:
        native_environment = json.loads(args.native_environment_json) if args.native_environment_json else None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--native-environment-json must be valid JSON: {exc}") from exc
    scorecard = build_scorecard(
        report["rows"],
        suite=args.suite,
        suite_kind=args.suite_kind,
        model=args.model,
        harness=args.harness,
        seed=args.seed,
        suite_version=args.suite_version,
        suite_commit=args.suite_commit,
        native_metric=args.native_metric,
        native_metric_value=args.native_metric_value,
        native_report_sha256=native_report_sha256,
        native_report_path=args.native_report,
        native_grader=args.native_grader,
        native_environment=native_environment,
        native_run_complete=report.get("complete") if "complete" in report else None,
        task_spec_sha256=report.get("task_spec_sha256"),
        execution_budget=report.get("execution_budget") or report.get("budget") or report.get("config"),
        runtime=report.get("runtime") or report.get("resource"),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: scorecard[key] for key in ("suite", "suite_kind", "task_runs", "verified_success_rate", "macro_family_success_rate", "runtime_replay_agreement", "unsafe_attempt_rate")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
