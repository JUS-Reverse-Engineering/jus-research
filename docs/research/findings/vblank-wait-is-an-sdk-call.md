# The main loop waits for vertical blank through an SDK call

Tracker item: `jus-vblank-wait-sdk-call-du3c`. Static read, 2026-11-13 intake, re-derived against
our ROM. Credit: pakoito's jus-online (private recompilation project).

The main loop's frame wait is a call to the SDK interrupt wait, not a `swi` in game code.

## Static evidence

The main loop calls 0x020552A8 (OS_WaitVBlankIntr) from 0x02042250 (`bl 0x020552A8`). That
function first calls the Thumb stub 0x020000EA, which is `svc 3`, and then waits through
OS_WaitIrq at 0x02051B0C.

## What it corrects

The 2026-09-12 search found zero `swi` instructions in game code and no DISPSTAT or VCOUNT
busy-loop. That search was right about what it looked for, but its conclusion that ARM9 has
no VBlank wait was wrong: the wait is an SDK library call, so an ARM-mode grep for `swi`
cannot find it.

## What it answers

It answers the open hardware vsync point gap in the physics reference: the vsync point is
the 0x020552A8 call at 0x02042250 in the main loop. Where that sits relative to the
accumulator loop is still to be stated from the call order.

The code is byte-identical across the two ROM dumps.
