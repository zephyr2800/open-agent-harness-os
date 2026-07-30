"""Build a machine-readable release and research readiness manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


def build_readiness(root: Path) -> dict[str, Any]:
    results = root / "experiments" / "results"
    preflight_path = results / "launch-preflight-v4.json"
    matrix_path = results / "research-project2-qwopus35-9b-promotion-greedy-v1.json"
    decision_path = results / "research-project2-qwopus35-9b-promotion-decision-v1.json"
    external_path = results / "research-project2-qwopus35-9b-external-bar-lite-v1.json"
    rl_gate_path = results / "verified-rl-gate-v2.json"
    wheel_smoke_path = results / "clean-wheel-smoke-v2.json"
    preflight = _load(preflight_path)
    decision = _load(decision_path)
    rl_gate = _load(rl_gate_path)
    preflight_passed = bool(preflight and preflight.get("passed"))
    promotion_passed = bool(decision and decision.get("decision") == "promote" and decision.get("passed"))
    matrix_complete = matrix_path.exists()
    external_complete = external_path.exists()

    gates = {
        "local_developer_preview": {
            "status": "ready" if preflight_passed else "blocked",
            "evidence": str(preflight_path),
            "detail": "preflight passed" if preflight_passed else "preflight missing or failed",
        },
        "9b_frozen_matrix": {
            "status": "complete" if matrix_complete else "pending",
            "evidence": str(matrix_path),
            "detail": "matrix artifact exists" if matrix_complete else "long-running matrix has not completed",
        },
        "9b_promotion_gate": {
            "status": "passed" if promotion_passed else ("pending" if not decision else "failed"),
            "evidence": str(decision_path),
            "detail": decision.get("reason") if decision else "decision artifact not available",
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
            "status": "passed" if bool(_load(wheel_smoke_path) and _load(wheel_smoke_path).get("passed")) else "pending",
            "evidence": str(wheel_smoke_path),
            "detail": "fresh-target wheel smoke passed" if bool(_load(wheel_smoke_path) and _load(wheel_smoke_path).get("passed")) else "fresh-target wheel smoke has not passed",
        },
        "full_external_suite": {
            "status": "not_run",
            "evidence": "docs/EXTERNAL_BAR_UPDATE_2026-07-26.md",
            "detail": "external-bar-lite is a local diagnostic, not TUA-Bench/OSWorld/AgentDojo certification",
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
    else:
        research_status = "evaluation_pending"
    return {
        "schema": "release-readiness/v1",
        "scope": "paired-local-action-model-and-open-agent-harness-os",
        "generated_from": str(root),
        "status": {
            "developer_preview": "ready" if preflight_passed else "not_ready",
            "research": research_status,
            "public_launch": "not_ready",
        },
        "gates": gates,
        "artifacts": {
            "preflight": _artifact(preflight_path),
            "matrix": _artifact(matrix_path),
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
            "The Qwopus branch has completed SFT and merge; evaluation is separate from that training claim.",
        ],
        "unsupported_claims": [
            "The 9B branch beats the promoted 7B until the frozen gate passes.",
            "The system is generally capable on terminal/computer-use work.",
            "The product is production-ready or safe against all possible tools/content.",
        ],
        "next_actions": [
            "Complete and independently audit the 9B frozen matrix.",
            "Run and summarize the disjoint external-bar-lite diagnostic.",
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
