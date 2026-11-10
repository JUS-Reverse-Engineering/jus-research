// SmokeTest.java
//
// Headless Ghidra postScript: the scripted smoke tests for a built project.
// NOT eyeballed -- every check prints a machine-grepable SMOKE_<NAME>_OK/FAIL
// line and the orchestrator (import_project.sh) fails the build if any FAIL
// marker or the timeout marker appears in the log.
//
// Modes (first arg):
//   decompile <addr>
//       Decompile the function containing <addr>, print the C, and check the
//       ApplyDeltaToCurrent clamp semantics: a signed halfword read at +0x18,
//       an add, a clamp to [0, max loaded from +0x16], a store back to +0x18,
//       and a boolean return. (Anchor: arm9 0x02078488.)
//   thumb <site> <target>
//       Verify the instruction at <site> is Thumb (TMode context = 1) and its
//       flow target equals <target>. (Anchor: ov6 0x02150DD8 -> 0x020783CC,
//       ground truth lr=0x02150DDD from live GDB.)
//   armbl <site> <target>
//       Verify the instruction at <site> is ARM-mode (TMode = 0) BL/BL and its
//       flow target equals <target>. (Anchor: ov5 0x02156C70 -> 0x02078CB8,
//       hand-confirmed ARM BL encoding.)
//   timeout
//       Report analysisTimeoutOccurred() as SMOKE_TIMEOUT_OK (no timeout) or
//       SMOKE_TIMEOUT_FAIL (analysis did not complete -- do not ship).
//   range <lo> <hi> <expectHex>
//       Assert that memory in [lo,hi) of THIS program equals fixed hex. Used to
//       prove two same-address overlays (ov5/ov6, both base 0x0214CD20) each
//       hold THEIR OWN bytes despite the shared RAM address -- the byte just
//       past ov5's end must differ from ov6 at that spot. (expectHex is the
//       exact byte string expected at the given range, so a wrong binary is a
//       FAIL, not a guess.)
//
// Every mode also prints SMOKE_ANALYSIS_TIMEOUT if analysisTimeoutOccurred()
// returned true, because a half-analyzed program invalidates every other check.

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.app.util.headless.HeadlessScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;

public class SmokeTest extends HeadlessScript {

    // Real clamped-add semantic check (the important decompile assertion). Each
    // regex is whitespace/naming tolerant; \s covers newlines so the compiler's
    // multi-line expression shape can't defeat it (no DOTALL needed since \s
    // includes \n). param_[0-9]+ accepts any decompiler variable name.
    // Add:  cur = *(short*)(p+0x18) + delta   (both assignment and additive form)
    private static final java.util.regex.Pattern ADD_P =
        java.util.regex.Pattern.compile(
            "param_[0-9]+\\s*=\\s*param_[0-9]+\\s*\\+\\s*\\*\\(short \\*\\)\\(param_[0-9]+\\s*\\+\\s*0x18\\)"
          + "|\\+\\s*\\*\\(short \\*\\)\\(param_[0-9]+\\s*\\+\\s*0x18\\)");
    // Store back:  *(short*)(p+0x18) = (short)cur
    private static final java.util.regex.Pattern STOREBACK_P =
        java.util.regex.Pattern.compile(
            "\\*\\(short \\*\\)\\(param_[0-9]+\\s*\\+\\s*0x18\\)\\s*=\\s*\\(short\\)\\s*param_[0-9]+");
    // Clamp low:  if (cur < 0) { cur = 0; }
    private static final java.util.regex.Pattern CLAMPLOW_P =
        java.util.regex.Pattern.compile(
            "if\\s*\\(param_[0-9]+\\s*<\\s*0\\)\\s*\\{\\s*param_[0-9]+\\s*=\\s*0;\\s*\\}");
    // Clamp high:  if (max(+0x16) < cur) { cur = (int)*(short*)(p+0x16); }
    private static final java.util.regex.Pattern CLAMPHIGH_P =
        java.util.regex.Pattern.compile(
            "if\\s*\\(\\*\\(short \\*\\)\\(param_[0-9]+\\s*\\+\\s*0x16\\)\\s*<\\s*param_[0-9]+\\)\\s*\\{\\s*"
          + "param_[0-9]+\\s*=\\s*\\(int\\)\\*\\(short \\*\\)\\(param_[0-9]+\\s*\\+\\s*0x16\\);\\s*\\}");
    // Boolean return:  return *(short*)(p+0x18) != 0;
    private static final java.util.regex.Pattern BOOLRET_P =
        java.util.regex.Pattern.compile(
            "return\\s*\\*\\(short \\*\\)\\(param_[0-9]+\\s*\\+\\s*0x18\\)\\s*!=\\s*0;");

    private static final class DecompSub {
        boolean add;
        boolean storeBack;
        boolean clampLow;
        boolean clampHigh;
        boolean boolRet;
        boolean all() { return add && storeBack && clampLow && clampHigh && boolRet; }
    }

    private DecompSub evalDecomp(String c) {
        DecompSub s = new DecompSub();
        s.add       = ADD_P.matcher(c).find();
        s.storeBack = STOREBACK_P.matcher(c).find();
        s.clampLow  = CLAMPLOW_P.matcher(c).find();
        s.clampHigh = CLAMPHIGH_P.matcher(c).find();
        s.boolRet   = BOOLRET_P.matcher(c).find();
        return s;
    }

    private void printDecompSub(DecompSub s) {
        println("SMOKE_DECOMPILE_SUB add=" + s.add +
            " clampLow=" + s.clampLow + " clampHigh=" + s.clampHigh +
            " storeBack=" + s.storeBack + " boolRet=" + s.boolRet);
    }

    // Spec G0 Step 4a: on failure walk the checklist in order - bytes at address,
    // base mapping, instruction mode, function boundary, analyzer completion - not
    // just "base address wrong". The FUNC= line is already printed before decompile.
    private void printDecompChecklist() {
        println("CHECKLIST: (1) bytes at 0x02078488 - dump `arm9.bin` bytes at offset 0x78488 via xxd and compare against the disasm DB (query.py disasm 0x02078488 20)");
        println("CHECKLIST: (2) base mapping - program memory block base must be 0x02000000 (arm9), not 0x0 (a decompile of address 0x20-hex suggests wrong base)");
        println("CHECKLIST: (3) instruction mode - TMode at 0x02078488 must be 0 (ARM); Thumb decode of ARM bytes yields nonsense C");
        println("CHECKLIST: (4) function boundary - a function must START at 0x02078488 (FUNC= line above shows the containing function; if entry != 0x02078488 the seed/analysis created the boundary wrong)");
        println("CHECKLIST: (5) analyzer completion - SMOKE_ANALYSIS_TIMEOUT line above must be false (a half-analyzed program decompiles garbage)");
    }

    private boolean checkTimeout() {
        boolean t = analysisTimeoutOccurred();
        println("SMOKE_ANALYSIS_TIMEOUT=" + t);
        return t;
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length < 1) {
            println("SMOKE_FAIL no mode arg (decompile|thumb|armbl|timeout)");
            return;
        }
        String mode = getScriptArgs()[0];
        boolean timedOut = checkTimeout();

        if ("decompile".equals(mode)) {
            runDecompile(timedOut);
        } else if ("thumb".equals(mode)) {
            runModeCheck(timedOut, true);
        } else if ("armbl".equals(mode)) {
            runModeCheck(timedOut, false);
        } else if ("selftest-bad".equals(mode)) {
            runSelfTestBad(timedOut);
        } else if ("timeout".equals(mode)) {
            if (timedOut) {
                println("SMOKE_TIMEOUT_FAIL analysis did not complete");
            } else {
                println("SMOKE_TIMEOUT_OK analysis completed");
            }
        } else if ("range".equals(mode)) {
            runRangeCheck(timedOut);
        } else {
            println("SMOKE_FAIL unknown mode " + mode);
        }
    }

    // same-address distinct-bytes test: assert raw memory equality against an
    // expected hex prefix. Because ov5 and ov6 both load at 0x0214CD20, their
    // own bins must be distinguishable -- we check the byte just past ov5's end
    // (0x0214CD20 + ov5_len) which sits inside ov6.
    private void runRangeCheck(boolean timedOut) throws Exception {
        if (getScriptArgs().length < 4) {
            println("SMOKE_RANGE_FAIL need lo hi expectHex args");
            return;
        }
        long lo = Long.decode(getScriptArgs()[1]);
        long hi = Long.decode(getScriptArgs()[2]);
        String expectHex = getScriptArgs()[3].toLowerCase();
        Address loA = toAddr(lo);
        Address hiA = toAddr(hi);
        MemoryBlock b = currentProgram.getMemory().getBlock(loA);
        if (b == null) {
            println("SMOKE_RANGE_FAIL no memory block at " + getScriptArgs()[1]);
            return;
        }
        try {
            byte[] data = new byte[(int)(hi - lo)];
            currentProgram.getMemory().getBytes(loA, data);
            StringBuilder sb = new StringBuilder();
            for (byte by : data) sb.append(String.format("%02x", by & 0xff));
            String gotHex = sb.toString();
            boolean ok = gotHex.equals(expectHex);
            println("SMOKE_RANGE_" + (ok ? "OK" : "FAIL") +
                " lo=" + getScriptArgs()[1] + " hi=" + getScriptArgs()[2] +
                " got=" + gotHex + " expect=" + expectHex +
                " len=" + data.length);
            if (timedOut) {
                println("SMOKE_RANGE_FAIL_CASCADE analysis timed out");
            }
        } catch (Exception ex) {
            println("SMOKE_RANGE_FAIL read error: " + ex.getMessage());
        }
    }

    private void runDecompile(boolean timedOut) throws Exception {
        if (getScriptArgs().length < 2) {
            println("SMOKE_DECOMPILE_FAIL no addr arg");
            return;
        }
        long target = Long.decode(getScriptArgs()[1]);
        Address a = toAddr(target);
        Function f = getFunctionContaining(a);
        if (f == null) {
            println("SMOKE_DECOMPILE_FAIL no function containing " + getScriptArgs()[1]);
            return;
        }
        println("FUNC=" + f.getName() + " entry=" + f.getEntryPoint());
        DecompInterface di = new DecompInterface();
        try {
            di.toggleCCode(true);
            di.toggleSyntaxTree(true);
            di.setSimplificationStyle("decompile");
            if (!di.openProgram(currentProgram)) {
                println("SMOKE_DECOMPILE_FAIL decompiler openProgram failed");
                return;
            }
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            if (res == null || !res.decompileCompleted()) {
                println("SMOKE_DECOMPILE_FAIL decompile incomplete: " +
                    (res == null ? "null" : res.getErrorMessage()));
                return;
            }
            String c = res.getDecompiledFunction().getC();
            println("=== DECOMPILE BEGIN ===");
            println(c);
            println("=== DECOMPILE END ===");

            // ApplyDeltaToCurrent semantics (Battle-Engine-Map.md), verified against
            // the C structurally - NOT by substring (a wrong function that merely
            // mentions 0x18/0x16 with a "< 0" and any return must not pass):
            //   1. add:        cur = *(short*)(p+0x18) + delta, then stored back
            //   2. clamp low:  if (cur < 0) cur = 0;
            //   3. clamp high: if (cur > *(short*)(p+0x16)) cur = *(short*)(p+0x16);
            //   4. store back: *(short*)(p+0x18) = cur;
            //   5. bool ret:   return *(short*)(p+0x18) != 0;
            DecompSub s = evalDecomp(c);
            printDecompSub(s);
            boolean ok = s.all();
            println("SMOKE_DECOMPILE_" + (ok ? "OK" : "FAIL"));
            if (!ok) {
                printDecompChecklist();
            }
            if (timedOut) {
                println("SMOKE_DECOMPILE_FAIL_CASCADE analysis timed out");
            }
        } finally {
            // Ghidra's documented contract: a DecompInterface must be disposed when
            // done. Harmless today (the process exits after one decompile) but wrong
            // not to -- dispose on every path, including the early returns above.
            di.dispose();
        }
    }

    // Ad-hoc negative self-test: run the SAME sub-check functions against a
    // hardcoded WRONG C snippet (the anchor C with the addition removed) and
    // print the SUB markers + checklist, expecting FAIL. Used manually to prove
    // the real semantic check rejects a wrong function: one that merely mentions
    // 0x18/0x16, clamps at 0, and returns must NOT pass. Not wired into
    // import_project.sh - validation only.
    //
    // Marker semantics (deliberately NOT the real SMOKE_DECOMPILE_OK/FAIL -- a
    // negative test must never emit the real anchor's markers, or an accidental
    // invocation would read as the real decompile passing):
    //   SELFTEST_BAD_PASS  the wrong C correctly FAILED the semantic check
    //                      (ok=false -> the negative test passed)
    //   SELFTEST_BAD_FAIL  the wrong C incorrectly PASSED the semantic check
    //                      (ok=true -> the negative test FAILED)
    private void runSelfTestBad(boolean timedOut) throws Exception {
        String wrongC =
            "bool FUN_02078488(int param_1,int param_2)\n" +
            "{\n" +
            "  param_2 = param_2;\n" +                       // addition removed
            "  if (param_2 < 0) {\n" +
            "    param_2 = 0;\n" +
            "  }\n" +
            "  if (*(short *)(param_1 + 0x16) < param_2) {\n" +
            "    param_2 = (int)*(short *)(param_1 + 0x16);\n" +
            "  }\n" +
            "  *(short *)(param_1 + 0x18) = (short)param_2;\n" +
            "  return *(short *)(param_1 + 0x18) != 0;\n" +
            "}\n";
        println("=== SELFTEST-BAD BEGIN (anchor C with the addition removed) ===");
        println(wrongC);
        println("=== SELFTEST-BAD END ===");
        DecompSub s = evalDecomp(wrongC);
        printDecompSub(s);
        boolean ok = s.all();
        println("SELFTEST_BAD_" + (ok ? "FAIL" : "PASS") + " selftest-bad");
        if (!ok) {
            printDecompChecklist();
        }
        if (timedOut) {
            println("SMOKE_DECOMPILE_FAIL_CASCADE analysis timed out");
        }
    }

    private void runModeCheck(boolean timedOut, boolean wantThumb) throws Exception {
        if (getScriptArgs().length < 3) {
            println("SMOKE_FAIL need site and target args");
            return;
        }
        long site = Long.decode(getScriptArgs()[1]);
        long want = Long.decode(getScriptArgs()[2]);
        Listing listing = currentProgram.getListing();
        Instruction ins = listing.getInstructionAt(toAddr(site));
        if (ins == null) {
            println("SMOKE_" + (wantThumb ? "THUMB" : "ARMBL") +
                "_FAIL no instruction at " + getScriptArgs()[1]);
            return;
        }
        Register tmode = currentProgram.getLanguage().getRegister("TMode");
        boolean isThumb = false;
        if (tmode != null) {
            RegisterValue rv = currentProgram.getProgramContext().getRegisterValue(tmode, toAddr(site));
            BigInteger val = rv == null ? null : rv.getUnsignedValueIgnoreMask();
            isThumb = (val != null && val.equals(BigInteger.ONE));
        }
        println("SITE=" + Long.toHexString(site) + " " + ins.getMnemonicString() +
            " " + ins.toString() + " TMode=" + isThumb);
        Address[] flows = ins.getFlows();
        boolean hit = false;
        for (Address f : flows) {
            println("  flow -> " + f);
            if (f.getOffset() == want) hit = true;
        }
        String tag = wantThumb ? "THUMB" : "ARMBL";
        boolean ok = hit && (isThumb == wantThumb);
        println("SMOKE_" + tag + "_" + (ok ? "OK" : "FAIL") +
            " site=" + getScriptArgs()[1] + " target=" + getScriptArgs()[2] +
            " isThumb=" + isThumb + " hit=" + hit);
        if (timedOut) {
            println("SMOKE_" + tag + "_FAIL_CASCADE analysis timed out");
        }
    }
}