import json
import unittest
from pathlib import Path


class ReferenceSFTTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_bootstrap_fixture_is_complete_and_marked_synthetic(self):
        path = self.ROOT / "fixtures" / "training" / "action-sft-v0.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["schema"] == "action-sft/v0" for row in rows))
        self.assertTrue(all(row["provenance"]["synthetic"] is True for row in rows))
        self.assertTrue(all(row["target"]["schema"] == "action-ir/v0" for row in rows))
