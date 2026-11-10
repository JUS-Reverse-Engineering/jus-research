# Projectile matched causal review

Date: 2026-09-16

## Question

After removing the explicit diagnosis from the original projectile packet, can
a reviewer reject an unsupported contact cause and accept a matched teardown
cause that has a direct control-flow link? This guards against a reviewer that
rejects every causal claim.

Case A contains the two positive-lifetime kind-`0x00` event sequences and the
actual probe coverage from
`docs/research/feel-captures/entity-kinds-2026-09-12/RESULTS.md`.
It does not use the words from the later correction, owner testimony, or the
original report's proposed contact-gate interpretation.

Case B is the matched positive control. Static analysis shows that the
`0x0216C958` age-threshold branch calls shared destructor `0x02083648`, returning
to `0x216ca90`. The live destructor probe recorded that return address. The
claim is deliberately scoped to the projectile subsystem because the live call
was not attributed to a named kind or element. The static basis is also recorded
in `docs/research/Battle-Engine-Map.md`.

TypeSafe and the Luna reviewer received both cases together. The Luna reviewer
ran from `<TMP>` without repository access.

## Results

TypeSafe resolved `jev-latest` to `jev-1.13.0`.

| Criterion | Case A: contact claim | Case B: age-threshold claim |
| --- | --- | --- |
| Causal status | underdetermined, 0.98 | supported, 0.98 |
| Evidence basis | missing variable, 0.69 | direct variable-to-teardown link, 1.00 |
| Preserve teardown | Noul 0.96 | Noul 0.96 |
| Scope | no causal scope, 0.97 | projectile subsystem, 1.00 |

The Luna reviewer made the same split. It rejected Case A because the probe
recorded no contact event or decisive contact state. It accepted Case B with a
scope caveat because static control flow identifies the age branch's destructor
call and the live return address proves that call site executed, but no named
element was attached to the event.

This is stronger evidence than the first projectile trial. TypeSafe did not
merely select an available skeptical label. It accepted the matched positive
control at the scope justified by the packet while rejecting the unsupported
case and retaining both sets of measurements.

Artifacts: [`typesafe-request.json`](typesafe-request.json),
[`typesafe-response.json`](typesafe-response.json),
[`ordinary-reviewer-prompt.md`](ordinary-reviewer-prompt.md), and
[`ordinary-reviewer-response.json`](ordinary-reviewer-response.json).

## Limit

Case B is matched by subsystem and teardown question, but its evidence is
static-plus-live at subsystem scope rather than a per-element trace. A future
positive control should log the element identity, age, suppression bit, branch,
and destructor call in one event chain.
