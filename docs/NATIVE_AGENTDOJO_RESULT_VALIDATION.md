# Native AgentDojo result validation

`experiments.agentdojo_native_result_validator` validates one completed
checkpoint-bound AgentDojo run before it can be summarized as local external
evidence:

```powershell
python -m experiments.agentdojo_native_result_validator `
  --run-manifest C:\path\to\native-run\run_manifest.json `
  --output C:\path\to\new-agentdojo-validation.json
```

It requires a completed zero-return-code launcher manifest, a clean-audit-bound
merged checkpoint, the pinned AgentDojo benchmark entrypoint and commit, exact
registered selectors, loopback `openai-compatible` policy adapter, loaded
checkpoint health check, adapter-log record, and current Project 1/harness
source-tree fingerprints. It verifies every recorded native JSON file by hash
and byte count, then rejects any missing, extra, selector-mismatched, modified,
or errored task result.

For a clean run, the report's primary metric is AgentDojo's native
`TaskResults.utility` rate. Clean rows set `security=true` by construction, so
the validator explicitly does not present that field as an injection-security
metric. For the registered `direct`-injection condition, it reports utility,
security, and joint utility-and-security rates on user-task/injection-task
pairs. It reports the injection-task-as-user-task controls separately so they
cannot be mistaken for the paired security result.

The resulting status is `locally_consistent`, not independently attested. It
does not establish independent trace replay, full-suite coverage, a public
leaderboard score, calibrated cost, or safety beyond the exact registered
direct-injection pairs. A successful dry plan or a historical log without this
validator is not a new native benchmark result.
