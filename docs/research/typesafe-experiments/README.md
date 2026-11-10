# TypeSafe evidence-review experiments

These trials test whether a typed reviewer catches a specific unsupported step
without discarding measurements that remain valid. TypeSafe outputs are compared
with one-shot structured reviewers over the same blinded packet. Model output is
evaluation evidence, not a source of game facts.

The operating policy is the
TypeSafe and Luna routing policy. TypeSafe handles
bounded claim and control judgments. Luna handles repository exploration, raw
artifact review, and diagnosis. The project does not require TypeSafe to find a
fact that Luna missed.

| Trial | TypeSafe result | Structured reviewer |
| --- | --- | --- |
| [Projectile causal overclaim](projectile-causality-2026-09-16/README.md) | Rejected hit cause; preserved early termination | `gpt-5.6-sol`, same result |
| [Landing-lag generalization](landing-lag-generalization-2026-09-16/README.md) | Found non-independent input; preserved 23 within-run fits | `gpt-5.6-luna`, same result |
| [Mode-gate causality](mode-gate-causality-2026-09-16/README.md) | Found missing failing-mode execution; preserved mode-2 path | `gpt-5.6-luna`, same result |
| [Projectile matched causal review](projectile-matched-causality-2026-09-16/README.md) | Rejected unsupported contact cause and accepted age-threshold control | `gpt-5.6-luna`, same split |
| [Kakashi SELECT live steering](select-live-steering-2026-09-16/README.md) | Added matched delay controls, then limited the accepted capture to one corresponding protected hit | `gpt-5.6-luna`, same control gap plus raw capture and harness checks |

Each directory contains the exact TypeSafe request and response, ordinary-review
prompt and schema, raw structured response, source basis, interpretation, and
limitations.

The live steering directory uses a
[frozen baseline](select-live-steering-2026-09-16/BASELINE.md) instead of an
ordinary-reviewer prompt because the comparison is the frozen action, the
policy-proposed action, and the observed run outcome.
