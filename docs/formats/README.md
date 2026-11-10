# Data format references

This directory describes binary layouts used by the original game. A verified offset or
record size establishes where data lives. A field name describes what the current tools
call that data and remains provisional unless its row cites a tracker item or a current reference
under [`../confirmed-facts/`](../confirmed-facts/).

| Reference | Scope |
|---|---|
| [Combat data formats](Combat-Formats.md) | `chr_b.bin`, collision records, `jpower.bin`, sprite archives, and extraction tools |

Use the confirmed-facts documents for original-game behavior. Do not promote an exporter
label into them without evidence from the field's reader or writer.
