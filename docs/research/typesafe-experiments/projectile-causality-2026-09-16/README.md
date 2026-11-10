# Projectile causal-overclaim review

Date: 2026-09-16
Tracker item: `jus-n35o`

## Question

Can a reviewer reject the unsupported step from observed early projectile
termination to a hit-driven explanation while preserving the observations that
the probe did record?

This is the first trial proposed in the typesafe-experiments primer.
It uses the kind-`0x00` projectile claim later corrected under `jus-68cu`.

## Blinding and source packet

The packet was reconstructed from the pre-correction version of
`docs/research/feel-captures/entity-kinds-2026-09-12/RESULTS.md` at commit
`a1555570`. That revision called two instances "early/hit-driven" and said they
cross-validated the mechanism. It also described a code path as a plausible
hit/contact flag test while acknowledging that the live run had not watched the
bit change.

The packet preserved these recorded observations:

- instance A: creation at lifetime 32, checks at 32 and 31, then an adjacent
  destructor event with return address `0x216f9cc`;
- instance B: creation at lifetime 30, checks at 30 and 29, then an adjacent
  destructor event with the same return address;
- other kind-`0x00` instances had a lifetime-countdown shape.

It also preserved the limitations stated in
`scripts/gdb/e68cu_kind_despawn_probe.gdb`: destructor adjacency is heuristic,
the probe had no frame counter, it did not watch the proposed flag, and it had
no breakpoint or logged field for contact, collision, hit, damage, or knockback.

The packet excluded the correction at current `RESULTS.md:377`, the corrected
label, and the owner testimony cited by the correction. The held-out expected
answer was therefore based on evidence coverage alone: early termination is
observed, but hit causation is not instrumented.

## Reviewers

TypeSafe received [`typesafe-request.json`](typesafe-request.json) through the
documented `POST /v1/systemone` endpoint with requested model `jev-latest`. The
service resolved that alias to `jev-1.13.0`. The questions separately tested the
causal status, the primary failure mode, and preservation of the observation.
The question design follows the live TypeSafe documentation for
[structured state](https://docs.typesafe.ai/concepts/state.md),
[Choice](https://docs.typesafe.ai/primitives/choice.md), and
[confidence](https://docs.typesafe.ai/confidence.md).

The ordinary reviewer was a one-shot `gpt-5.6-sol` Codex call with no reasoning
effort, a read-only sandbox, the prompt in
[`ordinary-reviewer-prompt.md`](ordinary-reviewer-prompt.md), and the JSON schema
in [`ordinary-reviewer-schema.json`](ordinary-reviewer-schema.json). Its prompt
contained the same evidence and limitations. The process made no repository
tool calls during review, so it did not read the held-out correction.

## Results

TypeSafe passed all three criteria. Its raw response is in
[`typesafe-response.json`](typesafe-response.json).

| Criterion | TypeSafe answer | Strength |
| --- | --- | --- |
| Status of hit causation | `underdetermined_missing_causal_observation` | probability 1.00, confidence 1.00 |
| Primary failure | `missing_causal_variable` | probability 1.00, confidence 1.00 |
| Preserve early termination | yes | Noul 0.92 |

The ordinary structured-output reviewer also passed. Its raw response is in
[`ordinary-reviewer-response.json`](ordinary-reviewer-response.json). It called
the claim `underdetermined`, identified the unsupported inference as hit/contact
causation, preserved both positive-lifetime event sequences, and asked for the
contact-gate result tied to the projectile element at the teardown branch. It
also noticed a second, valid limitation: the shared-destructor event was only
heuristically attributed to each element.

## Interpretation

This trial does not distinguish TypeSafe from the ordinary reviewer on accuracy.
Both caught the exact error Astra identified. TypeSafe did so in 166 output
tokens and exposed distributions that a deterministic policy can consume. The
ordinary reviewer supplied a more useful explanation and proposed precise next
instrumentation, at much higher output and inference cost.

TypeSafe's useful result was not merely low confidence. It assigned full
probability to the specific missing-causal-observation category and 0.00 to
"too few repetitions." It also retained the measured early-termination pattern
at 0.92 after rejecting the explanation. That is the behavior this trial was
designed to test.

The trial is deliberately favorable to both reviewers. The packet plainly lists
the missing signals, and the TypeSafe answer set contains the correct failure
mode. The result demonstrates classification when the application has already
defined the important distinction. It does not show that TypeSafe can discover a
new evidence failure, generalize across other reverse-engineering claims, or
replace a reasoning reviewer. A useful next evaluation set should include the
landing-lag and unreachable-byte cases, plus matched supported controls and
harder cases where the absent causal variable is only implied by probe coverage.

No canonical fact was changed from either model output.
