# PyGhidra query layer

query.py interrogates the analyzed G0 project without re-analysis or saving. It handles Thumb, cross-binary and indirect calls, decompilation, and P-code field-write slices beyond the older static query layer.

Examples: python3 scripts/ghidra/query.py callers 0x020783CC --overlay arm9; python3 scripts/ghidra/query.py field-writes 0x18 --overlay arm9 --function 0x02078488.

Full deterministic JSON outputs default to jus_files/analysis/ghidra/; use --out-dir for scratch output. Each embeds Ghidra 12.1.3, PyGhidra 3.1.0, project identity, and generation time. Stdout has a count and at most five highlights.

Run pure tests with python3 -m unittest scripts/ghidra/tests/test_analysis.py and live tests with JUS_GHIDRA_INTEGRATION=1 python3 -m unittest scripts/ghidra/tests/test_integration.py. Field writes are labeled PROVEN_BASE, RESOLVED_OFFSET_ONLY, or RANKED_CANDIDATE. Low P-code proves the instruction offset; high P-code supplies the attached data-flow slice, excluding post-index pointer updates.
