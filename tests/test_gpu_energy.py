from __future__ import annotations

import unittest

from experiments.gpu_energy import (
    GpuPowerSample,
    build_energy_report,
    integrate_energy_joules,
    parse_nvidia_smi_csv,
)


def _sample(timestamp: float, power: float) -> GpuPowerSample:
    return GpuPowerSample(
        monotonic_seconds=timestamp,
        wall_time_unix=1_700_000_000.0 + timestamp,
        device_index=0,
        power_watts=power,
        memory_used_mib=123.0,
        utilization_percent=50.0,
    )


class GpuEnergyTests(unittest.TestCase):
    def test_parse_nvidia_smi_csv_preserves_optional_telemetry(self) -> None:
        sample = parse_nvidia_smi_csv(
            "0, 125.5, N/A, 93\n",
            expected_device_index=0,
            monotonic_seconds=2.0,
            wall_time_unix=3.0,
        )
        self.assertEqual(sample.power_watts, 125.5)
        self.assertIsNone(sample.memory_used_mib)
        self.assertEqual(sample.utilization_percent, 93.0)

    def test_parse_nvidia_smi_csv_rejects_device_drift_and_missing_power(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 0"):
            parse_nvidia_smi_csv(
                "1, 125.5, 1, 93\n",
                expected_device_index=0,
                monotonic_seconds=2.0,
                wall_time_unix=3.0,
            )
        with self.assertRaisesRegex(ValueError, "power.draw"):
            parse_nvidia_smi_csv(
                "0, N/A, 1, 93\n",
                expected_device_index=0,
                monotonic_seconds=2.0,
                wall_time_unix=3.0,
            )

    def test_trapezoidal_energy_integration(self) -> None:
        samples = [_sample(0.0, 100.0), _sample(1.0, 200.0), _sample(3.0, 50.0)]
        self.assertEqual(integrate_energy_joules(samples), 400.0)

    def test_report_is_incomplete_when_collection_has_a_gap(self) -> None:
        report = build_energy_report(
            samples=[_sample(0.0, 100.0), _sample(2.0, 100.0)],
            device_index=0,
            sample_interval_seconds=1.0,
            command=["fake-evaluation"],
            command_returncode=0,
            collection_errors=["RuntimeError: telemetry unavailable"],
        )
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["energy_joules"], 200.0)
        self.assertEqual(report["measurement_scope"], "whole_nvidia_device")

    def test_report_is_complete_only_for_successful_command_with_two_samples(self) -> None:
        report = build_energy_report(
            samples=[_sample(0.0, 180.0), _sample(2.0, 180.0)],
            device_index=0,
            sample_interval_seconds=1.0,
            command=["fake-evaluation"],
            command_returncode=0,
        )
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["energy_joules"], 360.0)
        self.assertEqual(report["energy_watt_hours"], 0.1)
        self.assertEqual(report["average_power_watts"], 180.0)


if __name__ == "__main__":
    unittest.main()
