# Element flag stores and the W3 LIST phase

Amendment 27 Step 0, read-only investigation, 2026-11-03. No capture, new hook
profile or admission replay was built. W3 remains refused at its two LIST-byte
disagreements. This census identifies a clear writer, but does not establish
global pointer closure or a sufficient hook set for full-byte replay.

## Sources and method

The ARM9 image is
jus_files/arm9/arm9.bin,
SHA256 6464c6e726cd536756476392bf21996ae7289d16e269863cd0b88c1703d09287.
The ARM9 and all 14 extracted overlay images were compared byte for byte with
the private ROM's ARM9 header, overlay table and FAT extents. No source image
was changed. 

full_scan.py enumerates positive-immediate STRB +0x18 encodings in ARM and Thumb
alignment across all 15 images. It finds 65 ARM and 77 Thumb candidates.
Capstone decodes the candidates; the clear instruction and store operands also
have independent bit-field assertions in classify.py. Literal encoding matches
include data and instructions that write other object types. Classification
therefore retains unresolved candidates rather than calling them non-element.

## The bit-2 clear

The collision pass at 0x0207B414 visits an element through r5. Its geo_visit
hook at 0x0207B4C4 samples the flags before the clear. Unless the retirement
branch is taken, these instructions clear bit 2:

| PC | Opcode | Operation |
|---|---|---|
| 0x0207B4E4 | 0xE3C00004 | bic r0, r0, #4 |
| 0x0207B4EC | 0xE5C50018 | strb r0, [r5, #0x18] |

The store precedes geo_end at 0x0207B7EC and the row-end LIST sample S(g).
The dispatcher at 0x0207B3EC calls the collision pass at 0x0207B3FC, the overlap
builder at 0x0207B404, then the pair walk at 0x0207B40C. The pair walk's two
endpoint stores, 0x0207BBC4 and 0x0207BBD4, OR bit 2 after geo_end and before the
integrator I(g). A row boundary can put S(g) between the clear and those stores.

The retained Native visits corroborate the before-clear bytes at gfc 92227,
view row 1528, nds_frame 299101. Element 0x023C03B0 enters with 0x25 and LIST
holds 0x21. Element 0x02392C18 enters with 0xA5 and LIST holds 0xA1. The GDB
integrator sample in the next native row has 0x25 and 0xA5. Those observations
fit clear-then-set, but do not record the pair byte or prove the later branch.
clear-entry-corroboration.json is diagnostic only.

The constructor also clears bit 2 initially. It allocates 0x64 bytes, calls
memset at 0x0207B170, and writes flags=0x20 at 0x0207B194, opcode 0xE5C40018,
before the birth-return hook at 0x0207B1B0. This is an initialization writer,
not the recurring live-element clear.

## Classified writers

The disassembly clips and direct-call encoding census are retained separately.
Only the dispatcher establishes the stated S(g)/I(g) order. Callback phase and
some caller identities remain unverified.

| Store PC | Operation | Caller or phase |
|---|---|---|
| 0x0207B194 | flags = 0x20 | constructor, before birth return |
| 0x0207B2B8 | flags OR 0x10 | count/retirement helper; preserves bit 2 |
| 0x0207B2F0 | flags OR 1 | enable helper; preserves bit 2 |
| 0x0207B2FC | flags AND NOT 1 | disable helper; preserves bit 2 |
| 0x0207B3D8 | set/clear 0x40 | origin-inclusion helper; preserves bit 2 |
| 0x0207B4EC | flags AND NOT 4 | collision visit, before S(g) |
| 0x0207BBC4 | endpoint flags OR 4 | pair walk, before I(g) |
| 0x0207BBD4 | endpoint flags OR 4 | pair walk, before I(g) |
| 0x0207D554 | flags OR 0x80 | setup callback; precise phase unverified |
| 0x0207D568 | flags AND NOT 0x80 | setup callback; precise phase unverified |
| 0x0207E81C | flags OR 2 | participant callback; precise phase unverified |
| 0x0207FDAC | flags OR 2 | participant callback; precise phase unverified |
| 0x02080904 | flags AND NOT 2 | participant callback; precise phase unverified |
| 0x02080968 | flags OR 2 | participant callback; precise phase unverified |
| 0x02080B2C | flags OR 2 | participant callback; precise phase unverified |
| 0x02080B68 | flags OR 2 | participant callback; precise phase unverified |
| 0x02080C18 | flags OR 2 | participant callback; precise phase unverified |
| 0x0208214C | flags OR 2 | participant callback; precise phase unverified |

## Coverage limits and owner request input

Of 142 encoding candidates, 18 are classified element writers, two write stack
bytes, two are fighter-state writes, and 120 have unresolved code mode or object
type. Register-offset stores, aliased pointers and wider writes are not globally
closed. The census is complete for its stated encoding pattern; a claim to have
proved every possible element-byte writer would exceed this evidence.

The confirmed minimum for the owner's proposed profile is 0x0207BBB0,
0x0207BBC4, 0x0207BBD4 and the newly identified 0x0207B4EC clear store.
0x0207B194 must also be considered if replay can include newly born elements.
This list is review input, not an executable profile or a sufficiency claim.
The unresolved candidates and callback phases remain UNVERIFIED. Retained pair
state is still absent, so no LP prediction or admission is made.
