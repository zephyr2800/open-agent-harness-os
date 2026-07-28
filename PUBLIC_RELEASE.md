# Public release boundary

This repository is the public harness and research-methods release. It is
deliberately separate from local model checkpoints and private training
artifacts.

Included:

- Harness implementation, protocol, runtime, safety, replay, and MCP code
- Synthetic benchmark generators and task fixtures
- Tests and launch-preflight tooling
- Research reports, claim controls, literature notes, and reproducibility
  instructions
- The source implementation of the companion Action IR policy project

Excluded:

- Any model weights or adapter files
- Generated matrix/result dumps and private traces
- Raw remediation curricula and machine-specific work directories
- Credentials, tokens, local absolute paths, and watcher processes
- Claims that the incomplete 9B matrix is a promotion, breakthrough, or public
  autonomous-agent benchmark result

Before a public model release, independently review upstream weight licenses,
training-data provenance, benchmark terms, external-suite results, and
security/operations requirements.
