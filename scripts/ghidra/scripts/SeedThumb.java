// SeedThumb.java
//
// Headless Ghidra postScript: seed the current program's functions from the repo's
// static-analysis database (jus_files/analysis/functions.json).
//
// Why: a raw `BinaryLoader` import with ARM:LE:32:v5t knows nothing about which
// 16-bit regions are Thumb code. Ghidra's auto-analysis guesses at this and gets
// it wrong wherever a Thumb function is entered from an ARM-mode indirect call or
// from an unestablished path (the exact blind spot of the old capstone tools).
// functions.json records a function-start table with an explicit `mode` per start
// (from capstone linear sweep). We use those starts as *seeds*, not gospel:
//   - for a "thumb" start we set the TMode context register to 1 at the entry
//     address BEFORE creating the function, so Ghidra disassembles it as Thumb;
//   - we then create a Function at every seed (arm and thumb).
// Ghidra's own analysis then follows BL/BLX/call edges from these seeded starts
// and propagates correct ARM/Thumb interworking into the bodies -- the capability
// the old tools lack.
//
// MUST run as a postScript on a *-noanalysis* import (or with analysis that has not
// yet disassembled those addresses). If analysis has already turned a Thumb address
// into an ARM instruction, setValue() throws a ContextChangeException ("conflicts
// with one or more instructions") and that function is skipped -- which is why
// import_project.sh runs this as postScript on `-noanalysis` import passes.
//
// Args (getScriptArgs()):
//   [0] provenance filter: arm9 | ov0..ov12 (NULL/absent = seed everything)
//   [1] path to functions.json (required)
//   [2] optional explicit ARM entry address (hex, e.g. arm9 entry 0x02005080).
//       Forced TMode=0 + a Function, so the true entry is never left to the
//       ARM-by-default guess that would also apply to any other missed seed.
//       (Ghidra's default is ARM, so this is mostly belt-and-braces, but it
//       makes the entry explicit in the seeding record.)
//
// Prints SEED_DONE with counts on success, SEED_FAIL on fatal error.

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;
import java.math.BigInteger;
import java.nio.file.*;

public class SeedThumb extends GhidraScript {

    @Override
    public void run() throws Exception {
        String prov = getScriptArgs().length > 0 ? getScriptArgs()[0] : null;
        String jsonPath = getScriptArgs().length > 1 ? getScriptArgs()[1] : null;
        println("SeedThumb prov=" + prov + " json=" + jsonPath);
        if (jsonPath == null) {
            println("SEED_FAIL missing functions.json path arg");
            return;
        }

        String content = new String(Files.readAllBytes(Paths.get(jsonPath)));
        com.google.gson.JsonParser parser = new com.google.gson.JsonParser();
        com.google.gson.JsonObject root = parser.parse(content).getAsJsonObject();
        if (!root.has("functions")) {
            println("SEED_FAIL no 'functions' key in " + jsonPath);
            return;
        }
        com.google.gson.JsonArray arr = root.getAsJsonArray("functions");

        ProgramContext ctx = currentProgram.getProgramContext();
        Register tmode = currentProgram.getLanguage().getRegister("TMode");
        if (tmode == null) {
            println("SEED_WARN no TMode register in language " +
                currentProgram.getLanguage().getLanguageID());
        }
        println("TMode register: " + tmode);

        int created = 0, thumb = 0, skipped = 0, missingTarget = 0, armKept = 0;
        // Explicit ARM entry (arg [2]) forced to TMode=0 + Function.
        if (getScriptArgs().length > 2) {
            String rawEntry = getScriptArgs()[2];
            try {
                long eAddr = Long.decode(rawEntry);
                Address ea = toAddr(eAddr);
                if (currentProgram.getMemory().getBlock(ea) != null) {
                    if (tmode != null) {
                        try {
                            ctx.setValue(tmode, ea, ea, BigInteger.ZERO);
                        } catch (Exception ex) {
                            skipped++;
                            println("SEED_WARN entry TMode=0 conflicted at " + rawEntry);
                        }
                    }
                    if (createFunction(ea, null) != null) {
                        created++;
                        armKept++;
                        println("SEED_ENTRY arm entry " + rawEntry + " seeded (TMode=0)");
                    }
                } else {
                    println("SEED_WARN entry " + rawEntry + " not in this program's memory");
                }
            } catch (Exception ex) {
                println("SEED_WARN bad entry arg " + rawEntry + ": " + ex.getMessage());
            }
        }
        for (com.google.gson.JsonElement e : arr) {
            com.google.gson.JsonObject f = e.getAsJsonObject();
            String p = f.get("provenance").getAsString();
            if (prov != null && !p.equals(prov)) {
                continue;
            }
            long addr;
            String mode;
            try {
                addr = Long.decode(f.get("addr").getAsString());
                mode = f.get("mode").getAsString();
            } catch (Exception ex) {
                skipped++;
                continue;
            }
            Address a = toAddr(addr);
            // Only seed functions that map into a memory block of THIS program. Each
            // program is its own binary, so seeds from another provenance simply don't
            // resolve into our memory; skip rather than creating phantom functions.
            if (currentProgram.getMemory().getBlock(a) == null) {
                missingTarget++;
                continue;
            }
            boolean isThumb = "thumb".equals(mode);
            if (isThumb) {
                try {
                    ctx.setValue(tmode, a, a, BigInteger.ONE);
                    thumb++;
                } catch (Exception ex) {
                    // Context change conflicted with an existing instruction -- the
                    // address was already disassembled as ARM. Keep the count so the
                    // orchestrator can report how many seeds actually took.
                    skipped++;
                    continue;
                }
            }
            try {
                Function fn = createFunction(a, null);
                if (fn != null) {
                    created++;
                    if (!isThumb) armKept++;
                } else {
                    skipped++;
                }
            } catch (Exception ex) {
                skipped++;
            }
        }
        println("SEED_DONE created=" + created + " thumb=" + thumb +
            " skipped=" + skipped + " noTargetInProg=" + missingTarget +
            " prov=" + prov);
    }
}