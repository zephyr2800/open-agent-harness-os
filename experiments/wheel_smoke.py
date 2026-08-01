"""Install a wheel into a fresh target and run the dependency-free smoke."""

from __future__ import annotations

import argparse
from configparser import ConfigParser
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


_PACKAGE_SOURCE_DIRS = (
    "app",
    "protocol",
    "runtime",
    "tools",
    "memory",
    "traces",
    "adapters",
    "search",
    "improve",
    "benchmarks",
    "experiments",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _python_source_sha256(content: bytes) -> str:
    """Hash module bytes after normalizing checkout-only line ending differences."""

    return hashlib.sha256(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def _package_digest(entries: list[tuple[str, str]]) -> str | None:
    """Hash relative package paths and their content hashes deterministically."""

    if not entries:
        return None
    digest = hashlib.sha256()
    for relative, content_sha256 in sorted(entries):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content_sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def source_tree_sha256(root: Path) -> str | None:
    """Fingerprint source package modules with an algorithm comparable to a wheel.

    The digest intentionally contains only importable package ``.py`` modules.
    It can therefore be recomputed over a wheel archive, unlike a generic
    source-tree digest that also includes packaging inputs and generated files.
    """

    if not root.is_dir():
        return None
    entries: list[tuple[str, str]] = []
    for package in _PACKAGE_SOURCE_DIRS:
        directory = root / package
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            relative = path.relative_to(root)
            if "__pycache__" not in relative.parts:
                entries.append((relative.as_posix(), _python_source_sha256(path.read_bytes())))
    return _package_digest(entries)


def wheel_source_tree_sha256(wheel: Path) -> str | None:
    """Fingerprint importable package modules stored in ``wheel``."""

    if not wheel.is_file():
        return None
    entries: list[tuple[str, str]] = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            path = PurePosixPath(name)
            if (
                path.suffix == ".py"
                and path.parts
                and path.parts[0] in _PACKAGE_SOURCE_DIRS
                and "__pycache__" not in path.parts
            ):
                entries.append((name, _python_source_sha256(archive.read(name))))
    return _package_digest(entries)


def wheel_manifest_sha256(wheel: Path) -> str | None:
    """Fingerprint every wheel member and its raw content, including metadata."""

    if not wheel.is_file():
        return None
    entries: list[tuple[str, str]] = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            entries.append((name, hashlib.sha256(archive.read(name)).hexdigest()))
    return _package_digest(entries)


def _source_console_scripts(root: Path) -> tuple[str, ...] | None:
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    scripts = project.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return None
    return tuple(sorted(f"{name} = {value}" for name, value in scripts.items() if isinstance(value, str)))


def _wheel_console_scripts(wheel: Path) -> tuple[str, ...] | None:
    with zipfile.ZipFile(wheel) as archive:
        candidates = [name for name in archive.namelist() if name.endswith(".dist-info/entry_points.txt")]
        if len(candidates) != 1:
            return None
        parser = ConfigParser()
        parser.optionxform = str
        try:
            parser.read_string(archive.read(candidates[0]).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if not parser.has_section("console_scripts"):
            return tuple()
        return tuple(sorted(f"{name} = {value}" for name, value in parser.items("console_scripts")))


def run(
    wheel: Path,
    *,
    target: Path | None = None,
    source_root: Path | None = None,
    reference_wheel: Path | None = None,
) -> dict[str, Any]:
    if not wheel.is_file():
        raise FileNotFoundError(wheel)
    owned_target = target is None
    target = target or Path(tempfile.mkdtemp(prefix="open-agent-harness-wheel-smoke-"))
    target.mkdir(parents=True, exist_ok=True)
    install_environment = os.environ.copy()
    install_environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        capture_output=True,
        text=True,
        check=False,
        env=install_environment,
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(target)
    demo = subprocess.run(
        [sys.executable, "-m", "app.cli", "demo"],
        cwd=target,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    imports = subprocess.run(
        [sys.executable, "-c", "import app.cli,app.mcp,runtime.orchestrator,traces.replay,experiments.agentdojo_adapter_server"],
        cwd=target,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        demo_value = json.loads(demo.stdout)
    except (TypeError, ValueError):
        demo_value = None
    source_package_sha256 = source_tree_sha256(source_root) if source_root else None
    wheel_package_sha256 = wheel_source_tree_sha256(wheel)
    wheel_manifest = wheel_manifest_sha256(wheel)
    source_console_scripts = _source_console_scripts(source_root) if source_root else None
    wheel_console_scripts = _wheel_console_scripts(wheel)
    reference_manifest = wheel_manifest_sha256(reference_wheel) if reference_wheel else None
    reference_manifest_matches = (
        bool(reference_manifest and reference_manifest == wheel_manifest)
        if reference_wheel
        else None
    )
    if source_root:
        package_matches = bool(source_package_sha256 and source_package_sha256 == wheel_package_sha256)
        console_scripts_match = bool(source_console_scripts is not None and source_console_scripts == wheel_console_scripts)
        source_matches_wheel: bool | None = bool(
            package_matches
            and console_scripts_match
            and (reference_manifest_matches is None or reference_manifest_matches)
        )
    else:
        console_scripts_match = None
        source_matches_wheel = None
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next((name for name in names if name.endswith("METADATA")), None)
        metadata = archive.read(metadata_name).decode("utf-8") if metadata_name else ""
    bytecode_entries = [name for name in names if "/__pycache__/" in name or name.endswith((".pyc", ".pyo"))]
    passed = bool(
        install.returncode == 0
        and demo.returncode == 0
        and imports.returncode == 0
        and isinstance(demo_value, dict)
        and demo_value.get("verified_success") is True
        and not bytecode_entries
        and (source_root is None or source_matches_wheel is True)
    )
    return {
        "schema": "clean-wheel-smoke/v1",
        "passed": passed,
        "wheel": wheel.name,
        "wheel_sha256": _sha256(wheel),
        "wheel_bytes": wheel.stat().st_size,
        "source_package_sha256": source_package_sha256,
        "wheel_package_sha256": wheel_package_sha256,
        "wheel_manifest_sha256": wheel_manifest,
        "source_matches_wheel": source_matches_wheel,
        "source_console_scripts": source_console_scripts,
        "wheel_console_scripts": wheel_console_scripts,
        "console_scripts_match": console_scripts_match,
        "reference_wheel": reference_wheel.name if reference_wheel else None,
        "reference_wheel_sha256": _sha256(reference_wheel) if reference_wheel and reference_wheel.is_file() else None,
        "reference_wheel_manifest_sha256": reference_manifest,
        "wheel_manifest_matches_reference": reference_manifest_matches,
        "target": "isolated-target" if owned_target else target.name,
        "target_created_by_runner": owned_target,
        "install_returncode": install.returncode,
        "demo_returncode": demo.returncode,
        "demo_verified_success": demo_value.get("verified_success") if isinstance(demo_value, dict) else None,
        "imports_returncode": imports.returncode,
        "metadata_license": [line for line in metadata.splitlines() if line.startswith("License:")],
        "has_license_file": any("license" in name.lower() for name in names),
        "bytecode_free": not bytecode_entries,
        "bytecode_entries": len(bytecode_entries),
        "stderr_tail": "\n".join(
            line
            for line in (install.stderr + demo.stderr + imports.stderr).splitlines()
            if "[notice]" not in line and "To update" not in line
        )[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target")
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--reference-wheel", help="independent fresh source-derived wheel for full manifest comparison")
    args = parser.parse_args()
    report = run(
        Path(args.wheel),
        target=Path(args.target) if args.target else None,
        source_root=Path(args.source_root),
        reference_wheel=Path(args.reference_wheel) if args.reference_wheel else None,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "wheel_sha256": report["wheel_sha256"], "source_package_sha256": report["source_package_sha256"], "wheel_package_sha256": report["wheel_package_sha256"], "wheel_manifest_matches_reference": report["wheel_manifest_matches_reference"], "output": str(output)}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
