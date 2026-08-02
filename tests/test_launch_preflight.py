from __future__ import annotations

import base64
import hashlib
import io
import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from experiments.launch_preflight import _redact_public_log, _wheel_check
from experiments.wheel_smoke import _source_console_scripts, source_tree_sha256, wheel_manifest_sha256, wheel_source_tree_sha256


class LaunchPreflightTests(unittest.TestCase):
    def test_public_build_logs_redact_user_home_paths(self) -> None:
        windows_path = "C:" + "\\" + "Users" + "\\" + "alice\\cache\\wheel.whl"
        output = _redact_public_log(windows_path + "\n/home/bob/build.log")
        self.assertNotIn("alice", output)
        self.assertNotIn("bob", output)
        self.assertIn("<user-home>", output)

    def test_source_console_scripts_parse_project_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                "[project.scripts]\n"
                'alpha-tool = "alpha.cli:main"\n'
                "beta_tool = 'beta.cli:main'\n"
                "\n"
                "[tool.setuptools]\n"
                "include-package-data = false\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _source_console_scripts(root),
                ("alpha-tool = alpha.cli:main", "beta_tool = beta.cli:main"),
            )

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
                    "experiments/agentdojo_adapter_server.py",
                    "experiments/launch_preflight.py",
                    "demo-0.0.0.dist-info/METADATA",
                    "demo-0.0.0.dist-info/WHEEL",
                    "demo-0.0.0.dist-info/licenses/LICENSE",
                    "demo-0.0.0.dist-info/licenses/NOTICE",
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
        self.assertTrue(result["detail"]["license_notice_present"])
        self.assertTrue(result["detail"]["record_hashes_valid"])

    def test_wheel_check_requires_license_and_notice_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing-license.whl"
            with zipfile.ZipFile(path, "w") as archive:
                members = (
                    "app/__init__.py",
                    "app/cli.py",
                    "experiments/agentdojo_adapter_server.py",
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
        self.assertFalse(result["passed"])
        self.assertFalse(result["detail"]["license_notice_present"])

    def test_wheel_check_rejects_bytecode_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bytecode.whl"
            with zipfile.ZipFile(path, "w") as archive:
                members = (
                    "app/__init__.py",
                    "app/cli.py",
                    "experiments/launch_preflight.py",
                    "app/__pycache__/cli.cpython-312.pyc",
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
        self.assertFalse(result["passed"])
        self.assertFalse(result["detail"]["bytecode_free"])
        self.assertEqual(result["detail"]["bytecode_entries"], 1)

    def test_package_source_fingerprint_ignores_prior_result_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "experiments" / "results").mkdir(parents=True)
            (root / "app" / "cli.py").write_text("print('a')\n", encoding="utf-8")
            baseline = source_tree_sha256(root)
            (root / "experiments" / "results" / "old.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(source_tree_sha256(root), baseline)
            (root / "app" / "cli.py").write_text("print('b')\n", encoding="utf-8")
            self.assertNotEqual(source_tree_sha256(root), baseline)

    def test_wheel_package_fingerprint_matches_equivalent_source_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "experiments").mkdir()
            (root / "app" / "cli.py").write_text("print('a')\n", encoding="utf-8")
            (root / "experiments" / "agentdojo_adapter_server.py").write_text("VALUE = 1\n", encoding="utf-8")
            wheel = root / "fixture.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("app/cli.py", "print('a')\n")
                archive.writestr("experiments/agentdojo_adapter_server.py", "VALUE = 1\n")
            self.assertEqual(source_tree_sha256(root), wheel_source_tree_sha256(wheel))
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("app/cli.py", "print('b')\n")
                archive.writestr("experiments/agentdojo_adapter_server.py", "VALUE = 1\n")
            self.assertNotEqual(source_tree_sha256(root), wheel_source_tree_sha256(wheel))

    def test_wheel_manifest_fingerprint_includes_metadata_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.whl"
            second = root / "second.whl"
            for wheel, metadata in ((first, "Name: demo\nRequires-Dist: safe\n"), (second, "Name: demo\nRequires-Dist: altered\n")):
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr("app/cli.py", "print('a')\n")
                    archive.writestr("demo-0.0.0.dist-info/METADATA", metadata)
                    archive.writestr("demo-0.0.0.dist-info/RECORD", "")
            self.assertNotEqual(wheel_manifest_sha256(first), wheel_manifest_sha256(second))


if __name__ == "__main__":
    unittest.main()
