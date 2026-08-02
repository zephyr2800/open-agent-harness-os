# Research breakthrough protocol - preregistration draft

## Question

For a fixed model and task budget, does the verifier-first harness improve
independently verified completion and reduce false completion relative to a
model-only loop? Does that effect survive task-family, tool-name, and seed
perturbations?

## Configuration factors

The primary comparison is a 2 x 3 configuration matrix:

| Factor | Conditions |
|:---|:---|
| Policy | promoted compact policy; scale-branch policy |
| Harness | model-only; verifier-first repair; verifier-backed post-training |
| Search control | matched-budget independent model-only attempts selected only by the immutable verifier |

The policy, tokenizer, task specification, output budget, decoding settings,
and environment revision are held fixed within each comparison. The evaluator,
independent verifier, trace recorder, and promotion rules are not editable by
the policy.

## Splits and perturbations

- Training data may contain only the training split and verifier-backed
  reference trajectories whose provenance is recorded.
- The primary holdout is authored after the training curriculum and has new
  names, payload markers, paraphrases, and state values.
- New markers alone are not enough: promotion and RL authorization require a
  passing direct-contract audit and a bound, identifier-normalized
  template-affinity audit. The latter is a conservative local screen, not a
  semantic-novelty proof.
- `task-spec-author-holdout-v1.json` is the current post-freeze local
  diagnostic for evidence-to-action transformations and a required slice of
  promotion protocol `v2`. It is published and therefore is not a substitute
  for a hidden or native external suite.
- At least three decoding seeds are required for a completed checkpoint; an
  independent training seed is preferred for a paper claim.
- A stochastic matrix must record its exact temperature and nucleus threshold
  with every run and use the same values for every compared arm. Sampling
  controls are invalid when sampling is disabled.
- The active v2 protocol requires stochastic seeds 0, 1, and 2 and records
  both the executable policy and harness source trees. The decision gate
  recomputes those records and rejects source drift.
- Tool aliases, reordered tool descriptions, long-horizon state dependencies,
  insufficient information, confirmation boundaries, and indirect injection
  are separate slices.
- An external run must preserve the external suite's environment, grader, and
  native metric. It must not be relabeled as a local Action IR score.

## Primary metrics

The machine-readable `agent-eval-scorecard/v1` is the required report shape.
The primary result is macro-average verified completion across task families,
with the following reported beside it:

- micro verified completion and 95% Wilson interval by family;
- protocol-valid rate and trace-valid rate;
- runtime/independent-replay agreement;
- false-completion rate and premature-finish rejections;
- unsafe-attempt rate and safe-abstention rate on adversarial tasks;
- mean output tokens, wall-clock seconds, and peak device memory when
  available;
- model, harness, suite version/commit, seed, task-spec hash, and budget.

The scorecard must expose the worst family. A launch or research headline may
not use the micro average to hide a zero-success long-horizon or safety slice.

## Promotion criteria

### Research candidate

A candidate result requires complete rows, valid traces, 100% runtime/replay
agreement, no unknown actions, no unsafe action execution, and positive
pre-registered interaction on at least two nontrivial families. Confidence
intervals and the exact task-spec hash must be published. This is a candidate
for external review, not a breakthrough claim.

### Breakthrough claim

A breakthrough claim additionally requires:

1. a disjoint author-held-out suite that passes both isolation screens;
2. at least three decoding seeds and, where practical, independent training
   replication;
3. a model-only versus verifier-first versus post-trained ablation;
4. a matched-budget task-level search control, so extra attempts are not
   misreported as a harness improvement;
5. family-level improvement that is not explained by a single easy slice;
6. a native external-suite result with its native metric;
7. independent replay and artifact/state verification for every reported
   success; and
8. an explicit negative-result section covering reward hacking, regressions,
   unsafe attempts, and cost/latency tradeoffs.

## Post-training order

1. Freeze the pre-RL baseline and scorecard.
2. Generate only verifier-backed rollouts from the frozen environment.
3. Separate rewards for protocol validity, state transition, evidence-grounded
   finalization, safe abstention, and efficiency.
4. Run a small RL smoke test with a held-out control; stop if reward rises while
   replay agreement, safety, or external-bar performance falls.
5. Run the full post-training comparison with unchanged holdout and external
   suite.
6. Publish the reward definition, rollout counts, seed, checkpoint hashes,
   optimizer settings, and failed runs before making any improvement claim.

## Product launch boundary

The immediate launch target is a local developer preview: typed actions,
authority gates, independent evidence, replay, local MCP/HTTP surfaces,
bounded resource use, and explicit model-endpoint locality. A production
multi-tenant service is a separate release requiring identity lifecycle,
secret rotation, distributed quotas, monitoring, network isolation, usability
sessions, licensing/provenance review, and deployment-specific security
review.
