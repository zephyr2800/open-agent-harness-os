# Native τ³ result validation

The τ³ launcher preserves the benchmark's native results.json beside its
completed run manifest. Run the validator only after an executed run has
status completed:

~~~powershell
python -m experiments.tau2_native_result_validator --run-manifest C:\path\to\native-run\run_manifest.json --output C:\path\to\new-native-validation.json
~~~

The validator rejects a result unless it is tied to the clean merged
checkpoint and audit, the source-bound pinned τ³ checkout, the exact
telecom/base task list and budget, the loopback local policy, the recorded
adapter command and health check, the compatibility runner, and a
byte-consistent preserved copy of the official results file. The launcher also
uses the pinned τ³ runtime's own Pydantic Results model before preserving the
file. The validator rejects any native simulation terminated with
infrastructure_error.

It also recomputes the recorded Project 1 and harness runtime source trees.
Changing either tree after execution invalidates local result consistency.

The validated primary metric is mean_reward from τ³'s own reward_info.reward,
with reward_one_rate, per-family reward, native message availability, duration,
and reported costs alongside it. Reported LiteLLM costs are deliberately not
treated as price-validated.

This validator does not convert missing evidence into zeroes or false values.
It explicitly labels independent trace replay, safety, interactive user
simulation, and calibrated cost as not measured. A completed solo run is a
native τ³ telecom/base result, not evidence for those distinct claims.

The resulting status is locally_consistent. File records detect accidental
mixing or modification relative to the launcher manifest, but they are not an
independent cryptographic attestation: a party able to rewrite both a manifest
and its artifacts can recompute those hashes. Do not call this report
cryptographically tamper-proof without a separate signed provenance system.
