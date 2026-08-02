from __future__ import annotations

import json
import io
import sys
import threading
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
from pathlib import Path

from experiments.factorial import run_factorial
from improve.promotion import PromotionGate, Proposal
from adapters.base import ScriptedModel
from runtime.orchestrator import Harness, HarnessConfig
from tools.memory_workspace import make_memory_registry
from experiments.project1_integration import run as run_project1_integration
from traces.replay import load_jsonl
from benchmarks.tasks import load_tasks
from verify.independent import verify_factorial_report
from verify.real import verify_real_report
from adapters.project1_transformers import Project1TransformersAdapter
from adapters.http import OpenAICompatibleAdapter
from app.service import run_action
from app.cli import _load_auth_tokens, _optional_local_adapter, _server, _validate_bind_host, _validate_server_security
from app.storage import TraceStore
from experiments.verify_checkpoint_run import verify as verify_checkpoint_run
from experiments.run_promotion_matrix import _run_report, _write_heartbeat, main as promotion_matrix_main
from experiments.launch_preflight import _wheel_smoke_sidecar, main as launch_preflight_main
from experiments.release_readiness import _current_preflight, _current_wheel_smoke, _preflight_is_current, build_readiness
from experiments.data_split_audit import (
    REQUIRED_FROZEN_FIXTURE_HASHES,
    audit,
    main as audit_main,
    validate_required_audit_manifest,
)


ROOT = Path(__file__).parent.parent


class ExperimentTests(unittest.TestCase):
    def test_train_holdout_audit_rejects_contract_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            train = root / "train.jsonl"
            train.write_text(
                json.dumps({"task_id": "training-retry", "input": {"goal": "retry frozen-job-17"}}) + "\n",
                encoding="utf-8",
            )
            fixture = root / "fixture.json"
            fixture.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "holdout-retry-17",
                                "prompt": "Recover frozen-job-17 before completing.",
                                "expected_arguments": {"operation": "frozen-job-17", "attempt": 2},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = audit([train], [fixture])
        self.assertFalse(report["passed"])
        self.assertTrue(any(item["value"] == "frozen-job-17" for item in report["overlaps"]))

    def test_train_holdout_audit_accepts_disjoint_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            train = root / "train.jsonl"
            train.write_text(json.dumps({"task_id": "training-retry", "input": {"goal": "retry curriculum-job-19"}}) + "\n", encoding="utf-8")
            fixture = root / "fixture.json"
            fixture.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "holdout-retry-17",
                                "prompt": "Recover frozen-job-17 before completing.",
                                "expected_arguments": {"operation": "frozen-job-17", "attempt": 2},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = audit([train], [fixture])
        self.assertTrue(report["passed"])
        self.assertEqual(report["overlap_count"], 0)

    def test_train_holdout_audit_covers_contract_values_and_short_mapping_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            train = root / "train.jsonl"
            train.write_text(json.dumps({
                "task": "frozen-task-001",
                "prompt": "prompt-contract-001",
                "argument": "arg-001",
                "action": "act-001",
                "file": "a.cfg",
                "file_content": "file-contract-001",
                "api_key": "api-001",
                "api_value": "api-contract-001",
                "page_key": "page-01",
                "page_value": "browser-contract-001",
                "answer": "result-contract-001",
            }) + "\n", encoding="utf-8")
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps({
                "tasks": [{
                    "task_id": "frozen-task-001",
                    "prompt": "prompt-contract-001",
                    "expected_arguments": {"operation": "arg-001"},
                    "expected_actions": [{"arguments": {"token": "act-001"}}],
                    "expected_files": {"a.cfg": "file-contract-001"},
                    "api_records": {"api-001": {"token": "api-contract-001"}},
                    "browser_pages": {"page-01": {"body": "browser-contract-001"}},
                    "expected_result_contains": ["result-contract-001"],
                }],
            }), encoding="utf-8")
            report = audit([train], [fixture])
        kinds = {item["kind"] for item in report["overlaps"]}
        self.assertTrue({
            "task_id", "prompt", "expected_arguments_short_exact",
            "expected_action_arguments_short_exact", "expected_files",
            "expected_file_key_short_exact", "api_records",
            "api_record_key_short_exact", "browser_pages",
            "browser_page_key_short_exact", "expected_result_contains",
        }.issubset(kinds))

    def test_train_holdout_audit_known_proxy_contamination_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            train = Path(temporary) / "train.jsonl"
            train.write_text(json.dumps({"path": "proxy_v1_source_00.dat"}) + "\n", encoding="utf-8")
            fixture = ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v1.json"
            report = audit([train], [fixture])
        self.assertFalse(report["passed"])
        self.assertTrue(any(item["value"] == "proxy_v1_source_00.dat" for item in report["overlaps"]))

    def test_train_holdout_audit_covers_every_pinned_fixture_at_fixed_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            train = Path(temporary) / "train.jsonl"
            train.write_text(json.dumps({"example": "fresh-training-only-token-912"}) + "\n", encoding="utf-8")
            fixtures = [
                ROOT / "benchmarks" / "fixtures" / name
                for name in REQUIRED_FROZEN_FIXTURE_HASHES
            ]
            report = audit([train], fixtures)
            manifest = Path(temporary) / "audit.json"
            manifest.write_text(json.dumps(report), encoding="utf-8")
            validated = validate_required_audit_manifest(manifest)
        self.assertTrue(report["required_fixture_gate"]["passed"])
        self.assertEqual(set(report["required_fixture_gate"]["required_fixture_hashes"]), set(REQUIRED_FROZEN_FIXTURE_HASHES))
        self.assertTrue(validated["passed"])

    def test_required_audit_manifest_rejects_pinned_fixture_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            train = Path(temporary) / "train.jsonl"
            train.write_text(json.dumps({"example": "fresh-training-only-token-913"}) + "\n", encoding="utf-8")
            report = audit([train], [
                ROOT / "benchmarks" / "fixtures" / name
                for name in REQUIRED_FROZEN_FIXTURE_HASHES
            ])
            report["fixtures"][0]["sha256"] = "0" * 64
            manifest = Path(temporary) / "audit.json"
            manifest.write_text(json.dumps(report), encoding="utf-8")
            validated = validate_required_audit_manifest(manifest)
        self.assertFalse(validated["passed"])
        self.assertTrue(validated["fixture_gate"]["hash_mismatches"])

    def test_train_holdout_audit_cli_fails_for_overlap_and_incomplete_fixture_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            train = root / "train.jsonl"
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps({"tasks": [{"task_id": "cli-holdout", "expected_arguments": {"token": "cli-frozen-token"}}]}), encoding="utf-8")
            train.write_text(json.dumps({"token": "cli-frozen-token"}) + "\n", encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                "data_split_audit", "--train-jsonl", str(train), "--task-spec", str(fixture), "--fail-on-overlap",
            ]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(audit_main(), 2)
            train.write_text(json.dumps({"token": "clean-curriculum-token"}) + "\n", encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                "data_split_audit", "--train-jsonl", str(train), "--task-spec", str(fixture), "--require-required-fixtures",
            ]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(audit_main(), 2)

    def test_promotion_matrix_refuses_missing_or_incomplete_audit_before_model_load(self) -> None:
        missing_audit = ROOT / "work" / "missing-train-holdout-audit.json"
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json"
        with mock.patch.object(sys, "argv", [
            "run_promotion_matrix", "--project1-root", "missing-project", "--checkpoint", "missing-checkpoint",
            "--output", "missing-output.json", "--train-holdout-audit", str(missing_audit),
            "--task-spec", str(task_spec),
        ]):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exited:
                    promotion_matrix_main()
        self.assertEqual(exited.exception.code, 2)

    def test_promotion_matrix_v2_rejects_a_legacy_proxy_substitution_before_model_load(self) -> None:
        missing_audit = ROOT / "work" / "missing-train-holdout-audit.json"
        missing_novelty = ROOT / "work" / "missing-holdout-novelty-audit.json"
        research = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json"
        legacy_proxy = ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v1.json"
        active_proxy = ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v2.json"
        with mock.patch.object(sys, "argv", [
            "run_promotion_matrix", "--project1-root", "missing-project", "--checkpoint", "missing-checkpoint",
            "--output", "missing-output.json", "--train-holdout-audit", str(missing_audit),
            "--holdout-novelty-audit", str(missing_novelty), "--promotion-protocol", "v2",
            "--task-spec", str(research), "--task-spec", str(legacy_proxy), "--task-spec", str(active_proxy),
        ]):
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exited:
                promotion_matrix_main()
        self.assertEqual(exited.exception.code, 2)
        self.assertIn("--task-spec must name each pinned fixture", stderr.getvalue())

    def test_promotion_matrix_rejects_sampling_knobs_without_sampling(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json"
        with mock.patch.object(sys, "argv", [
            "run_promotion_matrix", "--project1-root", "missing-project", "--checkpoint", "missing-checkpoint",
            "--output", "missing-output.json", "--train-holdout-audit", "missing-audit.json",
            "--holdout-novelty-audit", "missing-novelty.json", "--task-spec", str(task_spec),
            "--temperature", "0.5",
        ]):
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exited:
                promotion_matrix_main()
        self.assertEqual(exited.exception.code, 2)
        self.assertIn("require --do-sample", stderr.getvalue())

    def test_promotion_matrix_v2_requires_stochastic_decoding_before_model_load(self) -> None:
        missing_audit = ROOT / "work" / "missing-train-holdout-audit.json"
        missing_novelty = ROOT / "work" / "missing-holdout-novelty-audit.json"
        research = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json"
        active_proxy = ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v2.json"
        author_holdout = ROOT / "benchmarks" / "fixtures" / "task-spec-author-holdout-v1.json"
        with mock.patch.object(sys, "argv", [
            "run_promotion_matrix", "--project1-root", "missing-project", "--checkpoint", "missing-checkpoint",
            "--output", "missing-output.json", "--train-holdout-audit", str(missing_audit),
            "--holdout-novelty-audit", str(missing_novelty), "--promotion-protocol", "v2",
            "--task-spec", str(research), "--task-spec", str(active_proxy), "--task-spec", str(author_holdout),
        ]):
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exited:
                promotion_matrix_main()
        self.assertEqual(exited.exception.code, 2)
        self.assertIn("requires --do-sample", stderr.getvalue())

    def test_promotion_matrix_heartbeat_is_claim_safe_and_timestamped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "matrix.heartbeat.json"
            _write_heartbeat(path, {"schema": "promotion-matrix/v1-heartbeat", "status": "generating", "task_id": "t"})
            report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "generating")
        self.assertEqual(report["task_id"], "t")
        self.assertIsInstance(report["updated_at"], float)

    def test_readiness_manifest_keeps_provenance_gate_explicit(self) -> None:
        report = build_readiness(ROOT)
        gate = report["gates"]["licensing_provenance_review"]
        self.assertEqual(gate["status"], "open")
        self.assertEqual(gate["evidence"], "docs/PROVENANCE_REVIEW.md")
        self.assertTrue((ROOT / "docs" / "PROVENANCE_REVIEW.md").is_file())

    def test_readiness_reports_current_wheel_evidence_or_a_pending_rebuild(self) -> None:
        report = build_readiness(ROOT)
        expected_wheel = f"open_agent_harness_os-{report['package_version']}-py3-none-any.whl"
        gate = report["gates"]["clean_wheel_smoke"]
        self.assertIn(expected_wheel, gate["detail"])
        # A source checkout may legitimately be ahead of its committed
        # preflight evidence. The release command, not this unit test, is what
        # creates a source-bound passing artifact after a code change.
        if gate["status"] == "passed":
            self.assertIn("clean-wheel-smoke-v", Path(gate["evidence"]).name)
        else:
            self.assertEqual(gate["status"], "pending")
            self.assertIn("clean-wheel-smoke-current-", Path(gate["evidence"]).name)
            self.assertIn("has not passed", gate["detail"])

    def test_preflight_exports_a_normalized_source_bound_wheel_smoke_sidecar(self) -> None:
        report = {
            "checks": [{
                "id": "wheel_install_smoke",
                "passed": True,
                "detail": {
                    "path": "open_agent_harness_os-0.1.8-py3-none-any.whl",
                    "sha256": "b" * 64,
                    "source_package_sha256": "a" * 64,
                    "wheel_package_sha256": "a" * 64,
                    "source_matches_wheel": True,
                    "console_scripts_match": True,
                    "wheel_manifest_sha256": "c" * 64,
                    "reference_wheel_sha256": "d" * 64,
                    "reference_wheel_manifest_sha256": "c" * 64,
                    "wheel_manifest_matches_reference": True,
                },
            }],
        }
        preflight = Path("experiments/results/launch-preflight-v42.json")
        sidecar = _wheel_smoke_sidecar(report, preflight_output=preflight)
        self.assertIsNotNone(sidecar)
        assert sidecar is not None
        self.assertTrue(sidecar["passed"])
        self.assertEqual(sidecar["wheel"], "open_agent_harness_os-0.1.8-py3-none-any.whl")
        self.assertEqual(sidecar["preflight_artifact"], str(preflight))

    def test_preflight_refuses_to_overwrite_a_wheel_smoke_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "clean-wheel-smoke-v99.json"
            existing.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                "launch_preflight", "--output", str(root / "preflight.json"),
                "--wheel-smoke-output", str(existing),
            ]):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as exited:
                    launch_preflight_main()
        self.assertEqual(exited.exception.code, 2)
        self.assertIn("new immutable evidence path", stderr.getvalue())

    def test_preflight_selection_requires_the_current_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            matching = {
                "passed": True,
                "source_package_sha256": "a" * 64,
                "checks": [
                    {"id": "unit_tests", "passed": True},
                    {
                        "id": "wheel_install_smoke",
                        "passed": True,
                        "detail": {
                            "source_package_sha256": "a" * 64,
                            "wheel_package_sha256": "a" * 64,
                            "source_matches_wheel": True,
                            "console_scripts_match": True,
                            "wheel_manifest_matches_reference": True,
                            "wheel_manifest_sha256": "a" * 64,
                            "reference_wheel_manifest_sha256": "a" * 64,
                        },
                    },
                ],
            }
            (results / "launch-preflight-v2.json").write_text(json.dumps(matching), encoding="utf-8")
            (results / "launch-preflight-v12.json").write_text(json.dumps(matching), encoding="utf-8")
            path, report = _current_preflight(results, "a" * 64)
        self.assertEqual(path.name, "launch-preflight-v12.json")
        self.assertIsNotNone(report)

    def test_wheel_smoke_selection_uses_numeric_artifact_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            matching = {
                "passed": True,
                "wheel": "open_agent_harness_os-0.1.8-py3-none-any.whl",
                "source_package_sha256": "a" * 64,
                "wheel_package_sha256": "a" * 64,
                "source_matches_wheel": True,
                "console_scripts_match": True,
                "wheel_manifest_matches_reference": True,
                "wheel_manifest_sha256": "a" * 64,
                "reference_wheel_manifest_sha256": "a" * 64,
            }
            (results / "clean-wheel-smoke-v2.json").write_text(json.dumps(matching), encoding="utf-8")
            (results / "clean-wheel-smoke-v12.json").write_text(json.dumps(matching), encoding="utf-8")
            path, report, _ = _current_wheel_smoke(results, "0.1.8", "a" * 64)
        self.assertEqual(path.name, "clean-wheel-smoke-v12.json")
        self.assertIsNotNone(report)

    def test_readiness_requires_completed_source_bound_preflight(self) -> None:
        fingerprint = "a" * 64
        preflight = {
            "passed": True,
            "source_package_sha256": fingerprint,
            "checks": [
                {"id": "unit_tests", "passed": True},
                {
                    "id": "wheel_install_smoke",
                    "passed": True,
                    "detail": {
                        "source_package_sha256": fingerprint,
                        "wheel_package_sha256": fingerprint,
                        "source_matches_wheel": True,
                        "console_scripts_match": True,
                        "wheel_manifest_sha256": fingerprint,
                        "reference_wheel_manifest_sha256": fingerprint,
                        "wheel_manifest_matches_reference": True,
                    },
                },
            ],
        }
        self.assertTrue(_preflight_is_current(preflight, fingerprint))
        preflight["checks"][1]["detail"]["wheel_package_sha256"] = "b" * 64
        self.assertFalse(_preflight_is_current(preflight, fingerprint))
        preflight["checks"][1]["detail"]["wheel_package_sha256"] = fingerprint
        preflight["checks"][1]["detail"]["wheel_manifest_matches_reference"] = False
        self.assertFalse(_preflight_is_current(preflight, fingerprint))
        preflight["checks"][1]["detail"]["wheel_manifest_matches_reference"] = True
        preflight["checks"] = preflight["checks"][1:]
        self.assertFalse(_preflight_is_current(preflight, fingerprint))

    def test_readiness_labels_private_matrix_and_public_summary_separately(self) -> None:
        report = build_readiness(ROOT)
        matrix_gate = report["gates"]["9b_frozen_matrix"]
        promotion_gate = report["gates"]["9b_promotion_gate"]
        self.assertEqual(matrix_gate["status"], "context_only")
        self.assertTrue(matrix_gate["evidence"].endswith("promotion-summary-v1.json"))
        self.assertEqual(promotion_gate["status"], "failed")
        self.assertIn("promotion_decision=reject", promotion_gate["detail"])
        self.assertEqual(report["status"]["research"], "historical_matrix_context_external_review_pending")

    def test_factorial_covers_ten_model_harness_cells(self) -> None:
        report = run_factorial(ROOT / "benchmarks" / "fixtures" / "task-spec-v0.json")
        self.assertEqual(len(report["cells"]), 10)
        self.assertIn("H4", report["interaction_vs_H1"])
        self.assertEqual(len(report["cells"]["specialized/H4"]["outcomes"]), 8)
        trace_text = report["cells"]["specialized/H4"]["outcomes"][0]["trace_jsonl"]
        replayed = load_jsonl(trace_text.splitlines())
        self.assertGreaterEqual(len(replayed.events), 1)
        self.assertEqual(replayed.validate(), [])
        independent = verify_factorial_report(report, ROOT / "benchmarks" / "fixtures" / "task-spec-v0.json")
        self.assertEqual(independent["task_cell_count"], 80)
        self.assertEqual(independent["trace_valid_rate"], 1.0)
        self.assertEqual(independent["runtime_independent_match_rate"], 1.0)

    def test_research_fixture_covers_renamed_web_and_long_horizon_surfaces(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v1.json"
        report = run_factorial(task_spec)
        self.assertEqual(len(report["cells"]), 10)
        self.assertEqual(len(report["cells"]["specialized/H4"]["outcomes"]), 11)
        independent = verify_factorial_report(report, task_spec)
        self.assertEqual(independent["task_cell_count"], 110)
        self.assertEqual(independent["trace_valid_rate"], 1.0)
        self.assertEqual(independent["runtime_independent_match_rate"], 1.0)

    def test_research_v4_is_frozen_broad_and_task_fixture_owned(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json"
        tasks = load_tasks(task_spec)
        self.assertEqual(len(tasks), 120)
        self.assertEqual(len({task.task_id for task in tasks}), 120)
        self.assertEqual({task.family for task in tasks}, {
            "abstain_high_risk", "abstain_unknown_capability", "alias_move", "alias_write",
            "api_lookup", "browser_lookup", "exact_write", "long_horizon", "long_horizon_alias",
            "move", "retry", "structured_json",
        })
        self.assertEqual(sum(task.adversarial for task in tasks), 20)
        self.assertTrue(all(task.api_records for task in tasks if task.family == "api_lookup"))
        self.assertTrue(all(task.browser_pages for task in tasks if task.family == "browser_lookup"))

    def test_exact_payload_ablation_holdout_is_fresh_and_byte_exact(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-exact-payload-holdout-v1.json"
        tasks = load_tasks(task_spec)
        self.assertEqual(len(tasks), 16)
        self.assertEqual(len({task.task_id for task in tasks}), 16)
        self.assertEqual({task.family for task in tasks}, {"exact_write"})
        self.assertTrue(all(task.split == "independent_exact_payload_holdout_v1" for task in tasks))
        self.assertTrue(all(task.expected_tool == "write_file" for task in tasks))
        self.assertTrue(all(len(task.expected_files) == 1 for task in tasks))
        self.assertTrue(all("STATE_DIGEST" not in next(iter(task.expected_files.values())) for task in tasks))

    def test_industry_proxy_has_stateful_and_injection_slices(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v1.json"
        tasks = load_tasks(task_spec)
        self.assertEqual(len(tasks), 48)
        self.assertEqual(sum(task.adversarial for task in tasks), 24)
        self.assertTrue(all(task.include_tool_outputs for task in tasks if task.adversarial))
        self.assertEqual({task.family for task in tasks}, {
            "state_dependency", "policy_sequence", "indirect_injection_browser", "indirect_injection_api",
        })

    def test_industry_proxy_v2_checks_answers_and_boundaries(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v2.json"
        tasks = load_tasks(task_spec)
        self.assertEqual(len(tasks), 16)
        self.assertEqual(sum(bool(task.expected_result_contains) for task in tasks), 8)
        self.assertEqual(sum(task.expected_kind == "abstain" for task in tasks), 8)

    def test_checkpoint_report_verifier_replays_current_shape(self) -> None:
        task_id = "verify-checkpoint"
        result = run_action(task_id, "Write x.txt", "write_file", {"path": "x.txt", "content": "hello"})
        report = {
            "variant": "H1",
            "rows": [{"task_id": "write-config", "verified_success": True, "trace_jsonl": result["trace_jsonl"]}],
        }
        task_spec = ROOT / "work" / "test-checkpoint-task-spec.json"
        task_spec.write_text(json.dumps({
            "schema": "harness-task-spec/v0",
            "tasks": [{"task_id": "write-config", "prompt": "Write x.txt", "split": "held_out", "available_tools": ["write_file"], "expected_kind": "finish", "expected_tool": "write_file", "expected_arguments": {"path": "x.txt", "content": "hello"}, "expected_files": {"x.txt": "hello"}}],
        }), encoding="utf-8")
        report_path = ROOT / "work" / "test-checkpoint-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        try:
            audited = verify_checkpoint_run(report_path, task_spec)
        finally:
            task_spec.unlink(missing_ok=True)
            report_path.unlink(missing_ok=True)
        self.assertEqual(audited["trace_valid_rate"], 1.0)
        self.assertEqual(audited["independent_success_rate"], 1.0)
        self.assertEqual(audited["runtime_independent_match_rate"], 1.0)

    def test_promotion_matrix_partial_report_preserves_horizon_and_completion_state(self) -> None:
        task_spec = ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json"
        row = {
            "task_id": "partial-task",
            "family": "long_horizon",
            "difficulty": "long_horizon",
            "adversarial": False,
            "expected_action_count": 3,
            "expected_tool_count": 3,
            "available_tool_count": 4,
            "protocol_valid": True,
            "verified_success": True,
            "unsafe_attempt": False,
            "false_completion": False,
            "unverified_action_attempts": 0,
            "unknown_action_attempts": 0,
            "premature_finish_rejections": 0,
            "abstained": False,
            "error": None,
            "metrics": {},
            "elapsed_seconds": 0.1,
            "trace_jsonl": "",
            "independent": {"independent_success": True, "trace_valid": True},
        }
        report = _run_report(
            task_spec,
            seed=0,
            do_sample=False,
            enable_repair=False,
            rows=[row],
            elapsed_seconds=0.2,
            complete=False,
            temperature=0.55,
            top_p=0.82,
        )
        self.assertFalse(report["complete"])
        self.assertEqual(report["task_count"], 1)
        self.assertEqual(report["rows"][0]["expected_action_count"], 3)
        self.assertEqual(report["runtime_replay_agreement"], 1.0)
        self.assertEqual(report["temperature"], 0.55)
        self.assertEqual(report["top_p"], 0.82)

    def test_real_report_verifier_replays_protocol_error_traces(self) -> None:
        report = {"rows": [{"model": "qwen", "variant": "H1", "seed": 0, "task_id": "t", "protocol_valid": False, "verified_success": False, "trace_jsonl": run_action("real-audit", "Write x", "write_file", {"path": "x", "content": "y"})["trace_jsonl"]}]}
        result = verify_real_report(report)
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["trace_valid_rate"], 1.0)

    def test_promotion_gate_rejects_protected_surface(self) -> None:
        gate = PromotionGate()
        with self.assertRaises(ValueError):
            gate.evaluate(Proposal("p", "evaluator", "bad", {}), held_in=lambda _: 1.0, held_out=lambda _: 1.0)

    def test_promotion_gate_uses_held_out_regression(self) -> None:
        gate = PromotionGate()
        proposal = Proposal("p", "context_rules", "add evidence", {"retain_verified": True})
        result = gate.evaluate(proposal, held_in=lambda item: 1.0 if item is None else 1.1, held_out=lambda item: 1.0 if item is None else 0.9)
        self.assertFalse(result.promoted)

    def test_h4_exposes_bounded_proposal_evaluation(self) -> None:
        _, registry = make_memory_registry()
        harness = Harness(ScriptedModel([]), registry, config=HarnessConfig(variant="H4"))
        result = harness.evaluate_proposal(
            Proposal("p", "context_rules", "retain verified evidence", {"retain_verified": True}),
            held_in=lambda item: 1.0 if item is None else 1.1,
            held_out=lambda item: 1.0 if item is None else 1.1,
        )
        self.assertTrue(result.promoted)

    def test_project1_adapter_smoke_preserves_strict_evidence(self) -> None:
        report = run_project1_integration()
        self.assertEqual(report["protocol_valid_rate"], 1.0)
        self.assertEqual(report["trace_valid_rate"], 1.0)
        self.assertEqual(report["verified_success_rate"], 0.75)

    def test_project1_transformers_bridge_maps_public_request(self) -> None:
        class FakePolicy:
            def decide(self, request):
                self.request = request
                return {
                    "schema": "action-ir/v0", "task_id": request.task_id, "step_id": "s0", "kind": "abstain",
                    "uncertainty": {"confidence": 0.9, "basis": "test"},
                    "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
                    "abstention": {"reason": "tool unavailable", "alternatives": ["ask"]},
                }

        adapter = Project1TransformersAdapter(ROOT / "projects" / "local-action-model", policy=FakePolicy())
        request = __import__("adapters.base", fromlist=["ModelRequest"]).ModelRequest("t", "prompt", "context", {}, ("abstain",), (), "sandbox", {"tokens": 50}, "H1", 0)
        self.assertEqual(adapter.decide(request)["kind"], "abstain")

    def test_product_service_returns_verified_replayable_trace(self) -> None:
        result = run_action("product-test", "Write x.txt", "write_file", {"path": "x.txt", "content": "hello"})
        self.assertTrue(result["verified_success"])
        self.assertEqual(load_jsonl(result["trace_jsonl"].splitlines()).validate(require_end=True), [])

    def test_product_service_keeps_high_risk_delete_denied(self) -> None:
        result = run_action("product-safety", "Delete temporary.txt", "delete_file", {"path": "temporary.txt"})
        self.assertFalse(result["verified_success"])
        self.assertFalse(result["protocol_valid"] is False)

    def test_product_model_endpoint_is_loopback_only(self) -> None:
        adapter, model_name = _optional_local_adapter({"model_endpoint": "http://127.0.0.1:11434", "model": "demo"})
        self.assertEqual(model_name, "demo")
        self.assertEqual(adapter.model, "demo")
        with self.assertRaises(ValueError):
            _optional_local_adapter({"model_endpoint": "https://example.com", "model": "demo"})
        _validate_bind_host("127.0.0.1")
        with self.assertRaises(ValueError):
            _validate_bind_host("0.0.0.0")
        _validate_bind_host("0.0.0.0", allow_non_loopback=True)

    def test_product_non_loopback_requires_authentication_and_tls(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires --auth-token"):
            _validate_server_security(
                "0.0.0.0",
                allow_non_loopback=True,
                auth_token=None,
                tls_certfile="cert.pem",
                tls_keyfile="key.pem",
            )
        with self.assertRaisesRegex(ValueError, "requires --tls-certfile"):
            _validate_server_security(
                "0.0.0.0",
                allow_non_loopback=True,
                auth_token="launch-preview-token-2026",
                tls_certfile=None,
                tls_keyfile=None,
            )
        with self.assertRaisesRegex(ValueError, "provided together"):
            _validate_server_security(
                "127.0.0.1",
                allow_non_loopback=False,
                auth_token=None,
                tls_certfile="cert.pem",
                tls_keyfile=None,
            )
        _validate_server_security(
            "127.0.0.1",
            allow_non_loopback=False,
            auth_token=None,
            tls_certfile=None,
            tls_keyfile=None,
        )

    def test_product_auth_token_file_parser_is_strict(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as handle:
            handle.write(json.dumps({"alice": "alice-launch-token-2026"}))
            path = handle.name
        try:
            self.assertEqual(_load_auth_tokens(path), {"alice": "alice-launch-token-2026"})
        finally:
            Path(path).unlink(missing_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as handle:
            handle.write("[]")
            invalid_path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "JSON object"):
                _load_auth_tokens(invalid_path)
        finally:
            Path(invalid_path).unlink(missing_ok=True)

    def test_product_http_auth_protects_configured_server(self) -> None:
        token = "launch-preview-token-2026"
        server = ThreadingHTTPServer(("127.0.0.1", 0), _server(auth_token=token))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/health")
            unauthorized = connection.getresponse()
            self.assertEqual(unauthorized.status, 401)
            unauthorized.read()
            connection.close()

            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/health", headers={"Authorization": f"Bearer {token}"})
            authorized = connection.getresponse()
            self.assertEqual(authorized.status, 200)
            self.assertEqual(json.loads(authorized.read())["status"], "ok")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_product_http_token_principals_isolate_retained_traces(self) -> None:
        tokens = {
            "alice": "alice-launch-token-2026",
            "bob": "bob-launch-token-2026",
        }
        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _server(directory, auth_tokens=tokens))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(principal: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
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
                run_body = {
                    "task_id": "tenant-run",
                    "prompt": "Write a tenant file",
                    "tool": "write_file",
                    "arguments": {"path": "tenant.txt", "content": "ok"},
                }
                alice_status, alice_run = request("alice", "POST", "/run", run_body)
                bob_status, bob_run = request("bob", "POST", "/run", {**run_body, "task_id": "tenant-run-bob"})
                self.assertEqual(alice_status, 200)
                self.assertEqual(bob_status, 200)
                self.assertNotEqual(alice_run["trace_retention"]["digest"], bob_run["trace_retention"]["digest"])

                alice_traces_status, alice_traces = request("alice", "GET", "/traces")
                bob_traces_status, bob_traces = request("bob", "GET", "/traces")
                self.assertEqual(alice_traces_status, 200)
                self.assertEqual(bob_traces_status, 200)
                self.assertEqual(len(alice_traces["traces"]), 1)
                self.assertEqual(len(bob_traces["traces"]), 1)

                foreign_status, _ = request("bob", "GET", f"/traces/{alice_run['trace_retention']['digest']}")
                self.assertEqual(foreign_status, 404)
                health_status, health = request("alice", "GET", "/health")
                self.assertEqual(health_status, 200)
                self.assertTrue(health["tenant_isolation"])
            finally:
                server.shutdown()
                server.server_close()

    def test_product_trace_retention_and_resource_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_action("retained", "Write x.txt", "write_file", {"path": "x.txt", "content": "hello"}, trace_dir=directory)
            self.assertTrue(result["verified_success"])
            store = TraceStore(directory, max_files=1)
            self.assertEqual(len(store.list()), 1)
            self.assertEqual(store.read(result["trace_retention"]["digest"]), result["trace_jsonl"])
        with self.assertRaises(ValueError):
            run_action("bad-limit", "Write x.txt", "write_file", {"path": "x.txt", "content": "hello"}, max_steps=0)
        with self.assertRaises(ValueError):
            run_action("bad-budget", "Write x.txt", "write_file", {"path": "x.txt", "content": "hello"}, token_budget=32)

    def test_product_trace_store_survives_restart_and_concurrent_writers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            def write_trace(index: int) -> dict:
                return run_action(
                    f"concurrent-{index}",
                    "Write x.txt",
                    "write_file",
                    {"path": "x.txt", "content": str(index)},
                    trace_dir=directory,
                )

            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(write_trace, range(12)))
            self.assertTrue(all(result["verified_success"] for result in results))
            restarted = TraceStore(directory, max_files=16)
            retained = restarted.list()
            self.assertEqual(len(retained), 12)
            for result in results:
                digest = result["trace_retention"]["digest"]
                restored = restarted.read(digest)
                self.assertEqual(restored, result["trace_jsonl"])
                self.assertEqual(load_jsonl(restored.splitlines()).validate(require_end=True), [])

    def test_product_service_can_call_local_openai_compatible_model(self) -> None:
        decision = {
            "schema": "action-ir/v0", "task_id": "endpoint-test", "step_id": "step-0", "kind": "act",
            "uncertainty": {"confidence": 0.9, "basis": "test"},
            "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
            "action": {"intent": "write_file", "arguments": {"path": "endpoint.txt", "content": "hello"}, "preconditions": [], "risk": "low", "expected_effect": "verified", "escalate_if": []},
        }

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                # Consume the request body before replying.  Leaving a POST
                # body unread can make Windows abort the client socket while
                # the handler closes, producing a nondeterministic
                # WinError 10053 unrelated to the adapter contract.
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                payload = json.dumps({"choices": [{"message": {"content": json.dumps(decision)}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            adapter = OpenAICompatibleAdapter(f"http://127.0.0.1:{server.server_port}", "fake-local")
            result = run_action("endpoint-test", "Write endpoint.txt", "write_file", {"path": "endpoint.txt", "content": "hello"}, variant="H0", adapter=adapter, model_name="fake-local")
            self.assertTrue(result["verified_success"])
            self.assertTrue(result["protocol_valid"])
        finally:
            server.shutdown()
            server.server_close()
