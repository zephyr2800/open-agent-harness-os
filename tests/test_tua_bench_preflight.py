from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.tua_bench_preflight import REQUIRED_CHECKOUT_PATHS, build_preflight


_PINNED_COMMIT = "a" * 40


def _git_clean(_: Path, args: tuple[str, ...]) -> tuple[int, str, str]:
    if args == ("rev-parse", "HEAD"):
        return 0, "a" * 40, ""
    if args == ("status", "--porcelain"):
        return 0, "", ""
    raise AssertionError(args)


def _git_dirty(_: Path, args: tuple[str, ...]) -> tuple[int, str, str]:
    if args == ("rev-parse", "HEAD"):
        return 0, "b" * 40, ""
    if args == ("status", "--porcelain"):
        return 0, " M README.md", ""
    raise AssertionError(args)


class TuaBenchPreflightTests(unittest.TestCase):
    def _checkout(self, root: Path) -> None:
        for name in REQUIRED_CHECKOUT_PATHS:
            path = root / name
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)

    def test_host_preflight_accepts_clean_checkout_and_explicit_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._checkout(root)
            asset = root / "generated" / "fixture.bin"
            asset.parent.mkdir()
            asset.write_bytes(b"fixture")
            report = build_preflight(
                root,
                expected_commit=_PINNED_COMMIT,
                required_assets=["generated/fixture.bin"],
                command_lookup=lambda name: f"C:/tools/{name}.exe",
                git_runner=_git_clean,
            )
        self.assertTrue(report["passed"])
        self.assertEqual(report["status"], "host_ready_for_manual_native_setup")
        self.assertEqual(report["execution_boundary"]["native_benchmark_result"], "not_run")
        self.assertEqual(report["execution_boundary"]["native_agent_integration"], "not_implemented_by_this_preflight")

    def test_host_preflight_requires_container_backend_uv_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._checkout(root)
            report = build_preflight(
                root,
                expected_commit=_PINNED_COMMIT,
                command_lookup=lambda _: None,
                git_runner=_git_clean,
            )
        checks = {item["id"]: item for item in report["checks"]}
        self.assertFalse(report["passed"])
        self.assertFalse(checks["container_backend"]["passed"])
        self.assertFalse(checks["uv_command"]["passed"])
        self.assertFalse(checks["required_assets"]["passed"])

    def test_host_preflight_rejects_dirty_or_incomplete_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._checkout(root)
            report = build_preflight(
                root,
                expected_commit="b" * 40,
                required_assets=["README.md"],
                command_lookup=lambda name: "podman" if name == "podman" else "uv",
                git_runner=_git_dirty,
            )
            (root / "uv.lock").unlink()
            incomplete = build_preflight(
                root,
                expected_commit=_PINNED_COMMIT,
                required_assets=["README.md"],
                command_lookup=lambda name: "podman" if name == "podman" else "uv",
                git_runner=_git_clean,
            )
        dirty = next(item for item in report["checks"] if item["id"] == "tua_checkout")
        missing = next(item for item in incomplete["checks"] if item["id"] == "tua_checkout")
        self.assertFalse(dirty["passed"])
        self.assertFalse(dirty["detail"]["clean"])
        self.assertFalse(missing["passed"])
        self.assertEqual(missing["detail"]["missing_paths"], ["uv.lock"])

    def test_host_preflight_rejects_assets_outside_the_pinned_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "checkout"
            root.mkdir()
            self._checkout(root)
            unrelated = base / "unrelated-asset.bin"
            unrelated.write_bytes(b"not a checkout asset")
            report = build_preflight(
                root,
                expected_commit=_PINNED_COMMIT,
                required_assets=[unrelated],
                command_lookup=lambda name: f"C:/tools/{name}.exe",
                git_runner=_git_clean,
            )
        assets = next(item for item in report["checks"] if item["id"] == "required_assets")
        self.assertFalse(report["passed"])
        self.assertFalse(assets["passed"])
        self.assertEqual(assets["detail"]["outside_checkout_paths"], [str(unrelated.resolve())])

    def test_host_preflight_requires_a_matching_full_commit_pin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._checkout(root)
            asset = root / "generated" / "fixture.bin"
            asset.parent.mkdir()
            asset.write_bytes(b"fixture")
            mismatch = build_preflight(
                root,
                expected_commit="b" * 40,
                required_assets=[asset],
                command_lookup=lambda name: f"C:/tools/{name}.exe",
                git_runner=_git_clean,
            )
            omitted = build_preflight(
                root,
                required_assets=[asset],
                command_lookup=lambda name: f"C:/tools/{name}.exe",
                git_runner=_git_clean,
            )
        mismatch_checkout = next(item for item in mismatch["checks"] if item["id"] == "tua_checkout")
        omitted_checkout = next(item for item in omitted["checks"] if item["id"] == "tua_checkout")
        self.assertFalse(mismatch["passed"])
        self.assertFalse(mismatch_checkout["detail"]["commit_matches_expected"])
        self.assertTrue(mismatch_checkout["detail"]["expected_commit_valid"])
        self.assertFalse(omitted["passed"])
        self.assertFalse(omitted_checkout["detail"]["expected_commit_valid"])


if __name__ == "__main__":
    unittest.main()
