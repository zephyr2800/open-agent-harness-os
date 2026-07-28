import unittest
from pathlib import Path

from train.generate_exact_payload_curriculum import build_rows as build_exact_payload_rows
from train.transformers_sft import load_examples, tokenized_examples


class FakeTokenizer:
    eos_token = "<eos>"
    pad_token_id = 0

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return " | ".join(message["content"] for message in messages)

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": list(range(max(1, len(text) // 20)))}


class SFTTrainingTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_tokenization_masks_prompt_and_keeps_target_labels(self):
        examples = load_examples(self.ROOT / "fixtures" / "training" / "action-sft-v0.jsonl")[:1]
        rows = tokenized_examples(FakeTokenizer(), examples, max_length=128)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["labels"][0] == -100)
        self.assertTrue(any(label != -100 for label in rows[0]["labels"]))
        self.assertLessEqual(len(rows[0]["input_ids"]), 128)

    def test_exact_payload_curriculum_separates_digest_metadata_from_content(self):
        rows = build_exact_payload_rows()
        actions = [row for row in rows if row["target"]["kind"] == "act"]
        finishes = [row for row in rows if row["target"]["kind"] == "finish"]
        self.assertEqual(len(rows), 120)
        self.assertEqual(len(actions), 60)
        self.assertEqual(len(finishes), 60)
        self.assertTrue(all(row["input"]["state"].get("state_digest") for row in rows))
        self.assertTrue(all(row["target"]["finish"]["evidence"] for row in finishes))
        self.assertTrue(all(
            "STATE_DIGEST" not in str(row["target"]["action"]["arguments"]["content"])
            for row in actions
        ))
