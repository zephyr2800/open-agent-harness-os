from __future__ import annotations

import unittest
from pathlib import Path

from experiments.promotion_protocols import (
    DEFAULT_PROMOTION_PROTOCOL,
    protocol_slices,
    validate_protocol_task_specs,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "benchmarks" / "fixtures"


class PromotionProtocolTests(unittest.TestCase):
    def test_v2_accepts_only_the_audited_active_fixture_set(self) -> None:
        paths = [FIXTURES / name for name in protocol_slices("v2")]
        report = validate_protocol_task_specs(paths, "v2")
        self.assertTrue(report["passed"])
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unexpected"], [])

    def test_v2_rejects_the_legacy_proxy_in_place_of_the_author_holdout(self) -> None:
        paths = [
            FIXTURES / "task-spec-research-v4.json",
            FIXTURES / "task-spec-industry-proxy-v1.json",
            FIXTURES / "task-spec-industry-proxy-v2.json",
        ]
        report = validate_protocol_task_specs(paths, "v2")
        self.assertFalse(report["passed"])
        self.assertEqual(report["missing"], ["task-spec-author-holdout-v1.json"])
        self.assertEqual(report["unexpected"], ["task-spec-industry-proxy-v1.json"])

    def test_v1_remains_available_for_historical_artifacts(self) -> None:
        paths = [FIXTURES / name for name in protocol_slices(DEFAULT_PROMOTION_PROTOCOL)]
        self.assertTrue(validate_protocol_task_specs(paths, DEFAULT_PROMOTION_PROTOCOL)["passed"])
