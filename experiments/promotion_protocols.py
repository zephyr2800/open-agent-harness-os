"""Versioned frozen task-spec sets for promotion and research RL.

The protocol name is evidence, not a convenience flag.  It records exactly
which immutable local slices a candidate had to satisfy, so a legacy result
can remain reproducible without silently changing the bar for later models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from experiments.data_split_audit import REQUIRED_FROZEN_FIXTURE_HASHES, task_spec_sha256


DEFAULT_PROMOTION_PROTOCOL = "v1"

# v1 is retained for interpretation of already-published evidence.  Its v1
# industry proxy is deliberately *not* the active protocol because the clean
# SFT mixture's affinity audit identified it as template-adjacent.  v2 replaces
# that slice with the post-freeze author holdout, whose direct and affinity
# audits pass against the clean training mixture.
PROMOTION_PROTOCOLS = {
    "v1": {
        "description": "Legacy three-slice protocol retained for historical reproducibility.",
        "slices": {
            "task-spec-research-v4.json": "research_v4",
            "task-spec-industry-proxy-v1.json": "industry_proxy_v1",
            "task-spec-industry-proxy-v2.json": "industry_proxy_v2",
        },
    },
    "v2": {
        "description": "Active protocol with the post-freeze author holdout replacing the high-affinity v1 proxy.",
        "slices": {
            "task-spec-research-v4.json": "research_v4",
            "task-spec-industry-proxy-v2.json": "industry_proxy_v2",
            "task-spec-author-holdout-v1.json": "author_holdout_v1",
        },
    },
}


def protocol_names() -> tuple[str, ...]:
    """Return the accepted protocol names in stable CLI/help order."""

    return tuple(PROMOTION_PROTOCOLS)


def _protocol(protocol: str) -> dict[str, Any]:
    try:
        return PROMOTION_PROTOCOLS[protocol]
    except KeyError as error:
        choices = ", ".join(protocol_names())
        raise ValueError(f"unknown promotion protocol {protocol!r}; choose one of: {choices}") from error


def protocol_slices(protocol: str) -> dict[str, str]:
    """Return the immutable task-spec basename -> reporting-slice mapping."""

    return dict(_protocol(protocol)["slices"])


def protocol_task_spec_hashes(protocol: str) -> dict[str, str]:
    """Return the exact fixture hashes required by one protocol."""

    slices = protocol_slices(protocol)
    missing = sorted(name for name in slices if name not in REQUIRED_FROZEN_FIXTURE_HASHES)
    if missing:
        raise RuntimeError(f"protocol {protocol!r} references unpinned fixtures: {', '.join(missing)}")
    return {name: REQUIRED_FROZEN_FIXTURE_HASHES[name] for name in slices}


def validate_protocol_task_specs(task_specs: list[Path], protocol: str) -> dict[str, Any]:
    """Fail closed unless supplied files are exactly the named protocol set."""

    expected_hashes = protocol_task_spec_hashes(protocol)
    observed: dict[str, list[str | None]] = {}
    for path in task_specs:
        try:
            digest: str | None = task_spec_sha256(path)
        except OSError:
            digest = None
        observed.setdefault(path.name, []).append(digest)
    missing = sorted(name for name in expected_hashes if name not in observed)
    unexpected = sorted(name for name in observed if name not in expected_hashes)
    duplicates = sorted(name for name, values in observed.items() if len(values) != 1)
    mismatches = [
        name
        for name, expected in expected_hashes.items()
        if name in observed and (len(observed[name]) != 1 or observed[name][0] != expected)
    ]
    return {
        "promotion_protocol": protocol,
        "expected_hashes": expected_hashes,
        "observed_hashes": observed,
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
        "mismatches": mismatches,
        "passed": not missing and not unexpected and not duplicates and not mismatches,
    }
