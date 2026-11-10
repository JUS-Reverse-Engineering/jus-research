Review the evidence packet below. Separate correlation from execution of the
proposed causal decision point. Decide whether the mode-specific explanation is
supported, contradicted, underdetermined, or based on an invalid run. Preserve
valid static and runtime observations if the explanation fails. Return only JSON
matching the supplied schema.

The claim is: "Byte 0x0217296D is the mode-12 discriminator for per-mode handler
installation: it is nonzero in modes that install, zero in mode 12, and its zero
branch prevents mode 12 from installing."

Static code at 0x0214DB24 loads the byte. Instructions at 0x0214DB26 through
0x0214DB2A compare it with zero and branch around an install path when zero. The
fall-through reaches a path that calls installer 0x0214F91C.

At rest, modes 0, 1, and 2 changed the byte from zero to one and installed a
handler with root+0xC8 = 1. Mode 12 left the byte zero, root+0xC8 = 0, and the
default handler in place. Sampling about every 40 frames put the mode-2 byte
transition and install transition in the same frame interval.

One healthy GDB session ran mode 2 first and then loaded mode 12 with the same
breakpoints. In mode 2, the byte-check breakpoint fired 114 times. It read zero
on 113 hits, one on hit 114, and the installer fired immediately afterward. In
mode 12, the byte-check and installer breakpoints each recorded zero hits. The
battle root was populated and recorded mode 12. The session had no error or
detach.

Identify the unsupported step, list what the packet still establishes, and name
the smallest next observation that would resolve the mode-12 cause.
