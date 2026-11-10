Review the evidence packet below. Separate direct observations, derived values,
and the proposed mechanic. Decide whether the formula is supported as a general
rule, contradicted by the cross-run test, or only a within-run fit. Do not lower
confidence merely because the sample is small. Check whether the proposed input
was independently known before each measured outcome. Preserve valid
measurements even if the general explanation fails. Return only JSON matching
the supplied schema.

The claim is: "Landing lag is the unplayed tail of the airborne animation:
lag = animation_length - obj+0x72_at_landing + 1." Two runs promoted this to a
mechanic after matching 12/12 and 11/11 rows.

Landing was the frame M+0x78 equaled 0x02. The elapsed value was obj+0x72 at
landing. "Animation length" was obj+0x72 on the frame state returned to zero in
a separate no-input probe from the same run. Lag was the first frame obj+0x18
equaled 1 with RIGHT held, minus the landing frame. The probe recorded the state
path, including the frame when control returned. It did not read a content-level
animation length independently from ROM or another source.

A later test used animation lengths recorded in prior runs to preregister fresh
predictions. Six of 21 matched exactly and 15 missed. Hits included Kenshin
plain jump 13/13, Kenshin fast-fall 13/13, Kenshin mashed air B 25/25, Yusuke
late air B 25/25, and Kakashi late air B 25/25. Misses included Kenshin double
jump 19/22, Kenshin one air B 26/25, Kenshin double jump plus air B 7/34,
Yusuke late air Y 21/25, and Kakashi late air Y 21/25.

Identify the unsupported inference, list the observations that survive, state
the missing evidence, and name the smallest decisive follow-up.
