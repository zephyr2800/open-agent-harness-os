"""Generate a fresh exact-payload holdout for the Qwopus correction ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CASES = (
    ("exact-holdout-00", "eval_contract_00.cfg", "contract=sealed-h0", "write"),
    ("exact-holdout-01", "eval_region_01.cfg", "region=local-north-h1", "create"),
    ("exact-holdout-02", "eval_policy_02.cfg", "policy=verify-h2", "persist"),
    ("exact-holdout-03", "eval_queue_03.ini", "queue=bounded-h3", "write"),
    ("exact-holdout-04", "eval_workers_04.ini", "workers=6", "create"),
    ("exact-holdout-05", "eval_handoff_05.txt", "handoff=approved-h5", "save"),
    ("exact-holdout-06", "eval_checkpoint_06.txt", "checkpoint=green-h6", "persist"),
    ("exact-holdout-07", "eval_marker_07.md", "marker=launch-h7", "write"),
    ("exact-holdout-08", "eval_operator_08.md", "operator=bounded-h8", "create"),
    ("exact-holdout-09", "eval_status_09.json", '{"status":"ready-h9"}', "write"),
    ("exact-holdout-10", "eval_version_10.json", '{"version":10}', "create"),
    ("exact-holdout-11", "eval_profile_11.toml", 'profile = "offline-h11"', "persist"),
    ("exact-holdout-12", "eval_release_12.cfg", "release=local-h12", "write"),
    ("exact-holdout-13", "eval_scope_13.txt", "scope=sandbox-h13", "save"),
    ("exact-holdout-14", "eval_state_14.ini", "state=clean-h14", "create"),
    ("exact-holdout-15", "eval_build_15.cfg", "build=launch-h15", "persist"),
)


PROMPT_STYLES = (
    "{verb} {path} with exactly this text: {content}",
    "The complete content of {path} must be {content}; do not add anything else.",
    "Use the registered write capability to put only {content} in {path}.",
    "Follow the exact requested contract: save {path} as the literal payload {content}.",
)


def build_spec() -> dict:
    tasks = []
    for index, (case_id, path, content, verb) in enumerate(CASES):
        style = PROMPT_STYLES[index % len(PROMPT_STYLES)]
        tasks.append({
            "task_id": case_id,
            "prompt": style.format(verb=verb.capitalize(), path=path, content=content),
            "split": "independent_exact_payload_holdout_v1",
            "available_tools": ["write_file"],
            "expected_kind": "finish",
            "family": "exact_write",
            "difficulty": "payload_fidelity",
            "adversarial": False,
            "expected_tool": "write_file",
            "expected_arguments": {"path": path, "content": content},
            "expected_files": {path: content},
        })
    spec = {
        "schema": "harness-task-spec/v0",
        "version": "exact-payload-holdout-v1-16-independent",
        "provenance": {
            "training_overlap": "none by construction; fresh paths and values",
            "authoring": "deterministic payload-fidelity holdout generator",
            "purpose": "causal evaluation of exact-content SFT correction",
            "task_count": len(tasks),
            "families": ["exact_write"],
        },
        "tasks": tasks,
    }
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spec = build_spec()
    raw = json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(raw, encoding="utf-8", newline="\n")
    print(json.dumps({
        "schema": spec["schema"],
        "version": spec["version"],
        "task_count": len(spec["tasks"]),
        "output": str(output),
        "sha256": hashlib.sha256(raw.encode()).hexdigest(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
