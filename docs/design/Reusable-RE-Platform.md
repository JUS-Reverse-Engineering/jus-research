# Future idea: a reusable agent-driven RE platform

> Kind: Deferred design. This page is not a current requirement for this project.

**Status: deferred, deliberately.** Written 2026-08-24, distilled from a design
discussion around [lisptc](https://d4shi.com/blog/lisptc/) ("programmatic tool
calling" — let an AI agent write a small program that orchestrates tools,
instead of making one tool call per model turn). We decided *not* to build this
for this project, because its remaining reverse-engineering questions are
few and specific. This doc captures the design so it can be picked up if a
second RE project ever makes the investment worth it.

## The core idea

An LLM agent doing reverse engineering shouldn't act as a very expensive `for`
loop. The division of labor should be:

- **LLM** decides *what* to investigate and interprets ambiguous evidence.
- **A runtime** executes the mechanical parts: graph traversal, batch
  breakpoints, memory diffs, xref walks — dozens of operations per LLM turn.

This project independently converged on the useful 80% of this without
any new language: JSON button-plans executed whole by a Lua bridge, GDB
auto-triggers that capture state without babysitting, batch GDB scripts
generated up front because the melonDS stub only survives one attach per
emulator launch. The lesson: the batch/programmatic style is justified less by
token savings and more by *environments where conversational tool-by-tool
control is unreliable*.

## The architecture (if generalized)

Three providers, one thin kernel, domain plugins on top. Ghidra, GDB, and the
emulator are three views of the same executable — not three unrelated tools.

```text
                     AI agent
                        │
              ┌─────────┴─────────┐
              │  analysis kernel  │
              │  result store     │
              │  evidence graph   │
              │  plan executor    │
              └─────────┬─────────┘
        ┌───────────────┼───────────────┐
   STATIC provider  RUNTIME provider  EMULATOR provider
     (Ghidra/          (GDB/MI          (Lua bridge,
      PyGhidra)         or DAP)          savestates)
        └───────────────┼───────────────┘
                 DOMAIN plugins
              (NDS addresses/overlays,
               game-specific structs)
```

Key pieces, in rough value order:

1. **A common semantic API per provider.** `static.decompile/callers/xrefs/
   find_field_writes`, `debug.break/watch/snapshot/trace`, `emu.run_plan/
   state/input`. The agent never drives raw Ghidra API calls or raw GDB text.
2. **Canonical addresses.** NDS overlays make "address 0x02204C20" ambiguous.
   Every provider should speak something like `nds://arm9/overlay/17/02204c20`
   so static, runtime, and emulator results can be joined.
3. **Context virtualization.** Big results (2,000 xrefs, an 80 KB snapshot)
   get stored under a handle (`$xrefs_42`) with a summary; the agent asks for
   filtered slices. Never dump raw bulk into model context.
4. **An evidence graph with provenance.** Edges like
   `fn_020491C8 —writes→ Character.pending_damage`, tagged
   `source: ghidra-pcode, confidence: inferred` versus
   `source: gdb-watchpoint, confidence: observed`. Static analysis produces
   hypotheses; runtime produces observations; the graph accumulates both.
   (SQLite is plenty. For a small project, markdown docs with
   HYPOTHESIS/TENTATIVE/CONFIRMED labels do the same job — that's what this
   project uses and it works.)
5. **A constrained plan language.** JSON step-lists are enough and have great
   properties (serializable, inspectable, safe, easy for models to emit and
   validate). A Lisp-style language with macros is theoretically nicer but was
   the least-proven part of the original lisptc pitch. Don't start there.

## The canonical workflow it enables

```text
Question: "who writes Character+0x134?"
    │
    ▼ cheap existing indexes (xref db, immediate-offset scan)
answer? ── yes → document
    │ no
    ▼ Ghidra: decompile / P-code dataflow / find_field_writes
answer? ── yes → document
    │ no — but a small candidate set
    ▼ generate ONE batch GDB script (all probes installed up front)
    ▼ emulator runs a deterministic reproduction plan
    ▼ runtime evidence names the writer
    ▼ confirmed-facts / ticket update
```

Ghidra hypothesizes, GDB observes, the emulator reproduces, the LLM
interprets, the graph remembers.

## What we explicitly deferred, and why

- **Provider/plugin registry, capability metadata** — abstraction for a
  breadth of backends that doesn't exist yet.
- **Generic multi-language support** (Ruby/C#/TS/etc. via LSPs) — belongs to
  a source-code agent platform, not a binary-RE vertical.
- **ARM7 / cross-CPU IPC semantic graphing** — JUS's game logic is all ARM9 +
  overlays; researchy and unneeded.
- **A Lisp interpreter / new plan language** — JSON plans already cover it.
- **A graph database** — the confirmed-facts docs + issue tracker already
  express the epistemic states that matter.

## When to revisit

Pick this back up if any of these become true:

- A **second** binary-RE target appears (another ROM, another platform), so
  the provider abstraction would actually get two implementations.
- The open-question list grows past what ad-hoc scripts + docs can track, and
  provenance queries ("show me everything only inferred, never observed")
  would change decisions.
- Agents are routinely burning context on bulk tool output — that's the
  signal to add result handles + filtering first, since it's the cheapest,
  most independently valuable piece.

The stopping point that was right here: install Ghidra + NTRGhidra, add
a tiny PyGhidra query layer (no registry, just a class with `decompile`,
`callers`, `xrefs`, `find_field_writes`), keep the handwritten indexes as fast
paths, and batch every GDB confirmation into a single generated session.
