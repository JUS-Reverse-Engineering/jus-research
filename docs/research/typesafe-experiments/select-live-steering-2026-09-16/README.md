# Kakashi SELECT live steering trial

Date: 2026-09-16

## Question

Did TypeSafe change the evidence plan for `jus-n4io`, narrow the claim, or
justify stopping before another invalid capture?

The owner approved one bounded live campaign. The pre-review plan is preserved
in [`BASELINE.md`](BASELINE.md). It allowed two capture batches and one redesign.

## Review result

TypeSafe resolved `jev-latest` to `jev-1.13.0` in 0.388 seconds. The request used
2,300 input tokens and 294 output tokens. Monetary API cost was not available,
so it remains unknown.

| Judgment | Result |
| --- | --- |
| Experiment discrimination | Add a matched no-SELECT control at every tested delay, probability 0.90 |
| Control adequacy | Adequate only for the first-hit comparison, probability 0.61 |
| Claim scope after one protected hit | First-hit behavior only, probability 1.00 |

The frozen policy accepted the instrumentation change.

The redesigned plan required a fresh no-SELECT damage control for every delay.
A delayed SELECT run would be interpretable only if the paired control proved
that the corresponding CPU attack lowered P1 HP without SELECT.

Artifacts: [`typesafe-request.json`](typesafe-request.json) and
[`typesafe-response.json`](typesafe-response.json).

## Harness review

The existing `atns43_cancel.gdb` path is unsafe for this trial. It still reads
fixed HP addresses, does not disable auto-heal, and receives the primary
Kakashi fixture hash instead of the fight-CPU fixture hash through the current
`map_kit` path. No capture used that path.

A read-only Luna review independently found the same matched-delay gap before
the TypeSafe response arrived. Luna also found the unsafe capture path. TypeSafe
therefore confirmed a useful action change, but it did not uniquely discover
it.

## Live outcome

The emulator launched with no existing holder or melonDS process. The command
to load `pc-kakashi-npc-jotaro-fightcpu` produced no acknowledgment within 30
seconds. The bridge then reported `dead`, and the heartbeat remained frozen at
frame 43. The launch output already reported frame 43, so the record does not
prove that the load command caused the first session to stop.

The repository's documented health recovery stopped the unresponsive process,
relaunched melonDS, and issued a reload of the same fixture. The second process
also failed the independent heartbeat control. Its heartbeat remained frozen
at frame 24 and the bridge again reported `dead`. The trial locates the failure
around launch and state loading, but it does not attribute the failure to the
fixture.

The batch stopped at that deterministic precondition failure. No battle root,
identity, auto-heal, HP, damaging-hit, or SELECT measurement was accepted. No
capture artifact exists, and the live result says nothing about SELECT.

The emulator holder was cleared and no melonDS process remained after cleanup.
[`live-output.txt`](live-output.txt) preserves the relevant command output.

## Post-capture continuation

The launch failure was a process-lifetime artifact: melonDS had been launched
from a command that ended before later interactions. Keeping launch, load, and
capture in one foreground command made state loading reliable.

A no-menu matched pair then resolved the behavior question. At the corresponding
CPU hit, the control entered state 8 and lost HP while the SELECT trial entered
state 20 and retained HP. TypeSafe's post-capture review classified this as
SELECT-associated protection (0.81), and limited the supported claim to one
corresponding hit (0.91). Artifacts:
[`postcapture-request.json`](postcapture-request.json),
[`postcapture-response.json`](postcapture-response.json), and the live
live capture results.

## Decision

Keep the TypeSafe steering pattern for narrow claim classification and retain
Luna for repository and raw-artifact checks. TypeSafe need not replace Luna or
uniquely discover a finding to earn its place; the efficiency gain comes from
giving each model bounded work that matches its strengths. The accepted matched
capture closes `jus-n4io`; exact duration and consumption semantics remain open.
