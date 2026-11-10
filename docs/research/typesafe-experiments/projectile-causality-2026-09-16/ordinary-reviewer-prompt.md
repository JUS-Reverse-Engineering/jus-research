Review the evidence packet below. Separate direct observations from interpretations.
Decide whether the stated conclusion is supported, contradicted, or underdetermined
by the recorded probe fields. Identify the single most important unsupported
inference, state exactly what the packet does establish, and name the smallest
additional observation needed to test the proposed cause.

Do not lower confidence merely because the sample is small. Evaluate whether the
recorded variables can establish the claimed causal link at all. Return only JSON
matching the supplied schema.

## Evidence packet

The claim under review is: "Kind 0x00 has an early hit-driven teardown condition.
Two instances were destroyed within two update checks of creation while lifetime
remained about 29-31." The report marked the two-trigger conclusion CONFIRMED_LIVE
and described the proposed contact gate as plausible.

Instance A recorded creation at lifetime 32, update checks at lifetimes 32 and 31,
then an immediately following shared-destructor event with return address
0x216f9cc. Instance B recorded creation at lifetime 30, update checks at lifetimes
30 and 29, then an immediately following shared-destructor event with the same
return address. Other kind-0x00 instances showed lifetime countdown followed by
teardown near lifetime zero.

The probe broke at ObjShot creation, three candidate update/despawn-check entries,
and the shared pooled-entity destructor. It logged element pointer, kind, lifetime,
owner, destructor argument and return address, plus a monotonic sequence number.
The destructor argument is not guaranteed to equal the ObjShot element, so
adjacency is a heuristic teardown signal rather than direct per-element
attribution. The probe has no frame counter, and update-check counts are only a
proxy for elapsed frames.

The original report described tests of bits 0x4/0x8 and a write to elem+0x26 bit
0x80 as a plausible hit/contact path. The live probe did not watch that bit or the
tested values. It recorded no collision breakpoint, contact marker, hit event,
damage event, or knockback event.
