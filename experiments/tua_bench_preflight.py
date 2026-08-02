"""Record TUA-Bench host readiness without downloading or running a benchmark.

TUA-Bench is an external, container-backed terminal-agent benchmark. This
module intentionally inspects only the checkout and host prerequisites: it
does not install packages, download assets, start a container, load a model,
or create a benchmark score. A passing result means the checked prerequisites
for *preparing* an isolated native run are present; it never means that an
agent integration or a native evaluation has completed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "tua-bench-host-preflight/v1"
REQUIRED_CHECKOUT_PATHS = (
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    "repo_env",
    "tasks",
)

CommandLookup = Callable[[str], str | None]
GitRunner = Callable[[Path, tuple[str, ...]], tuple[int, str, str]]


def _check(check_id: str, passed: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def _default_git_runner(root: Path, args: tuple[str, ...]) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _command_record(name: str, lookup: CommandLookup) -> dict[str, Any]:
    path = lookup(name)
    return {"name": name, "available": bool(path), "path": path}


def _checkout_check(root: Path, git_runner: GitRunner) -> dict[str, Any]:
    exists = root.is_dir()
    missing = [name for name in REQUIRED_CHECKOUT_PATHS if not (root / name).exists()] if exists else list(REQUIRED_CHECKOUT_PATHS)
    commit: str | None = None
    dirty: str | None = None
    git_error: str | None = None
    if exists:
        code, stdout, stderr = git_runner(root, ("rev-parse", "HEAD"))
        if code == 0 and stdout:
            commit = stdout
        else:
            git_error = stderr or stdout or "git rev-parse failed"
        if git_error is None:
            code, stdout, stderr = git_runner(root, ("status", "--porcelain"))
            if code == 0:
                dirty = stdout
            else:
                git_error = stderr or stdout or "git status failed"
    passed = exists and not missing and commit is not None and not dirty and git_error is None
    return _check(
        "tua_checkout",
        passed,
        {
            "root": str(root),
            "exists": exists,
            "required_paths": list(REQUIRED_CHECKOUT_PATHS),
            "missing_paths": missing,
            "commit": commit,
            "clean": dirty == "" if dirty is not None else False,
            "git_error": git_error,
        },
    )


def _backend_check(lookup: CommandLookup) -> dict[str, Any]:
    docker = _command_record("docker", lookup)
    podman = _command_record("podman", lookup)
    return _check(
        "container_backend",
        docker["available"] or podman["available"],
        {
            "docker": docker,
            "podman": podman,
            "requirement": "TUA-Bench requires Docker or Podman for its containerized task environments.",
        },
    )


def _uv_check(lookup: CommandLookup) -> dict[str, Any]:
    uv = _command_record("uv", lookup)
    return _check(
        "uv_command",
        bool(uv["available"]),
        {
            "uv": uv,
            "requirement": "TUA-Bench documents uv commands for setup-env and native benchmark execution.",
        },
    )


def _assets_check(root: Path, required_assets: Iterable[str | Path]) -> dict[str, Any]:
    root = root.resolve()
    resolved: list[Path] = []
    outside_root: list[str] = []
    for item in required_assets:
        path = Path(item).expanduser()
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        resolved.append(path)
        try:
            path.relative_to(root)
        except ValueError:
            outside_root.append(str(path))
    missing = [str(path) for path in resolved if not path.exists()]
    provided = bool(resolved)
    return _check(
        "required_assets",
        provided and not missing and not outside_root,
        {
            "provided": provided,
            "paths": [str(path) for path in resolved],
            "missing_paths": missing,
            "outside_checkout_paths": outside_root,
            "requirement": (
                "Pass one or more assets under the pinned checkout that its setup procedure created or downloaded. "
                "Without explicit paths, this preflight cannot attest that setup-env completed."
            ),
        },
    )


def build_preflight(
    tua_root: str | Path,
    *,
    required_assets: Iterable[str | Path] = (),
    command_lookup: CommandLookup = shutil.which,
    git_runner: GitRunner = _default_git_runner,
) -> dict[str, Any]:
    """Build a scope-limited host preflight report for a pinned TUA checkout."""

    root = Path(tua_root).expanduser().resolve()
    checks = [
        _checkout_check(root, git_runner),
        _backend_check(command_lookup),
        _uv_check(command_lookup),
        _assets_check(root, required_assets),
    ]
    passed = all(check["passed"] for check in checks)
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "TUA-Bench checkout, host commands, and caller-specified setup assets only; "
            "this does not install, download, run containers, load a model, or execute a benchmark."
        ),
        "passed": passed,
        "status": "host_ready_for_manual_native_setup" if passed else "blocked_by_prerequisites",
        "checks": checks,
        "execution_boundary": {
            "native_agent_integration": "not_implemented_by_this_preflight",
            "native_benchmark_result": "not_run",
            "model_or_provider_credentials": "not inspected",
        },
        "next_actions": (
            [
                "Implement and preregister a source-bound TUA policy bridge before attempting a native run.",
                "Run TUA-Bench's own setup and preserve its native artifacts, metric, revision, and license boundary.",
            ]
            if passed
            else [
                "Resolve each failed prerequisite without changing the current frozen model evaluation.",
                "Rerun this read-only preflight with explicit paths to setup-created assets.",
            ]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tua-root", required=True, help="path to a pinned TUA-Bench checkout")
    parser.add_argument("--output", required=True, help="path for the JSON preflight report")
    parser.add_argument(
        "--required-asset",
        action="append",
        default=[],
        help="path under --tua-root, relative or absolute, that setup-env created or downloaded; repeat as needed",
    )
    parser.add_argument(
        "--fail-on-blocker",
        action="store_true",
        help="return status 2 when checkout, container backend, uv, or required assets are unavailable",
    )
    args = parser.parse_args()
    report = build_preflight(args.tua_root, required_assets=args.required_asset)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "passed": report["passed"]}, sort_keys=True))
    return 0 if report["passed"] or not args.fail_on_blocker else 2


if __name__ == "__main__":
    raise SystemExit(main())
