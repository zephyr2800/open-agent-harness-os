from __future__ import annotations

import base64
import hashlib
import io
import csv
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
                members = (
                    "app/__init__.py",
                    "app/cli.py",
                    "experiments/launch_preflight.py",
                    "demo-0.0.0.dist-info/METADATA",
                    "demo-0.0.0.dist-info/WHEEL",
                )
                for name in members:
                    archive.writestr(name, "")
                record_name = "demo-0.0.0.dist-info/RECORD"
                record = io.StringIO()
                writer = csv.writer(record, lineterminator="\n")
                encoded = base64.urlsafe_b64encode(hashlib.sha256(b"").digest()).rstrip(b"=").decode("ascii")
                for name in members:
                    writer.writerow((name, f"sha256={encoded}", "0"))
                writer.writerow((record_name, "", ""))
                archive.writestr(record_name, record.getvalue())
            result = _wheel_check(path)
        self.assertTrue(result["passed"])
        self.assertTrue(result["detail"]["wheel_metadata_present"])
        self.assertTrue(result["detail"]["record_hashes_valid"])


if __name__ == "__main__":
    unittest.main()
