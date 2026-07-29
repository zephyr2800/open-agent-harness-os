"""Run one real CUDA 4-bit inference smoke test for a local checkpoint.

This is intentionally an opt-in diagnostic, not part of the dependency-free
CI suite. It proves that the documented serving path can load a checkpoint,
generate a parseable Action IR decision, and record the relevant hardware and
quantization provenance.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def run_smoke(*, project1_root: str | Path, checkpoint: str | Path, revision: str = "main", max_new_tokens: int = 128) -> dict[str, Any]:
    project1_root = Path(project1_root).resolve()
    if str(project1_root) not in sys.path:
        sys.path.insert(0, str(project1_root))
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("install the optional Transformers extra before running this smoke test") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("the quantized smoke test requires a CUDA-capable device")

    from model.adapter import ModelRequest
    from model.transformers_backend import TransformersActionPolicy

    load_started = time.perf_counter()
    policy = TransformersActionPolicy(
        model_id=str(checkpoint),
        revision=revision,
        device_map="auto",
        max_new_tokens=max_new_tokens,
        quantization="4bit",
        stop_on_complete_json=True,
    )
    load_ms = (time.perf_counter() - load_started) * 1000
    request = ModelRequest(
        task_id="quantized-serving-smoke",
        goal="Get the current day using the permitted tool.",
        state={"expected_tool": "get_current_day", "verified_evidence": [], "executed_actions": []},
        available_tools=("get_current_day", "abstain", "finish"),
        token_budget=48,
    )
    decision = policy.decide(request)
    action = decision.get("action") if isinstance(decision, dict) else None
    return {
        "schema": "quantized-serving-smoke/v1",
        "model_id": str(checkpoint),
        "revision": revision,
        "cuda_device": torch.cuda.get_device_name(0),
        "quantization": policy.quantization,
        "quantization_compute_dtype": policy.quantization_compute_dtype,
        "load_ms": round(load_ms, 1),
        "generation_ms": round(policy.last_generation_ms or 0.0, 1),
        "input_tokens": policy.last_input_tokens,
        "output_tokens": policy.last_output_tokens,
        "peak_vram_mib": policy.last_peak_vram_mib,
        "decision_kind": decision.get("kind") if isinstance(decision, dict) else None,
        "action_intent": action.get("intent") if isinstance(action, dict) else None,
        "valid_expected_action": bool(isinstance(action, dict) and action.get("intent") == "get_current_day"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_smoke(
        project1_root=args.project1_root,
        checkpoint=args.checkpoint,
        revision=args.revision,
        max_new_tokens=args.max_new_tokens,
    )
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
