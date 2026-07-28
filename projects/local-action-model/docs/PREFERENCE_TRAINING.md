# Preference and hard-negative training

`train.generate_preferences` creates `action-preference/v0` pairs from the
frozen task specification. Each pair contains a chosen reference decision, a
declared rejected mutation, and provenance.

The current fixture covers wrong argument values, missing artifacts, wrong
destinations, insufficient recovery, over-action when abstention is required,
and unverified finish. It is synthetic plumbing data, not an independent
preference dataset.

The research version must replace or augment these mutations with teacher or
human-reviewed trajectories whose rejection reason is supported by an
independent verifier. Preference optimization should be evaluated against
held-out tools and task states, with protocol validity, correct abstention,
verified success, and reward-hacking checks reported separately.

## RL reward boundary

`eval.reward.reward_decision` is the first environment-grounded reward
contract. It gives `+1.0` only to an independently verified task success,
penalizes invalid protocol, wrong decision kind, and failed independent
verification, and returns verifier evidence alongside the scalar. The
`train.rl_smoke` command calibrates it on the current synthetic chosen/rejected
pairs. The smoke result has mean chosen reward `1.0`, mean rejected reward
`-0.5625`, and chosen > rejected on 8/8 pairs. This is reward calibration, not
an RL training result; online GRPO/RLOO should not begin until non-synthetic
trajectories and reward-hacking tests are available.
