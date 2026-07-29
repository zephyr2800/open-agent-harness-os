"""Run the local developer-preview launch preflight and write its evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.cli import _optional_local_adapter, _server, _validate_bind_host, _validate_server_security
from app.mcp import PROTOCOL_VERSION, dispatch
from app.service import run_action
from app.storage import TraceStore
from experiments.product_smoke import run as run_product_smoke
from experiments.scorecard import build_scorecard
from experiments.wheel_smoke import run as run_wheel_smoke
from traces.replay import load_jsonl
from tools.memory_workspace import make_memory_registry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WHEEL = ROOT / "work" / "package-dist" / "open_agent_harness_os-0.1.0-py3-none-any.whl"
SOURCE_CHECKOUT = (ROOT / "pyproject.toml").is_file()
REQUIRED_DOCS = (
    "README.md",
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "PRODUCT.md",
    "docs/PRODUCT_LAUNCH_PLAN.md",
    "docs/USER_WORKFLOW_GUIDE.md",
    "docs/RESEARCH_LAUNCH_BRIEF.md",
    "docs/RESEARCH_LAUNCH_ONE_PAGER_2026-07-26.md",
    "docs/REPRODUCIBILITY_9B_CHAIN.md",
    "docs/EVIDENCE_INDEX.md",
    "docs/READING_LIST.md",
    "docs/EXTERNAL_BAR_UPDATE_2026-07-26.md",
    "docs/RESEARCH_LAUNCH_UPDATE_2026-07-27.md",
    "docs/CLAIMS_AND_EVIDENCE_MATRIX.md",
    "docs/RESEARCH_LANDSCAPE_2026-07-29.md",
    "docs/RESEARCH_BREAKTHROUGH_PROTOCOL_2026-07-29.md",
    "docs/EXTERNAL_EVALUATION_RUNBOOK_2026-07-29.md",
    "docs/PUBLIC_RELEASE_CHECKLIST.md",
    "docs/PROVENANCE_REVIEW.md",
    "benchmarks/fixtures/task-spec-external-bar-lite-v1.json",
    "benchmarks/fixtures/task-spec-external-bar-lite-v2.json",
)


def _check(check_id: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def _mcp_check() -> dict[str, Any]:
    initialized = dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    listed = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    expected_tools = {"harness_run", "harness_tools", "harness_replay"}
    listed_tools = {item["name"] for item in listed["result"]["tools"]}
    ran = dispatch({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "harness_run",
            "arguments": {
                "task_id": "launch-preflight",
                "prompt": "write a preflight file",
                "tool": "write_file",
                "arguments": {"path": "preflight.txt", "content": "ok"},
            },
        },
    })
    result = ran["result"]["structuredContent"]
    replay = dispatch({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "harness_replay",
            "arguments": {"trace_jsonl": result["trace_jsonl"]},
        },
    })
    replay_value = replay["result"]["structuredContent"]
    passed = (
        initialized["result"]["protocolVersion"] == PROTOCOL_VERSION
        and listed_tools == expected_tools
        and result["protocol_valid"]
        and result["verified_success"]
        and replay_value["valid"]
        and load_jsonl(result["trace_jsonl"].splitlines()).validate(require_end=True) == []
    )
    return _check(
        "mcp_stdio_contract",
        passed,
        {
            "protocol_version": initialized["result"]["protocolVersion"],
            "tools": sorted(listed_tools),
            "run_verified_success": result["verified_success"],
            "replay_valid": replay_value["valid"],
            "trace_events": replay_value["events"],
            "network_listener": False,
        },
    )


def _safety_check() -> dict[str, Any]:
    delete = run_action(
        "launch-preflight-delete",
        "delete protected file",
        "delete_file",
        {"path": "protected.txt"},
        initial_files={"protected.txt": "must remain"},
    )
    bind_rejected = False
    try:
        _validate_bind_host("0.0.0.0")
    except ValueError:
        bind_rejected = True
    endpoint_rejected = False
    try:
        _optional_local_adapter({"model_endpoint": "https://example.com", "model": "external"})
    except ValueError:
        endpoint_rejected = True
    tls_gate_rejected = False
    try:
        _validate_server_security(
            "0.0.0.0",
            allow_non_loopback=True,
            auth_token="launch-preflight-token-2026",
            tls_certfile=None,
            tls_keyfile=None,
        )
    except ValueError as exc:
        tls_gate_rejected = "requires --tls-certfile" in str(exc)
    passed = not delete["verified_success"] and delete["abstained"] and bind_rejected and endpoint_rejected and tls_gate_rejected
    return _check(
        "safety_and_locality",
        passed,
        {
            "high_risk_delete_verified_success": delete["verified_success"],
            "high_risk_delete_abstained": delete["abstained"],
            "non_loopback_bind_rejected": bind_rejected,
            "non_local_model_endpoint_rejected": endpoint_rejected,
            "non_loopback_tls_required": tls_gate_rejected,
        },
    )


def _tool_security_check() -> dict[str, Any]:
    """Audit every enabled tool's declared authority and verification boundary."""

    _, registry = make_memory_registry()
    metadata = {name: registry.metadata(name) for name in registry.names()}
    failures: dict[str, list[str]] = {}
    for name, value in metadata.items():
        issues: list[str] = []
        if value.get("risk") not in {"low", "medium", "high", "critical"}:
            issues.append("invalid risk")
        if not isinstance(value.get("required_authority"), str) or not value["required_authority"]:
            issues.append("missing required authority")
        if not isinstance(value.get("schema"), dict) or value["schema"].get("type") != "object":
            issues.append("schema is not an object schema")
        if not value.get("preconditions"):
            issues.append("missing preconditions")
        if not value.get("side_effects"):
            issues.append("missing side-effect declaration")
        spec = registry.get(name)
        if spec is None or not callable(spec.verifier):
            issues.append("missing independent verifier")
        if value.get("risk") in {"high", "critical"} and value.get("required_authority") != "elevated":
            issues.append("high-risk tool is not elevated")
        if issues:
            failures[name] = issues
    return _check(
        "tool_security_metadata",
        not failures,
        {
            "tool_count": len(metadata),
            "tools": sorted(metadata),
            "high_risk_tools": sorted(name for name, value in metadata.items() if value.get("risk") in {"high", "critical"}),
            "failures": failures,
        },
    )


def _retention_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        def write_trace(index: int) -> dict[str, Any]:
            return run_action(
                f"preflight-concurrent-{index}",
                "Write a retained file",
                "write_file",
                {"path": "retained.txt", "content": str(index)},
                trace_dir=directory,
            )

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(write_trace, range(12)))
        restarted = TraceStore(directory, max_files=16)
        retained = restarted.list()
        valid = 0
        for result in results:
            digest = result["trace_retention"]["digest"]
            restored = restarted.read(digest)
            if restored == result["trace_jsonl"] and load_jsonl(restored.splitlines()).validate(require_end=True) == []:
                valid += 1
        passed = len(retained) == 12 and valid == 12 and all(result["verified_success"] for result in results)
        return _check(
            "trace_retention_restart_concurrency",
            passed,
            {"concurrent_writes": 12, "retained_after_restart": len(retained), "valid_restored_traces": valid},
        )


def _auth_check() -> dict[str, Any]:
    token = "launch-preflight-token-2026"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _server(auth_token=token))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    unauthorized_status = None
    authorized_status = None
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/health")
        unauthorized = connection.getresponse()
        unauthorized_status = unauthorized.status
        unauthorized.read()
        connection.close()

        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/health", headers={"Authorization": f"Bearer {token}"})
        authorized = connection.getresponse()
        authorized_status = authorized.status
        authorized_body = json.loads(authorized.read())
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
    passed = unauthorized_status == 401 and authorized_status == 200 and authorized_body.get("status") == "ok"
    return _check(
        "http_bearer_authentication",
        passed,
        {"unauthorized_status": unauthorized_status, "authorized_status": authorized_status, "authorized_health": authorized_body.get("status")},
    )


def _rate_limit_check() -> dict[str, Any]:
    token = "launch-preflight-rate-token-2026"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _server(auth_token=token, rate_limit_per_minute=1))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    statuses: list[int] = []
    try:
        for _ in range(2):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/health", headers={"Authorization": f"Bearer {token}"})
            response = connection.getresponse()
            statuses.append(response.status)
            response.read()
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
    passed = statuses == [200, 429]
    return _check(
        "http_rate_limit",
        passed,
        {"configured_per_minute": 1, "statuses": statuses, "authenticated_only": True},
    )


def _tenant_isolation_check() -> dict[str, Any]:
    tokens = {
        "preflight-alice": "preflight-alice-token-2026",
        "preflight-bob": "preflight-bob-token-2026",
    }
    with tempfile.TemporaryDirectory() as directory:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _server(directory, auth_tokens=tokens))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(principal: str, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            payload = json.dumps(body).encode("utf-8") if body is not None else None
            headers = {"Authorization": f"Bearer {tokens[principal]}"}
            if payload is not None:
                headers["Content-Type"] = "application/json"
                headers["Content-Length"] = str(len(payload))
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            status = response.status
            value = json.loads(response.read())
            connection.close()
            return status, value

        try:
            body = {
                "task_id": "launch-preflight-tenant",
                "prompt": "write a tenant file",
                "tool": "write_file",
                "arguments": {"path": "tenant.txt", "content": "ok"},
            }
            alice_status, alice_run = request("preflight-alice", "POST", "/run", body)
            bob_status, bob_run = request("preflight-bob", "POST", "/run", {**body, "task_id": "launch-preflight-tenant-bob"})
            alice_list_status, alice_list = request("preflight-alice", "GET", "/traces")
            bob_list_status, bob_list = request("preflight-bob", "GET", "/traces")
            foreign_status, _ = request("preflight-bob", "GET", f"/traces/{alice_run['trace_retention']['digest']}")
            passed = (
                alice_status == 200
                and bob_status == 200
                and alice_run["verified_success"]
                and bob_run["verified_success"]
                and alice_list_status == 200
                and bob_list_status == 200
                and len(alice_list["traces"]) == 1
                and len(bob_list["traces"]) == 1
                and alice_run["trace_retention"]["digest"] != bob_run["trace_retention"]["digest"]
                and foreign_status == 404
            )
            return _check(
                "http_tenant_trace_isolation",
                passed,
                {
                    "alice_trace_count": len(alice_list.get("traces", [])),
                    "bob_trace_count": len(bob_list.get("traces", [])),
                    "foreign_trace_status": foreign_status,
                    "distinct_digests": alice_run.get("trace_retention", {}).get("digest") != bob_run.get("trace_retention", {}).get("digest"),
                },
            )
        finally:
            server.shutdown()
            server.server_close()


def _non_loopback_cli_check() -> dict[str, Any]:
    environment = os.environ.copy()
    environment.pop("HARNESS_AUTH_TOKEN", None)
    completed = subprocess.run(
        [sys.executable, "-m", "app.cli", "serve", "--host", "0.0.0.0", "--allow-non-loopback", "--port", "0"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    output = completed.stdout + "\n" + completed.stderr
    token_gate = completed.returncode == 2 and "requires --auth-token" in output
    environment["HARNESS_AUTH_TOKEN"] = "launch-preflight-token-2026"
    tls_completed = subprocess.run(
        [sys.executable, "-m", "app.cli", "serve", "--host", "0.0.0.0", "--allow-non-loopback", "--port", "0"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    tls_output = tls_completed.stdout + "\n" + tls_completed.stderr
    tls_gate = tls_completed.returncode == 2 and "requires --tls-certfile" in tls_output
    passed = token_gate and tls_gate
    return _check(
        "non_loopback_requires_token_and_tls",
        passed,
        {
            "token_gate_returncode": completed.returncode,
            "token_error_present": "requires --auth-token" in output,
            "tls_gate_returncode": tls_completed.returncode,
            "tls_error_present": "requires --tls-certfile" in tls_output,
        },
    )


def _wheel_check(wheel: Path) -> dict[str, Any]:
    if not wheel.is_file():
        return _check("wheel_integrity", False, {"path": wheel.name, "exists": False})
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    detail: dict[str, Any] = {"path": wheel.name, "exists": True, "bytes": wheel.stat().st_size, "sha256": digest}
    if not zipfile.is_zipfile(wheel):
        detail.update({"zipfile": False, "reason": "wheel is not a ZIP archive"})
        return _check("wheel_integrity", False, detail)
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            safe_names = all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)
            dist_info = {name for name in names if ".dist-info/" in name}
            required = {
                "app/__init__.py",
                "app/cli.py",
                "experiments/launch_preflight.py",
            }
            required_metadata = {name for name in dist_info if name.endswith(("/METADATA", "/WHEEL", "/RECORD"))}
            detail.update({
                "zipfile": True,
                "entry_count": len(names),
                "safe_paths": safe_names,
                "required_modules_present": required.issubset(names),
                "wheel_metadata_present": len(required_metadata) == 3,
            })
            passed = bool(safe_names and required.issubset(names) and len(required_metadata) == 3)
    except (OSError, zipfile.BadZipFile) as exc:
        detail.update({"zipfile": False, "reason": str(exc)})
        passed = False
    return _check(
        "wheel_integrity",
        passed,
        detail,
    )


def _wheel_smoke_check(wheel: Path) -> dict[str, Any]:
    """Install the wheel into an isolated target and run package-only smoke."""

    if not wheel.is_file():
        return _check("wheel_install_smoke", False, {"path": wheel.name, "exists": False})
    try:
        with tempfile.TemporaryDirectory(prefix="open-agent-harness-wheel-preflight-") as target:
            report = run_wheel_smoke(wheel, target=Path(target))
        detail = {
            "path": wheel.name,
            "sha256": report.get("wheel_sha256"),
            "install_returncode": report.get("install_returncode"),
            "demo_returncode": report.get("demo_returncode"),
            "demo_verified_success": report.get("demo_verified_success"),
            "imports_returncode": report.get("imports_returncode"),
        }
        passed = bool(report.get("passed"))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        detail = {"path": wheel.name, "error": str(exc)}
        passed = False
    return _check("wheel_install_smoke", passed, detail)


def _scorecard_check() -> dict[str, Any]:
    """Ensure local and external claim boundaries cannot be conflated."""

    local = build_scorecard(
        [
            {"task_id": "scorecard-a", "family": "stateful", "verified_success": True, "protocol_valid": True, "trace_valid": True, "runtime_replay_agreement": True},
            {"task_id": "scorecard-b", "family": "security", "verified_success": False, "protocol_valid": True, "trace_valid": True, "runtime_replay_agreement": True, "false_completion": True},
        ],
        suite="preflight-fixture",
        suite_kind="local_fixture",
        model="preflight-model",
        harness="preflight-harness",
    )
    external_rejected = False
    try:
        build_scorecard(
            [{"task_id": "scorecard-external", "verified_success": True}],
            suite="unidentified-external",
            suite_kind="external_native",
            model="preflight-model",
            harness="preflight-harness",
        )
    except ValueError:
        external_rejected = True
    external_accepted = True
    try:
        build_scorecard(
            [{"task_id": "scorecard-external", "verified_success": True}],
            suite="identified-external",
            suite_kind="external_native",
            model="preflight-model",
            harness="preflight-harness",
            suite_commit="abcdef1234567",
            native_metric="utility",
            native_metric_value=0.0,
            native_report_sha256="0" * 64,
            native_grader="preflight-grader",
            native_environment={"runner": "preflight", "runtime": "python", "platform": "local"},
        )
    except ValueError:
        external_accepted = False
    passed = local["macro_family_success_rate"] == 0.5 and external_rejected and external_accepted and "local" in local["claim_boundary"]
    return _check(
        "claim_safe_scorecard",
        passed,
        {
            "local_micro_success_rate": local["verified_success_rate"],
            "local_macro_family_success_rate": local["macro_family_success_rate"],
            "external_without_provenance_rejected": external_rejected,
            "external_complete_provenance_accepted": external_accepted,
        },
    )


def _test_check() -> dict[str, Any]:
    if not (ROOT / "tests").is_dir():
        return _check("unit_tests", True, {"not_applicable": True, "scope": "source-checkout-only"})
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return _check(
        "unit_tests",
        completed.returncode == 0,
        {"returncode": completed.returncode, "output_tail": output[-4000:]},
    )


def _companion_test_check() -> dict[str, Any]:
    """Run Project 1 from its package root so same-name modules do not collide."""

    companion_root = ROOT / "projects" / "local-action-model"
    if not companion_root.is_dir():
        return _check("companion_unit_tests", True, {"not_applicable": True, "scope": "source-checkout-only"})
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=companion_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return _check(
        "companion_unit_tests",
        completed.returncode == 0,
        {"returncode": completed.returncode, "output_tail": output[-4000:]},
    )


def run(*, wheel: Path = DEFAULT_WHEEL, include_tests: bool = False) -> dict[str, Any]:
    checks = [
        _check("product_smoke", True, run_product_smoke()),
        _mcp_check(),
        _safety_check(),
        _tool_security_check(),
        _retention_check(),
        _auth_check(),
        _rate_limit_check(),
        _tenant_isolation_check(),
        _non_loopback_cli_check(),
        _scorecard_check(),
    ]
    if SOURCE_CHECKOUT:
        checks.extend([
            _wheel_check(wheel),
            _wheel_smoke_check(wheel),
            _companion_test_check(),
            _check(
                "launch_docs",
                all((ROOT / relative).is_file() for relative in REQUIRED_DOCS),
                {"required": list(REQUIRED_DOCS), "missing": [relative for relative in REQUIRED_DOCS if not (ROOT / relative).is_file()]},
            ),
        ])
    else:
        checks.append(_check("package_scope", True, {"scope": "installed-wheel", "source_checkout_checks": "not_applicable"}))
    product = checks[0]["detail"]
    checks[0]["passed"] = (
        product["case_count"] >= 6
        and product["protocol_valid_rate"] == 1.0
        and product["safety_denied"] is True
    )
    if include_tests:
        checks.append(_test_check())
    return {
        "schema": "launch-preflight/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "local-developer-preview" if SOURCE_CHECKOUT else "installed-wheel-package",
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
        "limitations": [
            "This preflight does not establish public multi-user, operational, or external-benchmark readiness.",
            "The MCP check is in-process; the separate stdio subprocess artifact remains the protocol evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "experiments" / "results" / "launch-preflight-v1.json"))
    parser.add_argument("--wheel", default=str(DEFAULT_WHEEL))
    parser.add_argument("--with-tests", action="store_true", help="also run the full source test suite")
    args = parser.parse_args()
    report = run(wheel=Path(args.wheel), include_tests=args.with_tests)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": {item["id"]: item["passed"] for item in report["checks"]}}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
