"""Convert native τ³-bench results into claim-safe scorecard input rows.

This module intentionally preserves the τ³-bench native reward as the primary
metric. It never invents Action IR protocol validity, independent replay, or
safety fields that τ³-bench did not observe. The generic scorecard will expose
zero coverage for those unobserved metrics rather than presenting them as
measured zeros.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "tau3-native-export/v1"
SUITE = "tau3-bench"
NATIVE_GRADER = "tau2-native-results-reward"
_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return loaded


def _results_paths(path: Path) -> tuple[Path, Path | None]:
    resolved = path.expanduser().resolve()
    if resolved.is_dir():
        return resolved / "results.json", resolved / "simulations"
    simulation_dir = resolved.parent / "simulations"
    return resolved, simulation_dir if simulation_dir.is_dir() else None


def _directory_fingerprint(report_path: Path, simulation_dir: Path | None) -> tuple[str, list[str]]:
    candidates = [report_path]
    if simulation_dir is not None and simulation_dir.is_dir():
        candidates.extend(sorted(simulation_dir.glob("*.json")))
    if not report_path.is_file():
        raise ValueError(f"native τ³-bench results file is missing: {report_path}")
    root = report_path.parent
    digest = hashlib.sha256()
    files: list[str] = []
    for candidate in candidates:
        if not candidate.is_file():
            raise ValueError(f"native τ³-bench simulation file is missing: {candidate}")
        relative = candidate.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
        files.append(relative)
    return digest.hexdigest(), files


def load_results(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], Path, str, list[str]]:
    """Load τ³-bench's monolithic or directory result layout without importing it."""

    report_path, simulation_dir = _results_paths(path)
    report = _read_json(report_path)
    fingerprint, source_files = _directory_fingerprint(report_path, simulation_dir)
    simulations = report.get("simulations")
    if simulation_dir is not None:
        simulations = [_read_json(candidate) for candidate in sorted(simulation_dir.glob("*.json"))]
        index = report.get("simulation_index")
        if isinstance(index, list):
            indexed_ids = {str(item.get("id")) for item in index if isinstance(item, Mapping)}
            actual_ids = {candidate.stem for candidate in simulation_dir.glob("*.json")}
            if indexed_ids != actual_ids:
                raise ValueError("τ³-bench directory result index does not match its simulation files")
    if not isinstance(simulations, list):
        raise ValueError("τ³-bench results must contain a simulations list")
    normalised = []
    for position, item in enumerate(simulations):
        if not isinstance(item, Mapping):
            raise ValueError(f"τ³-bench simulation {position} is not a JSON object")
        normalised.append(dict(item))
    return report, normalised, report_path, fingerprint, source_files


def _reward(simulation: Mapping[str, Any]) -> float | None:
    reward_info = simulation.get("reward_info")
    if not isinstance(reward_info, Mapping):
        return None
    value = reward_info.get("reward")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def _is_native_success(reward: float | None) -> bool:
    return reward is not None and (1.0 - 1e-6) <= reward <= (1.0 + 1e-6)


def _native_domain(info: Mapping[str, Any]) -> str:
    environment = info.get("environment_info")
    if not isinstance(environment, Mapping):
        raise ValueError("τ³-bench results are missing info.environment_info")
    domain = environment.get("domain_name")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("τ³-bench results are missing info.environment_info.domain_name")
    return domain.strip()


def _validate_complete_run(
    report: Mapping[str, Any],
    simulations: Iterable[Mapping[str, Any]],
    *,
    num_trials: int,
) -> int:
    tasks = report.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("τ³-bench results must contain at least one task")
    task_ids: list[str] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, Mapping):
            raise ValueError(f"τ³-bench task {index} is not a JSON object")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"τ³-bench task {index} is missing id")
        task_ids.append(task_id)
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("τ³-bench results contain duplicate task ids")

    expected = {(task_id, trial) for task_id in task_ids for trial in range(num_trials)}
    observed: set[tuple[str, int]] = set()
    simulation_ids: set[str] = set()
    for index, simulation in enumerate(simulations):
        simulation_id = simulation.get("id")
        if not isinstance(simulation_id, str) or not simulation_id:
            raise ValueError(f"τ³-bench simulation {index} is missing id")
        if simulation_id in simulation_ids:
            raise ValueError(f"τ³-bench results contain duplicate simulation id: {simulation_id}")
        simulation_ids.add(simulation_id)

        task_id = simulation.get("task_id")
        if not isinstance(task_id, str) or task_id not in task_ids:
            raise ValueError(f"τ³-bench simulation {index} has an unknown task_id")
        trial = simulation.get("trial")
        if isinstance(trial, bool) or not isinstance(trial, int) or not 0 <= trial < num_trials:
            raise ValueError(f"τ³-bench simulation {index} has an invalid trial")
        run_key = (task_id, trial)
        if run_key in observed:
            raise ValueError(f"τ³-bench results contain a duplicate task/trial run: {task_id}/{trial}")
        observed.add(run_key)
        if simulation.get("termination_reason") == "infrastructure_error":
            raise ValueError("τ³-bench results contain an infrastructure error; rerun before export")
        if _reward(simulation) is None:
            raise ValueError(f"τ³-bench simulation {index} has no finite native reward")

    if observed != expected:
        missing = len(expected - observed)
        unexpected = len(observed - expected)
        raise ValueError(
            "τ³-bench results do not contain every expected task/trial run "
            f"(missing={missing}, unexpected={unexpected})"
        )
    return len(expected)


def _native_metrics(simulations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    evaluated = [simulation for simulation in simulations if simulation.get("termination_reason") != "infrastructure_error"]
    rewards = [reward for simulation in evaluated if (reward := _reward(simulation)) is not None]
    by_task: dict[str, list[bool]] = defaultdict(list)
    for simulation in evaluated:
        task_id = simulation.get("task_id")
        if task_id is None:
            continue
        by_task[str(task_id)].append(_is_native_success(_reward(simulation)))
    pass_hat: dict[str, float] = {}
    if by_task:
        max_k = min(len(successes) for successes in by_task.values())
        for k in range(1, max_k + 1):
            values = [math.comb(sum(successes), k) / math.comb(len(successes), k) for successes in by_task.values()]
            pass_hat[f"pass_hat_{k}"] = sum(values) / len(values)
    return {
        "average_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "pass_hat": pass_hat,
        "task_runs": len(simulations),
        "evaluated_task_runs": len(evaluated),
        "infrastructure_error_count": len(simulations) - len(evaluated),
        "task_count": len(by_task),
    }


def build_export(
    source: Path,
    *,
    domain: str,
    suite_version: str,
) -> dict[str, Any]:
    """Turn one τ³-bench native report into generic scorecard input rows."""

    expected_domain = domain.strip()
    if not expected_domain:
        raise ValueError("domain is required")
    if not suite_version.strip():
        raise ValueError("suite_version is required")
    report, simulations, report_path, fingerprint, source_files = load_results(source)
    info = report.get("info")
    if not isinstance(info, Mapping):
        raise ValueError("τ³-bench results are missing the info object")
    commit = str(info.get("git_commit") or "")
    if not _COMMIT_RE.fullmatch(commit):
        raise ValueError("τ³-bench results are missing a hexadecimal info.git_commit")
    num_trials = info.get("num_trials")
    if isinstance(num_trials, bool) or not isinstance(num_trials, int) or num_trials <= 0:
        raise ValueError("τ³-bench results are missing a positive integer info.num_trials")
    native_domain = _native_domain(info)
    if expected_domain != native_domain:
        raise ValueError(
            f"τ³-bench native domain does not match --domain: {native_domain!r} != {expected_domain!r}"
        )
    expected_runs = _validate_complete_run(report, simulations, num_trials=num_trials)
    rows: list[dict[str, Any]] = []
    for index, simulation in enumerate(simulations):
        task_id = simulation.get("task_id")
        if task_id is None or not str(task_id):
            raise ValueError(f"τ³-bench simulation {index} is missing task_id")
        reward = _reward(simulation)
        duration = simulation.get("duration")
        row: dict[str, Any] = {
            "task_id": str(task_id),
            "family": native_domain,
            "verified_success": _is_native_success(reward),
            "native_reward": reward,
            "native_termination_reason": simulation.get("termination_reason"),
            "native_trial": simulation.get("trial"),
            "native_seed": simulation.get("seed"),
            "native_grader_success": _is_native_success(reward),
            "unobserved_by_tau3": [
                "protocol_valid",
                "trace_valid",
                "runtime_replay_agreement",
                "unsafe_attempt",
                "false_completion",
            ],
        }
        if isinstance(duration, (int, float)) and not isinstance(duration, bool) and math.isfinite(float(duration)):
            row["elapsed_seconds"] = float(duration)
        rows.append(row)
    native_metrics = _native_metrics(simulations)
    return {
        "schema": SCHEMA,
        "suite": SUITE,
        "suite_version": suite_version,
        "suite_commit": commit,
        "domain": native_domain,
        "native_grader": NATIVE_GRADER,
        "native_metric": "average_reward",
        "native_metric_value": native_metrics["average_reward"],
        "native_source": {
            "path": str(report_path),
            "sha256": fingerprint,
            "files": source_files,
        },
        "run": {
            "num_trials": num_trials,
            "max_steps": info.get("max_steps"),
            "max_errors": info.get("max_errors"),
            "seed": info.get("seed"),
            "agent": dict(info.get("agent_info") or {}),
            "user": dict(info.get("user_info") or {}),
            "environment": dict(info.get("environment_info") or {}),
        },
        "native_metrics": native_metrics,
        "complete": True,
        "expected_task_runs": expected_runs,
        "rows": rows,
        "claim_boundary": (
            "τ³-bench native reward is preserved as the primary metric. Action IR protocol, replay, false-completion, and safety metrics are unobserved unless separately joined from auditable harness logs."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="τ³-bench results.json file or its result directory")
    parser.add_argument("--domain", required=True, help="native τ³-bench domain for all rows")
    parser.add_argument("--suite-version", required=True, help="pinned τ³-bench package/release version")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = build_export(Path(args.results), domain=args.domain, suite_version=args.suite_version)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "complete": result["complete"],
                "native_metric": result["native_metric"],
                "native_metric_value": result["native_metric_value"],
                "task_runs": result["native_metrics"]["task_runs"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
