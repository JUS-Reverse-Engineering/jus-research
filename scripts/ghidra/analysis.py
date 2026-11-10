#!/usr/bin/env python3
"""Read-only PyGhidra queries over the persistent one-Program-per-binary project."""
from __future__ import annotations

import json, os, re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = ROOT / "scripts/ghidra/project"
PROJECT_NAME = "JUS"
GHIDRA_DIR = Path(os.environ.get("GHIDRA_INSTALL_DIR", "/opt/homebrew/Cellar/ghidra/12.1.3/libexec"))
GHIDRA_PIN, PYGHIDRA_PIN = "12.1.3", "3.1.0"
PROVEN_BASE, RESOLVED_OFFSET_ONLY, RANKED_CANDIDATE = "PROVEN_BASE", "RESOLVED_OFFSET_ONLY", "RANKED_CANDIDATE"
_CONST = re.compile(r"^\(const, 0x([0-9a-fA-F]+), \d+\)$")
_ADDR = re.compile(r"^\(ram, 0x([0-9a-fA-F]+), \d+\)$")

class AddressResolutionError(ValueError): pass

@dataclass(frozen=True)
class ProgramSpec:
    overlay: str
    stored_name: str
    base: int
    size: int
    def contains(self, addr: int) -> bool: return self.base <= addr < self.base + self.size
    def pair(self, addr: int) -> dict[str, Any]: return {"overlay": self.overlay, "address": addr}

def normalize_overlay(value: str) -> str:
    value = value.strip().lower()
    if value in ("arm9", "arm9.bin"): return "arm9"
    if value.endswith(".bin"): value = value[:-4]
    if value.startswith("ov"): value = value[2:]
    if not value.isdigit(): raise AddressResolutionError(f"invalid overlay {value!r}")
    return f"ov{int(value)}"

def load_program_specs(root: Path = ROOT) -> tuple[ProgramSpec, ...]:
    arm = json.loads((root/"jus_files/arm9/binaries.json").read_text())["binaries"]["arm9"]
    ovs = json.loads((root/"jus_files/overlays/overlays.json").read_text())
    out = [ProgramSpec("arm9", arm["file"], int(arm["ram_address"]), int(arm["size"]))]
    out += [ProgramSpec(f"ov{int(o['id'])}", o["file"], int(o["ram_address"]), int(o["ram_size"])) for o in ovs if int(o["ram_size"]) >= 1000]
    return tuple(out)

def resolve_specs(specs: Sequence[ProgramSpec], addr: int, overlay: str|None=None) -> tuple[ProgramSpec, ...]:
    found = tuple(s for s in specs if s.contains(addr))
    if overlay:
        key = normalize_overlay(overlay); found = tuple(s for s in found if s.overlay == key)
    if not found: raise AddressResolutionError(f"0x{addr:08X} is not mapped by {overlay or 'any Program'}")
    if len(found) > 1: raise AddressResolutionError(f"0x{addr:08X} is ambiguous across {', '.join(s.overlay for s in found)}; pass overlay")
    return found

def _cv(v: str) -> int|None:
    m = _CONST.match(v); return int(m.group(1),16) if m else None

def _ops_reaching(ops: Sequence[dict[str,Any]], root: str) -> list[dict[str,Any]]:
    defs = {}
    for op in ops:
        if op.get("output"): defs.setdefault(op["output"],[]).append(op)
    todo=[(root,float("inf"))]; seen=set(); out=[]
    while todo and len(out)<80:
        v,bound=todo.pop(); key=(v,bound)
        if key in seen: continue
        seen.add(key); candidates=[o for o in defs.get(v,[]) if o["time"] < bound]
        op=max(candidates,key=lambda o:o["time"]) if candidates else None
        if op: out.append(op); todo.extend((x,op["time"]) for x in reversed(op["inputs"]))
    return out

def classify_store_slice(low: Sequence[dict[str,Any]], root: str, offset: int, *, high: Sequence[dict[str,Any]]=(), high_root: str|None=None, base_hint: int|None=None):
    """Classify only dependencies feeding STORE; sibling writeback ops do not count."""
    reachable=_ops_reaching(low,root); defs={o["output"]:o for o in reachable if o.get("output")}; cur=root
    while defs.get(cur,{}).get("op") in {"COPY","CAST","INT_ZEXT","INT_SEXT","SUBPIECE"}:
        cur=defs[cur]["inputs"][0]
    m=_ADDR.match(cur); absolute=int(m.group(1),16) if m and not cur.startswith("(const,") else _cv(cur)
    if absolute is not None and (base_hint is None or absolute-offset==base_hint):
        return PROVEN_BASE, absolute-offset, f"absolute address proves base + 0x{offset:X}"
    op=defs.get(cur); direct=False
    if op and op["op"] in {"INT_ADD","PTRADD"}:
        vals=[_cv(v) for v in op["inputs"]]
        direct=offset in vals and any(v != offset for v in vals)
    low_all_constants={n for o in low for v in o["inputs"] if (n:=_cv(v)) is not None}
    low_reachable_constants={n for o in reachable for v in o["inputs"] if (n:=_cv(v)) is not None}
    if offset in low_all_constants and offset not in low_reachable_constants:
        return None, None, "offset belongs to a sibling P-code operation, not the STORE address"
    high_reach=_ops_reaching(high,high_root) if high_root else []
    constants={n for o in reachable+high_reach for v in o["inputs"] if (n:=_cv(v)) is not None}
    if direct:
        if base_hint is not None and base_hint in constants:
            return PROVEN_BASE, base_hint, f"direct +0x{offset:X}; slice reaches base hint 0x{base_hint:X}"
        return RESOLVED_OFFSET_ONLY, None, f"direct opaque base + 0x{offset:X}"
    if offset in constants: return RANKED_CANDIDATE, None, f"0x{offset:X} occurs in address slice but is not a fixed field offset"
    return None, None, "offset absent from STORE address slice"

def _ser(op: Any) -> dict[str,Any]:
    seq=op.getSeqnum()
    return {"op":op.getMnemonic(),"inputs":[str(op.getInput(i)) for i in range(op.getNumInputs())],"output":str(op.getOutput()) if op.getOutput() else None,"address":seq.getTarget().getOffset(),"time":seq.getTime()}

class GhidraQuery:
    def __init__(self, project_dir: Path|str=PROJECT_DIR, project_name: str=PROJECT_NAME):
        import pyghidra
        self.specs=load_program_specs(); self.by_overlay={s.overlay:s for s in self.specs}
        if not pyghidra.started(): pyghidra.start(install_dir=GHIDRA_DIR,verbose=False)
        self.pyghidra=pyghidra; self.project=pyghidra.open_project(str(project_dir),project_name)
        self.programs={}; self.decompilers={}; self.closed=False
        from ghidra.framework import Application
        self.metadata={"ghidra_version":str(Application.getApplicationVersion()),"pyghidra_version":pyghidra.__version__,"project_name":project_name,"project_dir":str(Path(project_dir).resolve()),"topology":"one-program-per-binary"}
        if self.metadata["ghidra_version"] != GHIDRA_PIN or self.metadata["pyghidra_version"] != PYGHIDRA_PIN:
            self.close(); raise RuntimeError(f"version mismatch: {self.metadata}")
    def __enter__(self): return self
    def __exit__(self,*_): self.close()
    def close(self):
        if self.closed:return
        for d in self.decompilers.values(): d.dispose()
        for p,c in self.programs.values(): p.release(c)
        self.project.close(); self.closed=True
    def _spec(self,addr,overlay): return resolve_specs(self.specs,addr,overlay)[0]
    def _program(self,overlay):
        key=normalize_overlay(overlay)
        if key not in self.programs:
            s=self.by_overlay[key]; self.programs[key]=self.pyghidra.consume_program(self.project,"/"+s.stored_name)
        return self.programs[key][0]
    @staticmethod
    def _addr(p,a): return p.getAddressFactory().getDefaultAddressSpace().getAddress(a)
    def _fn(self,s,p,f): return {"overlay":s.overlay,"address":f.getEntryPoint().getOffset(),"name":f.getName(),"size":f.getBody().getNumAddresses()}
    def _mode(self,p,a):
        try:
            r=p.getLanguage().getRegister("TMode"); v=p.getProgramContext().getRegisterValue(r,a); n=v.getUnsignedValueIgnoreMask() if v else None
            return None if n is None else ("thumb" if n.longValue()==1 else "arm")
        except Exception:return None
    def _decomp(self,s):
        if s.overlay not in self.decompilers:
            from ghidra.app.decompiler import DecompInterface
            d=DecompInterface(); d.toggleCCode(True); d.toggleSyntaxTree(True)
            if not d.openProgram(self._program(s.overlay)): d.dispose(); raise RuntimeError("decompiler open failed")
            self.decompilers[s.overlay]=d
        return self.decompilers[s.overlay]
    def _candidates(self,a,source=None):
        xs=[s for s in self.specs if s.contains(a)]
        local=[s for s in xs if s.overlay==source]
        return [(s.pair(a)) for s in (local or xs)]
    def decompile(self,addr,overlay=None):
        s=self._spec(addr,overlay); p=self._program(s.overlay); f=p.getFunctionManager().getFunctionContaining(self._addr(p,addr))
        if not f:return {"query":"decompile","target":s.pair(addr),"completed":False,"function":None,"c":None,"error":"no containing function"}
        from ghidra.util.task import ConsoleTaskMonitor
        r=self._decomp(s).decompileFunction(f,60,ConsoleTaskMonitor()); ok=bool(r.decompileCompleted())
        return {"query":"decompile","target":s.pair(addr),"completed":ok,"function":self._fn(s,p,f),"c":r.getDecompiledFunction().getC() if ok else None,"error":None if ok else r.getErrorMessage()}
    def callers(self,addr,overlay=None):
        target=self._spec(addr,overlay); out=[]
        for s in self.specs:
            p=self._program(s.overlay)
            for r in p.getReferenceManager().getReferencesTo(self._addr(p,addr)):
                if "CALL" not in str(r.getReferenceType()):continue
                a=r.getFromAddress(); f=p.getFunctionManager().getFunctionContaining(a)
                out.append({"source":s.pair(a.getOffset()),"target":target.pair(addr),"reference_type":str(r.getReferenceType()),"mode":self._mode(p,a),"function":self._fn(s,p,f) if f else None})
        out.sort(key=lambda x:(x["source"]["overlay"],x["source"]["address"]))
        return {"query":"callers","target":target.pair(addr),"results":out}
    def callees(self,addr,overlay=None):
        s=self._spec(addr,overlay); p=self._program(s.overlay); f=p.getFunctionManager().getFunctionContaining(self._addr(p,addr)); out=[]
        if f:
            it=p.getListing().getInstructions(f.getBody(),True)
            while it.hasNext():
                ins=it.next()
                if not ins.getFlowType().isCall():continue
                refs=[r for r in ins.getReferencesFrom() if "CALL" in str(r.getReferenceType())]
                if not refs: out.append({"source":s.pair(ins.getAddress().getOffset()),"target":None,"target_candidates":[],"kind":"indirect","mnemonic":ins.getMnemonicString()})
                for r in refs:
                    a=r.getToAddress().getOffset(); cs=self._candidates(a,s.overlay)
                    out.append({"source":s.pair(ins.getAddress().getOffset()),"target":cs[0] if len(cs)==1 else None,"target_candidates":cs,"kind":"direct","reference_type":str(r.getReferenceType()),"mnemonic":ins.getMnemonicString()})
        return {"query":"callees","source":s.pair(addr),"function":self._fn(s,p,f) if f else None,"results":out}
    def xrefs_to(self,addr,overlay=None):
        target=self._spec(addr,overlay); out=[]
        for s in self.specs:
            p=self._program(s.overlay)
            for r in p.getReferenceManager().getReferencesTo(self._addr(p,addr)):
                out.append({"source":s.pair(r.getFromAddress().getOffset()),"target":target.pair(addr),"reference_type":str(r.getReferenceType()),"operand_index":r.getOperandIndex()})
        out.sort(key=lambda x:(x["source"]["overlay"],x["source"]["address"]))
        return {"query":"xrefs_to","target":target.pair(addr),"results":out}
    def xrefs_from(self,addr,overlay=None):
        s=self._spec(addr,overlay); p=self._program(s.overlay); out=[]
        for r in p.getReferenceManager().getReferencesFrom(self._addr(p,addr)):
            a=r.getToAddress().getOffset(); cs=self._candidates(a,s.overlay)
            out.append({"source":s.pair(addr),"target":cs[0] if len(cs)==1 else None,"target_candidates":cs,"reference_type":str(r.getReferenceType()),"operand_index":r.getOperandIndex()})
        return {"query":"xrefs_from","source":s.pair(addr),"results":out}
    def _high_stores(self,s,f):
        from ghidra.util.task import ConsoleTaskMonitor
        r=self._decomp(s).decompileFunction(f,60,ConsoleTaskMonitor())
        if not r.decompileCompleted():return {}
        ops=[_ser(o) for o in r.getHighFunction().getPcodeOps()]; out={}
        for o in ops:
            if o["op"]=="STORE":out.setdefault(o["address"],[]).append((o["inputs"][1],ops))
        return out
    def find_field_writes(self,offset,base_hint=None,*,overlay=None,function=None,max_results=500):
        if function is not None: specs=resolve_specs(self.specs,function,overlay)
        elif overlay:
            key=normalize_overlay(overlay)
            if key not in self.by_overlay: raise AddressResolutionError(f"unknown G0 Program {key}")
            specs=(self.by_overlay[key],)
        else: specs=self.specs
        out=[]; truncated=False
        for s in specs:
            p=self._program(s.overlay); fm=p.getFunctionManager()
            fs=(fm.getFunctionContaining(self._addr(p,function)),) if function is not None else fm.getFunctions(True)
            for f in fs:
                if f is None:continue
                high=self._high_stores(s,f); it=p.getListing().getInstructions(f.getBody(),True)
                while it.hasNext():
                    ins=it.next(); low=[_ser(o) for o in ins.getPcode()]
                    for st in (o for o in low if o["op"]=="STORE"):
                        hs=high.get(ins.getAddress().getOffset(),[]); hr,ho=hs[0] if hs else (None,[])
                        cat,base,reason=classify_store_slice(low,st["inputs"][1],offset,high=ho,high_root=hr,base_hint=base_hint)
                        if cat: out.append({"store":s.pair(ins.getAddress().getOffset()),"function":self._fn(s,p,f),"category":cat,"base":base,"reason":reason,"instruction":str(ins),"slice":{"instruction":_ops_reaching(low,st["inputs"][1]),"high":_ops_reaching(ho,hr) if hr else []}})
                        if len(out)>=max_results:truncated=True;break
                    if truncated:break
                if truncated:break
            if truncated:break
        out.sort(key=lambda x:(x["store"]["overlay"],x["store"]["address"]))
        return {"query":"find_field_writes","offset":offset,"base_hint":base_hint,"scope":{"overlay":normalize_overlay(overlay) if overlay else None,"function":function},"truncated":truncated,"results":out}
