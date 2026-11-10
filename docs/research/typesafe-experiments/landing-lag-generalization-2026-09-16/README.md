# Landing-lag generalization review

Date: 2026-09-16

> **Correction 2026-09-23 (`jus-wmqi.6.4`,
> [anim-timing.md](../../../rebuild/anim-timing.md) §7):** the packet and
> [`ordinary-reviewer-prompt.md`](ordinary-reviewer-prompt.md) treat
> `obj+0x72` as animation-elapsed frames. It is an input-run counter (frames the
> input word has stayed the same, reset on change or at 600; ov6 sampler
> `0x02161148`). The review's verdict still stands: the within-run fit was an
> identity and the rule is retracted. What falls is the idea that an
> "independent content-level animation length" would rescue the formula; no
> animation length enters it. ALMT frame counts are in anim-timing.md. The
> prompt file is kept verbatim as the record of what reviewers saw.

## Question

Can a reviewer distinguish a perfect within-run fit from a mechanic that
predicts an independent run, while preserving the measurements that produced
the fit?

The packet reconstructs the formula proposed in
`docs/research/feel-captures/register-2026-09-03/runtime-report-2.md` and
`docs/research/feel-captures/register-2026-09-03/runtime-report-9-regen-landing.md`.
Those reports matched 12/12 and 11/11 rows. The packet also includes the
preregistered cross-run outcome from
`docs/research/feel-captures/register-2026-09-03/runtime-report-11-landing-activity.md`:
6/21 exact predictions.

The correction and replacement mechanic were withheld. TypeSafe and the Luna
reviewer received the same measurements, derivation method, and holdout result.
The Luna reviewer ran from `<TMP>` without repository access.

## Results

TypeSafe resolved `jev-latest` to `jev-1.13.0`.

| Criterion | Answer | Distribution |
| --- | --- | --- |
| General claim | `unsupported_within_run_fit` | 0.56 unsupported, 0.44 contradicted by holdout |
| Primary problem | `input_not_independent` | 1.00 |
| Preserve measurements | yes | Noul 0.88 |

The split on the first question is reasonable. The packet supports both labels:
the within-run evidence is an outcome-derived fit, and the 6/21 holdout conflicts
with general prediction. The decisive result is that TypeSafe assigned 1.00 to
the non-independent input and 0.00 to insufficient repetitions.

The Luna structured reviewer returned `contradicted`. It identified that the
no-input probe's control-return frame supplied the supposed animation-length
input, preserved the 12/12 and 11/11 measurements, and proposed reading an
independent content-level animation length before predicting a fresh run.

Both reviewers passed the rubric. Neither substituted low confidence or more
repetitions for the missing independent input.

Artifacts: [`typesafe-request.json`](typesafe-request.json),
[`typesafe-response.json`](typesafe-response.json),
[`ordinary-reviewer-prompt.md`](ordinary-reviewer-prompt.md), and
[`ordinary-reviewer-response.json`](ordinary-reviewer-response.json).

## Limit

The packet states the 6/21 holdout and explains how animation length was
obtained. This tests whether reviewers classify the failure correctly. It does
not test whether they would discover the circular input from raw logs alone.
