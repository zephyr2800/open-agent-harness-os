"""Measure NVIDIA GPU device energy for a bounded evaluation command.

The NVIDIA driver exposes device draw, not per-process or whole-system power.
This utility therefore writes an auditable *whole-device* sidecar: it is valid
for a quiet, exclusive evaluation window, but must not be represented as the
energy of one model when other GPU workloads were active.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class GpuPowerSample:
    """One point-in-time device telemetry reading."""

    monotonic_seconds: float
    wall_time_unix: float
    device_index: int
    power_watts: float
    memory_used_mib: float | None
    utilization_percent: float | None


def _number(value: str, field: str, *, required: bool) -> float | None:
    cleaned = value.strip()
    if cleaned.lower() in {"n/a", "na", "[n/a]", ""}:
        if required:
            raise ValueError(f"nvidia-smi did not report {field}")
        return None
    try:
        result = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"invalid {field} from nvidia-smi: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite {field} from nvidia-smi: {value!r}")
    return result


def parse_nvidia_smi_csv(
    output: str,
    *,
    expected_device_index: int,
    monotonic_seconds: float,
    wall_time_unix: float,
) -> GpuPowerSample:
    """Parse one ``nvidia-smi --format=csv,noheader,nounits`` response."""

    rows = [line.strip() for line in output.splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError(f"expected exactly one GPU telemetry row, received {len(rows)}")
    fields = [field.strip() for field in rows[0].split(",")]
    if len(fields) != 4:
        raise ValueError(f"expected four GPU telemetry fields, received {len(fields)}")
    device_value = _number(fields[0], "index", required=True)
    assert device_value is not None
    device_index = int(device_value)
    if device_index != device_value or device_index != expected_device_index:
        raise ValueError(
            f"nvidia-smi returned device index {fields[0]!r}; expected {expected_device_index}"
        )
    power_watts = _number(fields[1], "power.draw", required=True)
    assert power_watts is not None
    if power_watts < 0:
        raise ValueError(f"negative power.draw from nvidia-smi: {power_watts}")
    return GpuPowerSample(
        monotonic_seconds=monotonic_seconds,
        wall_time_unix=wall_time_unix,
        device_index=device_index,
        power_watts=power_watts,
        memory_used_mib=_number(fields[2], "memory.used", required=False),
        utilization_percent=_number(fields[3], "utilization.gpu", required=False),
    )


class NvidiaSmiProbe:
    """Read one NVIDIA device telemetry sample without third-party packages."""

    def __init__(
        self,
        *,
        device_index: int = 0,
        executable: str = "nvidia-smi",
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        monotonic: Callable[[], float] = time.monotonic,
        wall_time: Callable[[], float] = time.time,
    ) -> None:
        if device_index < 0:
            raise ValueError("device_index must be non-negative")
        self.device_index = device_index
        self.executable = executable
        self._runner = runner
        self._monotonic = monotonic
        self._wall_time = wall_time

    def sample(self) -> GpuPowerSample:
        completed = self._runner(
            [
                self.executable,
                f"--id={self.device_index}",
                "--query-gpu=index,power.draw,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown nvidia-smi error").strip()
            raise RuntimeError(f"nvidia-smi failed with exit code {completed.returncode}: {detail}")
        return parse_nvidia_smi_csv(
            completed.stdout,
            expected_device_index=self.device_index,
            monotonic_seconds=self._monotonic(),
            wall_time_unix=self._wall_time(),
        )


def integrate_energy_joules(samples: Sequence[GpuPowerSample]) -> float:
    """Integrate sampled power with the trapezoidal rule."""

    if len(samples) < 2:
        raise ValueError("at least two power samples are required for energy integration")
    joules = 0.0
    for previous, current in zip(samples, samples[1:]):
        elapsed = current.monotonic_seconds - previous.monotonic_seconds
        if elapsed < 0:
            raise ValueError("power samples are not ordered by monotonic time")
        joules += (previous.power_watts + current.power_watts) * elapsed / 2.0
    return joules


def build_energy_report(
    *,
    samples: Sequence[GpuPowerSample],
    device_index: int,
    sample_interval_seconds: float,
    command: Sequence[str],
    command_returncode: int | None,
    collection_errors: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a claim-safe, machine-readable device-energy sidecar."""

    if sample_interval_seconds <= 0:
        raise ValueError("sample_interval_seconds must be positive")
    serialized_samples = [asdict(sample) for sample in samples]
    complete = len(samples) >= 2 and not collection_errors and command_returncode == 0
    energy_joules: float | None = None
    elapsed_seconds: float | None = None
    if len(samples) >= 2:
        try:
            energy_joules = integrate_energy_joules(samples)
            elapsed_seconds = samples[-1].monotonic_seconds - samples[0].monotonic_seconds
        except ValueError as exc:
            collection_errors = [*collection_errors, str(exc)]
            complete = False
    average_power_watts = energy_joules / elapsed_seconds if energy_joules is not None and elapsed_seconds and elapsed_seconds > 0 else None
    return {
        "schema": "gpu-energy/v1",
        "status": "complete" if complete else "incomplete",
        "measurement_scope": "whole_nvidia_device",
        "attribution_limit": "not per-process; not whole-system; requires an exclusive evaluation window for per-run use",
        "device_index": device_index,
        "sample_interval_seconds": sample_interval_seconds,
        "sample_count": len(samples),
        "command": list(command),
        "command_returncode": command_returncode,
        "sampling_elapsed_seconds": elapsed_seconds,
        "energy_joules": energy_joules,
        "energy_watt_hours": energy_joules / 3600.0 if energy_joules is not None else None,
        "average_power_watts": average_power_watts,
        "collection_errors": list(collection_errors),
        "samples": serialized_samples,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="energy sidecar JSON to write")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--sample-seconds", type=float, default=1.0)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command to measure; place after --")
    args = parser.parse_args()
    if args.device_index < 0:
        parser.error("--device-index must be non-negative")
    if args.sample_seconds <= 0:
        parser.error("--sample-seconds must be positive")
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    probe = NvidiaSmiProbe(device_index=args.device_index)
    samples: list[GpuPowerSample] = []
    collection_errors: list[str] = []
    child: subprocess.Popen[Any] | None = None
    returncode: int | None = None
    try:
        child = subprocess.Popen(command)
        while True:
            try:
                samples.append(probe.sample())
            except (OSError, RuntimeError, ValueError) as exc:
                collection_errors.append(f"{type(exc).__name__}: {exc}")
            returncode = child.poll()
            if returncode is not None:
                break
            time.sleep(args.sample_seconds)
        try:
            samples.append(probe.sample())
        except (OSError, RuntimeError, ValueError) as exc:
            collection_errors.append(f"{type(exc).__name__}: {exc}")
    except OSError as exc:
        collection_errors.append(f"command launch failed: {type(exc).__name__}: {exc}")
        returncode = None
    report = build_energy_report(
        samples=samples,
        device_index=args.device_index,
        sample_interval_seconds=args.sample_seconds,
        command=command,
        command_returncode=returncode,
        collection_errors=collection_errors,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output, report)
    print(json.dumps({
        "status": report["status"],
        "energy_joules": report["energy_joules"],
        "energy_watt_hours": report["energy_watt_hours"],
        "sample_count": report["sample_count"],
        "output": str(output),
    }, indent=2, sort_keys=True))
    if returncode not in (None, 0):
        return returncode
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
