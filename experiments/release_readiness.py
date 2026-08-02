"""Build a machine-readable release and research readiness manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from experiments.wheel_smoke import source_tree_sha256

def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _artifact(path: Path) -> dict[str, Any]:
    digest = None
    if path.exists():
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
    return {"path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0, "sha256": digest}


def _package_version(root: Path) -> str | None:
    """Read the package version without requiring a TOML dependency."""
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"(?m)^version\s*=\s*[\"']([^\"']+)[\"']\s*$", text)
    return match.group(1) if match else None


def _current_wheel_smoke(
    results: Path,
    package_version: str | None,
    expected_source_package_sha256: str | None,
) -> tuple[Path, dict[str, Any] | None, str | None]:
    """Select smoke evidence only when it matches the wheel and source tree."""
    expected_wheel = (
        f"open_agent_harness_os-{package_version}-py3-none-any.whl"
        if package_version
        else None
    )
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(results.glob("clean-wheel-smoke-*.json")):
        report = _load(path)
        if (
            report is not None
            and report.get("passed") is True
            and report.get("wheel") == expected_wheel
            and report.get("source_package_sha256") == expected_source_package_sha256
            and report.get("wheel_package_sha256") == expected_source_package_sha256
            and report.get("source_matches_wheel") is True
            and report.get("console_scripts_match") is True
            and report.get("wheel_manifest_matches_reference") is True
            and report.get("wheel_manifest_sha256") == report.get("reference_wheel_manifest_sha256")
        ):
            candidates.append((path, report))
    if candidates:
        path, report = candidates[-1]
        return path, report, expected_wheel
    missing = results / f"clean-wheel-smoke-current-{package_version or 'unknown'}.json"
    return missing, None, expected_wheel


def _preflight_is_current(preflight: dict[str, Any] | None, expected_source_package_sha256: str | None) -> bool:
    """Accept preflight only after its source-matched wheel and full source suite pass."""

    if not (
        preflight
        and preflight.get("passed") is True
        and preflight.get("source_package_sha256") == expected_source_package_sha256
        and expected_source_package_sha256
    ):
        return False
    checks = {
        item.get("id"): item
        for item in preflight.get("checks", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    unit_tests = checks.get("unit_tests")
    wheel_smoke = checks.get("wheel_install_smoke")
    if not (unit_tests and unit_tests.get("passed") is True and wheel_smoke and wheel_smoke.get("passed") is True):
        return False
    detail = wheel_smoke.get("detail")
    return bool(
        isinstance(detail, dict)
        and detail.get("source_package_sha256") == expected_source_package_sha256
        and detail.get("wheel_package_sha256") == expected_source_package_sha256
        and detail.get("source_matches_wheel") is True
        and detail.get("console_scripts_match") is True
        and detail.get("wheel_manifest_matches_reference") is True
        and detail.get("wheel_manifest_sha256") == detail.get("reference_wheel_manifest_sha256")
    )


def _current_preflight(
    results: Path,
    expected_source_package_sha256: str | None,
) -> tuple[Path, dict[str, Any] | None]:
    """Select the newest source-bound launch preflight without a version pin."""

    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in results.glob("launch-preflight-v*.json"):
        match = re.fullmatch(r"launch-preflight-v(\d+)\.json", path.name)
        report = _load(path)
        if match and _preflight_is_current(report, expected_source_package_sha256):
            candidates.append((int(match.group(1)), path, report))
    if candidates:
        _, path, report = max(candidates, key=lambda item: item[0])
        return path, report
    return results / "launch-preflight-current.json", None


def build_readiness(root: Path) -> dict[str, Any]:
    results = root / "experiments" / "results"
    package_version = _package_version(root)
    source_fingerprint = source_tree_sha256(root)
    matrix_path = results / "research-project2-qwopus35-9b-promotion-greedy-v1.json"
    matrix_summary_path = results / "research-project2-qwopus35-9b-promotion-summary-v1.json"
    decision_path = results / "research-project2-qwopus35-9b-promotion-decision-v1.json"
    external_path = results / "research-project2-qwopus35-9b-external-bar-lite-v1.json"
    rl_gate_path = results / "verified-rl-gate-v2.json"
    wheel_smoke_path, wheel_smoke, expected_wheel = _current_wheel_smoke(
        results,
        package_version,
        source_fingerprint,
    )
    preflight_path, preflight = _current_preflight(results, source_fingerprint)
    matrix_summary = _load(matrix_summary_path)
    decision = _load(decision_path)
    rl_gate = _load(rl_gate_path)
    preflight_passed = _preflight_is_current(preflight, source_fingerprint)
    promotion_passed = bool(decision and decision.get("decision") == "promote" and decision.get("passed"))
    matrix_complete = matrix_path.exists()
    summary_aggregate = matrix_summary.get("aggregate", {}) if matrix_summary else {}
    matrix_summary_complete = bool(
        matrix_summary
        and summary_aggregate.get("task_rows") == 552
        and summary_aggregate.get("runs") == 9
        and summary_aggregate.get("promotion_decision") in {"promote", "reject"}
    )
    external_complete = external_path.exists()
    wheel_smoke_passed = bool(wheel_smoke and wheel_smoke.get("passed"))

    gates = {
        "local_developer_preview": {
            "status": "ready" if preflight_passed else "blocked",
            "evidence": str(preflight_path),
            "detail": (
                "preflight passed with a source-matched wheel and completed source suite"
                if preflight_passed
                else "preflight missing, incomplete, failed, or does not match the current source package"
            ),
        },
        "9b_frozen_matrix": {
            "status": "complete" if matrix_complete else ("context_only" if matrix_summary_complete else "pending"),
            "evidence": str(matrix_path if matrix_complete else matrix_summary_path),
            "detail": (
                "private raw matrix artifact exists"
                if matrix_complete
                else (
                    "private raw matrix is omitted; public sanitized summary records the historical 9B matrix"
                    if matrix_summary_complete
                    else "long-running matrix has not completed"
                )
            ),
        },
        "9b_promotion_gate": {
            "status": "passed" if promotion_passed else (
                "failed" if decision or summary_aggregate.get("promotion_decision") == "reject" else "pending"
            ),
            "evidence": str(decision_path if decision else matrix_summary_path),
            "detail": (
                decision.get("reason")
                if decision
                else (
                    "public sanitized summary records promotion_decision=reject; raw decision artifact is omitted"
                    if summary_aggregate.get("promotion_decision") == "reject"
                    else "decision artifact not available"
                )
            ),
        },
        "external_bar_lite": {
            "status": "complete" if external_complete else "pending",
            "evidence": str(external_path),
            "detail": "diagnostic artifact exists" if external_complete else "scheduled after frozen matrix",
        },
        "verified_rl_gate": {
            "status": "passed" if bool(rl_gate and rl_gate.get("passed")) else "pending",
            "evidence": str(rl_gate_path),
            "detail": "frozen integrity and diagnostics passed; capability promotion remains separate" if bool(rl_gate and rl_gate.get("passed")) else "RL waits for a complete, replay-valid, zero-unsafe frozen matrix and diagnostics",
        },
        "clean_wheel_smoke": {
            "status": "passed" if wheel_smoke_passed else "pending",
            "evidence": str(wheel_smoke_path),
            "detail": (
                f"fresh-target wheel smoke passed for {expected_wheel}"
                if wheel_smoke_passed
                else f"fresh-target wheel smoke for {expected_wheel or 'the current package'} has not passed"
            ),
        },
        "full_external_suite": {
            "status": "not_run",
            "evidence": "docs/NATIVE_EVALUATION_LAUNCHER.md",
            "detail": "the checkpoint-bound AgentDojo launcher is prepared; no native AgentDojo/TUA-Bench/OSWorld result exists yet",
        },
        "public_identity_operations": {
            "status": "open",
            "evidence": "docs/PRODUCT_LAUNCH_PLAN.md",
            "detail": "tenant isolation and local per-principal limits exist; production identity, distributed quotas, rotation, and operations remain open",
        },
        "usability_sessions": {
            "status": "open",
            "evidence": "docs/PRODUCT_LAUNCH_PLAN.md",
            "detail": "three representative workflow sessions remain required",
        },
        "licensing_provenance_review": {
            "status": "open",
            "evidence": "docs/PROVENANCE_REVIEW.md",
            "detail": "engineering inventory is recorded; model, base, dataset, distilled-trace, and dependency sign-off remains open",
        },
    }
    if promotion_passed and external_complete:
        research_status = "candidate_for_external_review"
    elif matrix_complete:
        research_status = "matrix_complete_external_review_pending"
    elif matrix_summary_complete:
        research_status = "historical_matrix_context_external_review_pending"
    else:
        research_status = "evaluation_pending"
    return {
        "schema": "release-readiness/v1",
        "scope": "paired-local-action-model-and-open-agent-harness-os",
        "generated_from": str(root),
        "package_version": package_version,
        "source_package_sha256": source_fingerprint,
        "status": {
            "developer_preview": "ready" if preflight_passed else "not_ready",
            "research": research_status,
            "public_launch": "not_ready",
        },
        "gates": gates,
        "artifacts": {
            "preflight": _artifact(preflight_path),
            "matrix": _artifact(matrix_path),
            "matrix_summary": _artifact(matrix_summary_path),
            "promotion_decision": _artifact(decision_path),
            "external_bar_lite": _artifact(external_path),
            "research_positioning": _artifact(root / "docs" / "RESEARCH_POSITIONING_REFRESH_2026-07-26.md"),
            "research_launch_one_pager": _artifact(root / "docs" / "RESEARCH_LAUNCH_ONE_PAGER_2026-07-26.md"),
            "license": _artifact(root / "LICENSE"),
            "notice": _artifact(root / "NOTICE"),
            "security_policy": _artifact(root / "SECURITY.md"),
            "verified_rl_gate": _artifact(rl_gate_path),
            "clean_wheel_smoke": _artifact(wheel_smoke_path),
        },
        "allowed_claims": [
            "The local developer-preview surface passes its documented preflight scope.",
            "The harness provides typed actions, authority checks, independent evidence, and replay.",
            "The historical Qwopus branch completed SFT and merge; the active clean-split candidate is evaluated separately.",
        ],
        "unsupported_claims": [
            "The 9B branch beats the promoted 7B until the frozen gate passes.",
            "The system is generally capable on terminal/computer-use work.",
            "The product is production-ready or safe against all possible tools/content.",
        ],
        "next_actions": [
            (
                "Complete and independently audit any new 9B rerun; the public sanitized summary is historical context."
                if matrix_summary_complete and not matrix_complete
                else "Complete and independently audit the 9B frozen matrix."
            ),
            "Execute the checkpoint-bound AgentDojo plan after the clean candidate is merged, then publish native utility/security metrics and logs.",
            "Run verifier-backed RL only after frozen integrity/diagnostic evidence passes, with a held-out control and decomposed rewards; keep capability promotion separate.",
            "Close external-suite, usability, identity/operations, security, and licensing gates before public launch.",
        ],
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Release readiness manifest",
        "",
        f"- Developer preview: **{report['status']['developer_preview']}**",
        f"- Research status: **{report['status']['research']}**",
        f"- Public launch: **{report['status']['public_launch']}**",
        "",
        "| Gate | Status | Evidence | Detail |",
        "|:---|:---|:---|:---|",
    ]
    for name, gate in report["gates"].items():
        lines.append(f"| {name} | {gate['status']} | `{gate['evidence']}` | {gate['detail']} |")
    lines.extend(["", "## Next actions", ""])
    lines.extend(f"- {item}" for item in report["next_actions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args()
    report = build_readiness(Path(args.project_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown = Path(args.markdown_output)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(to_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps(report["status"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
