from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from experiments.scorecard import build_scorecard
from experiments.tau2_export import build_export


COMMIT = "363133ada1936491fb5bcec33cd62c3518a99f65"


def _simulation(identifier: str, task_id: str, trial: int, reward: float, *, termination: str = "user_stop") -> dict:
    return {
        "id": identifier,
        "task_id": task_id,
        "duration": 1.5,
        "termination_reason": termination,
        "reward_info": {"reward": reward},
        "trial": trial,
        "seed": 100 + trial,
    }


def _report(simulations: list[dict]) -> dict:
    return {
        "info": {
            "git_commit": COMMIT,
            "num_trials": 2,
            "max_steps": 200,
            "max_errors": 10,
            "seed": 300,
            "agent_info": {"implementation": "llm_agent", "llm": "openai/local-action-policy"},
            "user_info": {"implementation": "user_simulator", "llm": "openai/evaluator"},
            "environment_info": {"domain_name": "retail"},
        },
        "tasks": [{"id": "a"}, {"id": "b"}],
        "simulations": simulations,
    }


class Tau2ExportTests(unittest.TestCase):
    def test_export_preserves_native_reward_and_marks_unobserved_harness_metrics(self) -> None:
        simulations = [
            _simulation("a-0", "a", 0, 1.0),
            _simulation("a-1", "a", 1, 0.0),
            _simulation("b-0", "b", 0, 0.0),
            _simulation("b-1", "b", 1, 1.0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.json"
            path.write_text(json.dumps(_report(simulations)), encoding="utf-8")
            result = build_export(path, domain="retail", suite_version="1.0.1")
        self.assertTrue(result["complete"])
        self.assertEqual(result["suite_commit"], COMMIT)
        self.assertEqual(result["native_metrics"]["average_reward"], 0.5)
        self.assertEqual(result["native_metrics"]["pass_hat"]["pass_hat_1"], 0.5)
        self.assertEqual(result["native_metrics"]["pass_hat"]["pass_hat_2"], 0.0)
        self.assertTrue(result["rows"][0]["verified_success"])
        self.assertNotIn("trace_valid", result["rows"][0])
        self.assertIn("unsafe_attempt", result["rows"][0]["unobserved_by_tau3"])

    def test_export_handoff_keeps_unobserved_harness_metrics_visible(self) -> None:
        simulations = [
            _simulation("a-0", "a", 0, 1.0),
            _simulation("a-1", "a", 1, 0.0),
            _simulation("b-0", "b", 0, 1.0),
            _simulation("b-1", "b", 1, 0.0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "tau-results.json"
            export_path = root / "tau-export.json"
            source.write_text(json.dumps(_report(simulations)), encoding="utf-8")
            exported = build_export(source, domain="retail", suite_version="1.0.1")
            export_path.write_text(json.dumps(exported), encoding="utf-8")
            scorecard = build_scorecard(
                exported["rows"],
                suite=exported["suite"],
                suite_kind="external_native",
                suite_version=exported["suite_version"],
                suite_commit=exported["suite_commit"],
                native_metric=exported["native_metric"],
                native_metric_value=exported["native_metric_value"],
                native_report_sha256=hashlib.sha256(export_path.read_bytes()).hexdigest(),
                native_report_path=export_path,
                native_grader=exported["native_grader"],
                native_environment={"runner": "isolated", "runtime": "python-3.12", "platform": "linux-x86_64"},
                native_run_complete=exported["complete"],
                model="local-action-policy",
                harness="model-only",
            )
        self.assertEqual(scorecard["verified_success_rate"], 0.5)
        self.assertEqual(scorecard["metric_coverage"]["unsafe_attempt"], 0.0)
        self.assertIsNone(scorecard["unsafe_attempt_rate"])
        self.assertTrue(scorecard["native_run_complete"])
        self.assertIn("must not be interpreted", scorecard["metric_coverage_note"])

    def test_export_rejects_wrong_domain_and_incomplete_runs(self) -> None:
        complete = [
            _simulation("a-0", "a", 0, 1.0),
            _simulation("a-1", "a", 1, 1.0),
            _simulation("b-0", "b", 0, 1.0),
            _simulation("b-1", "b", 1, 1.0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "results.json"
            path.write_text(json.dumps(_report(complete)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native domain"):
                build_export(path, domain="airline", suite_version="1.0.1")

            duplicate = [
                _simulation("a-0", "a", 0, 1.0),
                _simulation("a-0-again", "a", 0, 1.0),
                _simulation("a-1", "a", 1, 1.0),
                _simulation("b-0", "b", 0, 1.0),
            ]
            path.write_text(json.dumps(_report(duplicate)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate task/trial"):
                build_export(path, domain="retail", suite_version="1.0.1")

            infrastructure_error = list(complete)
            infrastructure_error[0] = _simulation(
                "a-0", "a", 0, 0.0, termination="infrastructure_error"
            )
            path.write_text(json.dumps(_report(infrastructure_error)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "infrastructure error"):
                build_export(path, domain="retail", suite_version="1.0.1")

    def test_export_reads_directory_layout_and_checks_index(self) -> None:
        simulations = [
            _simulation("a-0", "a", 0, 1.0),
            _simulation("a-1", "a", 1, 1.0),
            _simulation("b-0", "b", 0, 1.0),
            _simulation("b-1", "b", 1, 1.0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            simulation_dir = root / "simulations"
            simulation_dir.mkdir()
            report = _report([])
            report["simulation_index"] = [{"id": item["id"]} for item in simulations]
            (root / "results.json").write_text(json.dumps(report), encoding="utf-8")
            for simulation in simulations:
                (simulation_dir / f'{simulation["id"]}.json').write_text(json.dumps(simulation), encoding="utf-8")
            result = build_export(root, domain="retail", suite_version="1.0.1")
        self.assertEqual(result["native_metrics"]["task_runs"], 4)
        self.assertEqual(result["native_metrics"]["average_reward"], 1.0)
        self.assertEqual(len(result["native_source"]["files"]), 5)

    def test_export_rejects_directory_index_drift(self) -> None:
        simulation = _simulation("a-0", "a", 0, 1.0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            simulation_dir = root / "simulations"
            simulation_dir.mkdir()
            report = _report([])
            report["simulation_index"] = [{"id": "missing"}]
            (root / "results.json").write_text(json.dumps(report), encoding="utf-8")
            (simulation_dir / "a-0.json").write_text(json.dumps(simulation), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "index does not match"):
                build_export(root, domain="retail", suite_version="1.0.1")
