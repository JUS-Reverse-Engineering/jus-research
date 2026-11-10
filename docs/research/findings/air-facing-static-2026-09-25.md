# Facing in the air (static, 2026-09-25)

Where JUS changes a fighter's facing, and which states and inputs can do
it. Read from `jus_files/analysis/disasm/ov6.txt` and `arm9.txt`; no
emulator was used (it was busy). Asked by the owner's report for the
Request: "if I'm facing right and jump, I'll be facing
right the whole time. In JUS, you can change direction in the air at any
time."

Grades (as in anim-timing.md and vfx-sfx.md): **static** = read straight
from the instructions; **measured** = a live capture, cited; **inferred** =
follows from the instructions but not traced end to end or seen live; **owner** = owner
testimony ([OWNER-NOTES.md](../moveset-notes/OWNER-NOTES.md), "2026-09-25 —
Specials are neutral X and up X only; air turning"); **unknown** = not
settled by either.

Second opinion: a neutral `codex exec -m gpt-5.6-sol` read of the same
excerpts, [prompt](air-facing-static-2026-09-25/codex-prompt.txt) and
[answer](air-facing-static-2026-09-25/codex-answer.txt). §6 lists where it
agrees and where it is more careful.

## 1. The facing byte and its setter

- `0x0215E91C(obj+0x1A8)` returns the byte `Q+0x48`, where
  `Q = [[[x+8]+4]+0x64]`, or 1 when `[x+8]` is null. (static)
- arm9 `0x02083950(x, b)` calls `Q->vtable[+0x5C](Q, b)`, then notifies two
  linked objects (`0x0207AA20`, `0x0207506C`). (static) Slot `+0x5C` is
  the setter of `Q+0x48`
  ([facing-flag-change-negates-a-coordinate.md](facing-flag-change-negates-a-coordinate.md)).
  (inferred)
- `Q+0x48` is the facing: 1 = left, 0 = right. The walk helper below
  negates the walk accel when the byte it chose is non-zero, and
  physics.md §6.2 measured that the sign flips facing left. (inferred)

## 2. One helper writes both the drift and the facing

ov6 `0x0215EFC0(obj, speed, turn)`:

1. Picks a direction byte `d` from the input word `obj+0x6C`: bit `0x08`
   held gives `d = 0` (right), else bit `0x04` gives `d = 1` (left), else
   `d` = the current facing (`0x0215E91C`). With both bits held, `0x08`
   wins. (static; which bit is which side is inferred from the sign)
2. Writes `element+0x2C = d ? -speed : speed` (store `0x0215F01C`). (static)
3. Returns if `turn == 0`. Else, if `d` differs from the current facing,
   calls `0x02083950(obj+0x1A8, d)` (`0x0215F03C`) and stores
   `0x0215DA84` into `obj+0x1D4` (`0x0215F044`). (static)

`0x0215EF58(obj, speed)` wraps it with `turn = 1`. It returns 0 without
calling when `0x02159930` is true (`obj+0xA0 == 0x22`). It calls when a
horizontal bit is held, or when `obj+0xA0` is `0x15` or `0x1E`
(`0x02159910`, `0x021599D0`; with no stick those keep the current
facing). (static; what `obj+0xA0` values `0x15`, `0x1E` and `0x22` mean
is unknown, likely status effects)

Only three sites call `0x0215EF58`, and one more calls `0x0215EFC0`
directly (the full `bl` list in ov6):

| site | handler | state | turn |
|---|---|---|---|
| `0x0215D814` | `0x0215D760` | 1 walk | yes (static) |
| `0x0215E0C0` | `0x0215DF18` | 6 airborne (installed at `0x0215DC84`, `0x0215DF00`) | yes (static) |
| `0x0215E1C0` | `0x0215E118` | 7 fast fall (installed at `0x0215E104`, gated on `obj+0x6C & 0x12 == 0x12`) | yes (static) |
| `0x0215A2FC` | per-frame update | any, only while `obj+0xCC != 0` | `obj+0xF6` (below) |

## 3. The rule

- **States 6 and 7 turn the fighter the frame the stick reads the other
  way.** The state-6 handler reaches `0x0215EF58` on every frame it does
  not leave early, in the same call that reads the input word. No counter
  or timer sits between the input test and the setter call. So the turn
  has no frame delay after the input word. (static; frame lag of the
  input word itself is the usual press-to-word basis, not re-measured)
- **State 6 only: not on a frame something else starts.** The state-6 handler returns
  before the drift/turn call when any of these fire first: the landing
  test `0x0215D904`, `0x0215E470` (state 15), `0x0215E534` (state 16), an
  air attack start `0x02159D7C(obj, 1)` (gated `obj+0xDA < 2`), the fast
  fall `0x0215E0CC`, the double or wall jump `0x0215E1D0`, and the air dash
  `0x0215D860` (ability bit 8). So pressing an air attack together with
  the other direction does not turn on that frame. (static)
- **State 7 turns on every frame** (correction, 2026-09-25 refute). Its
  handler `0x0215E118`–`0x0215E1C4` checks only the landing test
  `0x0215D904`, `0x0215E470` (state 15) and `0x0215E534` (state 16) before
  `0x0215EF58`. It has no attack, jump or fast-fall check of its own, so a
  jump press in state 7 still turns that frame. (static) An earlier draft
  applied the state-6 list to state 7 too; that was wrong.
- **State 5 (double-jump start) does not turn.** Its handler `0x0215E2DC`
  never calls the helper, except the wall jump's own flip (`0x0215E320`,
  `0x0215E328`, physics.md §6.4). State 5 lasts one frame on a plain double
  jump. (static)
- **State 4 (jump squat) does not turn.** Its handler is not a caller.
  (static)
- **Turning does not change velocity.** The accel store happens before the
  `turn` test and does not depend on whether the facing changed: the same
  held direction writes the same `element+0x2C` either way. Drift in the
  air already follows the held direction whatever the facing. (static
  for these instructions; the callees behind `0x02083950` are opaque, so an
  indirect effect is not ruled out: inferred)
- **Turning re-arms the double-tap detector.** `obj+0x1D4 = 0x0215DA84` is
  the first step of the small callback chain `0x0215DA84` → `0x0215DAB0`
  (wait for neutral) → `0x0215DACC` (count to 12). This reads as the
  double-tap dash detector. (inferred)
- **Hitstun (state 8) does not turn.** None of the three callers is a
  state-8 handler ([state-code-handler-table-static.md](state-code-handler-table-static.md)
  lists 8's install in `0x0215A978`), and the state change into hitstun
  resets `obj+0xCC` to 0, which turns the fourth site off (below). Once
  hitstun ends in the air the fighter is back in state 6 and can turn.
  (inferred: the caller list covers direct `bl` only; an indirect call was
  not searched)
- **Air attacks (state 9 and the move states) keep their facing** by
  default. The attack states do not run the state-6 handler. The only way
  a move turns is the fourth site: the per-frame update calls
  `0x0215EFC0(obj, obj+0xCC, obj+0xF6)` only while `obj+0xCC != 0`, and
  with `obj+0xF7 != 0` only while a horizontal bit is held. A state change
  resets `obj+0xCC = 0`, `obj+0xF6 = 1`, `obj+0xF7 = 0` (`0x0215A130`–
  `0x0215A140`). The one writer is script command 22 (`0x02157D90` →
  `0x0215A968`), so a move's own script can give it drift and turning.
  (static) Whether any air attack's script uses command 22 is unknown.
  The owner says none turn: "Turning does NOT work during air attacks,
  those fire in whatever direction you were already facing". (owner)

## 4. What the code does not settle

- Which air attacks, if any, carry command 22 (drift and turn inside the
  move). Owner: none turn.
- Whether any path turns a fighter during hitstun or knockback through an
  indirect call (a function pointer, not a direct `bl`).
- What `obj+0xA0` = `0x15`, `0x1E` and `0x22` are.



## 5. Observed facing rule

A fighter in state 6 faces the held direction on every frame it does not
start an attack, a jump or a fast fall; in state 7 on every frame. State 5, the squat, hitstun and
air attacks keep their facing. Air velocity is unchanged by the turn.

## 6. Codex second opinion

Agrees on every data-flow claim: the direction pick, that the accel write
does not depend on the turn, the same-call timing with no delay, the gates
before the call in state 6, the `obj+0xCC`/`0xF6`/`0xF7` defaults and the
command-22 writer, and that `obj+0x1D4` holds a callback chain.

More careful in three places, none a conflict:

- It grades "`0x08` = right" medium: the instructions show `0x08` picks the
  positive sign, not that positive x is right. physics.md §6.2 settles the
  sign.
- It grades `vtable[+0x5C]` as the `Q+0x48` setter medium, since the callee
  is not in the excerpt. The earlier finding linked in §1 reads it.
- It says the callees of `0x02083950` could change physics indirectly;
  nothing shown does. Hence "inferred" on the velocity claim above.
