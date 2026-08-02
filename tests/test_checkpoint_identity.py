from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.checkpoint_identity import record_checkpoint_identity, verify_checkpoint_identity_manifest


class CheckpointIdentityTests(unittest.TestCase):
    def _identity_fixture(self, root: Path) -> tuple[Path, Path]:
        checkpoint = root / "checkpoint"
        checkpoint.mkdir()
        (checkpoint / "config.json").write_text("{}\n", encoding="utf-8")
        (checkpoint / "model.safetensors").write_bytes(b"original-weights")
        identity = record_checkpoint_identity(checkpoint, model_id=str(checkpoint), revision="main")
        manifest = root / "identity.json"
        manifest.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return checkpoint, manifest

    def test_verifies_matching_checkpoint_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint, manifest = self._identity_fixture(Path(temporary))
            verified = verify_checkpoint_identity_manifest(
                manifest,
                model_id=str(checkpoint),
                revision="main",
                checkpoint_path=checkpoint,
            )
        self.assertEqual(verified["schema"], "checkpoint-identity/v1")
        self.assertEqual(verified["file_count"], 2)

    def test_rejects_checkpoint_content_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint, manifest = self._identity_fixture(Path(temporary))
            (checkpoint / "model.safetensors").write_bytes(b"mutated-weights")
            with self.assertRaisesRegex(ValueError, "does not match"):
                verify_checkpoint_identity_manifest(
                    manifest,
                    model_id=str(checkpoint),
                    revision="main",
                    checkpoint_path=checkpoint,
                )


if __name__ == "__main__":
    unittest.main()
