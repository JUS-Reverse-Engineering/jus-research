# Mode-gate causal review

Date: 2026-09-16

## Question

Can a reviewer reject a clean rest-state correlation when the proposed check
does not execute in the failing mode, while retaining the valid mode-2 mechanism
and measurements?

The packet comes from `jus-2cu`,
`docs/research/findings/p167-installer-caller-and-the-bss-gate.md`, and
`docs/research/Battle-Engine-Map.md`. It includes the static
byte check, the four-mode rest-state split, the same-session mode-2 control, and
the raw zero-hit result for mode 12. It omits the later interpretation and the
resolved upstream gate.

TypeSafe and the Luna reviewer received the same packet. The Luna reviewer ran
from `<TMP>` without repository access.

## Results

TypeSafe resolved `jev-latest` to `jev-1.13.0`.

| Criterion | Answer | Strength |
| --- | --- | --- |
| Mode-12 causal status | `underdetermined_missing_execution` | probability 0.98, confidence 0.97 |
| Primary problem | `failing_mode_did_not_reach_check` | probability 1.00 |
| Preserve observations | yes | Noul 0.85 |

The Luna structured reviewer also returned `underdetermined`. It named the exact
unsupported step: inferring that mode 12 took the byte's zero branch when the
byte-check breakpoint recorded no mode-12 execution. It preserved the static
path, rest-state values, and the live mode-2 poll. Its next check moves upstream
from `0x0214DB24` in mode 12.

Both reviewers passed. They treated the healthy mode-2 control as evidence that
the no-hit result was valid, rather than dismissing it as a failed instrument or
asking only for repetitions.

Artifacts: [`typesafe-request.json`](typesafe-request.json),
[`typesafe-response.json`](typesafe-response.json),
[`ordinary-reviewer-prompt.md`](ordinary-reviewer-prompt.md), and
[`ordinary-reviewer-response.json`](ordinary-reviewer-response.json).

## Limit

The packet exposes the breakpoint counts. This tests whether a reviewer can
interpret execution coverage correctly. It does not ask the reviewer to recover
the upstream branch from raw disassembly.
