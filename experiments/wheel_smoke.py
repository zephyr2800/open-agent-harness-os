"""Install a wheel into a fresh target and run the dependency-free smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(wheel: Path, *, target: Path | None = None) -> dict[str, Any]:
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
        [sys.executable, "-c", "import app.cli,app.mcp,runtime.orchestrator,traces.replay"],
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
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next((name for name in names if name.endswith("METADATA")), None)
        metadata = archive.read(metadata_name).decode("utf-8") if metadata_name else ""
    passed = bool(
        install.returncode == 0
        and demo.returncode == 0
        and imports.returncode == 0
        and isinstance(demo_value, dict)
        and demo_value.get("verified_success") is True
    )
    return {
        "schema": "clean-wheel-smoke/v1",
        "passed": passed,
        "wheel": wheel.name,
        "wheel_sha256": _sha256(wheel),
        "wheel_bytes": wheel.stat().st_size,
        "target": "isolated-target" if owned_target else target.name,
        "target_created_by_runner": owned_target,
        "install_returncode": install.returncode,
        "demo_returncode": demo.returncode,
        "demo_verified_success": demo_value.get("verified_success") if isinstance(demo_value, dict) else None,
        "imports_returncode": imports.returncode,
        "metadata_license": [line for line in metadata.splitlines() if line.startswith("License:")],
        "has_license_file": any("license" in name.lower() for name in names),
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
    args = parser.parse_args()
    report = run(Path(args.wheel), target=Path(args.target) if args.target else None)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "wheel_sha256": report["wheel_sha256"], "output": str(output)}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
