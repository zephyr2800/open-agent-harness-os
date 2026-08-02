from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.source_tree import record_source_tree


class SourceTreeTests(unittest.TestCase):
    def test_rejects_a_symlinked_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            outside = Path(directory) / "outside.py"
            outside.write_text("VALUE = 'outside'\n", encoding="utf-8")
            linked = root / "linked.py"
            try:
                linked.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"symlinks are unavailable in this environment: {error}")
            with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                record_source_tree(root)


if __name__ == "__main__":
    unittest.main()
