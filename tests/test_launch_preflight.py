from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from experiments.launch_preflight import _wheel_check


class LaunchPreflightTests(unittest.TestCase):
    def test_wheel_check_rejects_non_wheel_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-a-wheel.whl"
            path.write_text("not a zip", encoding="utf-8")
            result = _wheel_check(path)
        self.assertFalse(result["passed"])
        self.assertFalse(result["detail"]["zipfile"])

    def test_wheel_check_requires_modules_and_dist_info(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "minimal.whl"
            with zipfile.ZipFile(path, "w") as archive:
                for name in (
                    "app/__init__.py",
                    "app/cli.py",
                    "experiments/launch_preflight.py",
                    "demo-0.0.0.dist-info/METADATA",
                    "demo-0.0.0.dist-info/WHEEL",
                    "demo-0.0.0.dist-info/RECORD",
                ):
                    archive.writestr(name, "")
            result = _wheel_check(path)
        self.assertTrue(result["passed"])
        self.assertTrue(result["detail"]["wheel_metadata_present"])


if __name__ == "__main__":
    unittest.main()
