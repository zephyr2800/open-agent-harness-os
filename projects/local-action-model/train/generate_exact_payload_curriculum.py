"""Generate verifier-backed examples for exact artifact payload fidelity.

The Qwopus 9B exploratory matrix exposed a narrow failure mode: the policy
performed the requested write, but appended a state digest to the file and
therefore failed an exact-content verifier.  This curriculum makes that
boundary explicit while keeping the digest in runtime metadata, not in the
artifact payload.  Paths, values, and task ids are synthetic and disjoint
from the research and industry holdouts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .generate_action_curriculum_v1 import _act, _envelope, _state
except ImportError:  # pragma: no cover - supports direct script execution
    from generate_action_curriculum_v1 import _act, _envelope, _state


PREFIXES = (
    "",
    "In the bounded local workspace, ",
    "Follow the exact payload contract: ",
    "Use only the requested content and wait for independent verification: ",
    "Treat state metadata as verifier context, never as file content: ",
)


CASES = (
    ("payload-cfg-00", "release_mode.cfg", "mode=sealed-alpha", "Write"),
    ("payload-cfg-01", "region_note.cfg", "region=local-west", "Create"),
    ("payload-cfg-02", "tier_marker.cfg", "tier=research", "Persist"),
    ("payload-ini-03", "cache_policy.ini", "cache=disabled", "Save"),
    ("payload-ini-04", "worker_state.ini", "workers=4", "Write"),
    ("payload-txt-05", "handoff_note.txt", "handoff=approved", "Create"),
    ("payload-txt-06", "checkpoint_note.txt", "checkpoint=green", "Persist"),
    ("payload-md-07", "launch_marker.md", "launch-marker-v2", "Write"),
    ("payload-md-08", "operator_note.md", "operator=local", "Create"),
    ("payload-json-09", "status_record.json", '{"status":"ready"}', "Write"),
    ("payload-json-10", "version_record.json", '{"version":3}', "Create"),
    ("payload-toml-11", "profile_record.toml", "profile = \"offline\"", "Persist"),
)


def _evidence(task_id: str) -> tuple[str, dict[str, Any]]:
    evidence_id = "sha256:" + hashlib.sha256(f"exact-payload:{task_id}".encode()).hexdigest()
    return evidence_id, {
        "evidence_id": evidence_id,
        "status": "verified",
        "claim": "write_file completed with an exact byte-for-byte payload",
    }


def _input_state(task_id: str, tools: list[str], step: int, *, evidence: list[dict[str, Any]] | None = None, verified: list[str] | None = None, artifacts: list[str] | None = None) -> dict[str, Any]:
    state = _state(
        tools,
        step,
        executed=["write_file"] if step else [],
        verified=verified,
        evidence=evidence,
        artifacts=artifacts,
        expected_tool="write_file",
        required_tools=["write_file"],
    )
    state["task_id"] = task_id
    state["state_digest"] = "sha256:" + hashlib.sha256(f"runtime-state:{task_id}:{step}".encode()).hexdigest()
    state["facts"] = [
        "state_digest is verifier metadata and must never be copied into artifact content",
        "the requested payload is exact and must not receive labels, metadata, or extra lines",
    ]
    return state


def _row(task_id: str, prompt: str, state: dict[str, Any], target: dict[str, Any], style: int) -> dict[str, Any]:
    return {
        "schema": "action-sft/v0",
        "task_id": task_id,
        "input": {
            "task_id": task_id,
            "goal": PREFIXES[style] + prompt,
            "state": state,
            "available_tools": ["write_file", "abstain", "finish"],
            "token_budget": 1800,
        },
        "target": target,
        "provenance": {
            "source": "synthetic_exact_payload_fidelity_v1",
            "synthetic": True,
            "trajectory_verified": True,
            "sampling_stratum": "exact_payload_fidelity",
            "sampling_weight": 10.0,
            "state_digest_present": True,
            "holdout_excluded": "research-v4;research-v2;industry-proxy-v1;industry-proxy-v2;external-bar-lite-v1;external-bar-lite-v2",
            "augmentation_index": style,
        },
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id, path, content, verb in CASES:
        for style in range(len(PREFIXES)):
            task_id = f"{case_id}-s{style}"
            prompt = (
                f"{verb} {path} with exactly this content and nothing else: {content}. "
                "Do not append a state digest, labels, Markdown fences, metadata, or an extra newline."
            )
            start = _input_state(task_id, ["write_file"], 0)
            target = _act(task_id, 0, start, "write_file", {"path": path, "content": content})
            rows.append(_row(task_id, prompt, start, target, style))

            evidence_id, evidence = _evidence(task_id)
            finish = _input_state(
                task_id,
                ["write_file"],
                1,
                evidence=[evidence],
                verified=[evidence_id],
                artifacts=[path],
            )
            rows.append(_row(task_id, prompt, finish, _envelope(task_id, 1, "finish", finish), style))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = build_rows()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    output.write_text(raw, encoding="utf-8", newline="\n")
    print(json.dumps({
        "schema": "action-sft/v0",
        "examples": len(rows),
        "cases": len(CASES),
        "styles": len(PREFIXES),
        "output": str(output),
        "sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "sampling_stratum": "exact_payload_fidelity",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
