"""Scripted movement sweep (tracker item jus-movement-speed-runtime-0luv).

load a pc-* state -> run one fixed input plan on P1 (walk, dash, tapped jump,
held jump with forward drift) -> log the P1 fighter element per frame -> print
the velocity series and fitted constants. Output lands in
docs/research/feel-captures/movement-2026-09-02/.

Live addresses of the pc-* states: P1 element 0x0220C068 (+0xc x s32 8.8,
+0x10 y, +0x24 vx s16, +0x26 vy s16, +0x3c/+0x3d drag k per axis, +0x3e),
victim element 0x0220C0A8. Inputs: A = jump (mv01), B light, Y heavy, X
special (jus-hbmn). P1 starts at x~642 facing the victim on the left; the right
wall is at x 764 (mv00), so walks go RIGHT for <= 25 frames only.

  python3 movement_sweep.py run --state pc-kenshin-npc-luffy-dark-tournament --name mv02-kenshin
  python3 movement_sweep.py summ mv02-kenshin
"""
import json, os, struct, subprocess, sys, time, gzip
import os; REPO=os.environ.get("JUS_REPO", "."); OUT=f"{REPO}/docs/research/feel-captures/movement-2026-09-02"
P1=0x0220C068; V=0x0220C0A8
# one plan for every character so the series line up frame for frame
SEGS=[{"from":0,"to":25,"buttons":["RIGHT"]},                      # walk right, then coast
      {"from":70,"to":71,"buttons":["LEFT"]},{"from":74,"to":94,"buttons":["LEFT"]},   # double-tap dash left, hold 20
      {"from":150,"to":152,"buttons":["A"]},                        # tapped jump
      {"from":230,"to":250,"buttons":["A"]},                        # held jump (20 frames)
      {"from":330,"to":350,"buttons":["A","RIGHT"]},{"from":351,"to":400,"buttons":["RIGHT"]},  # held jump + forward drift
      {"from":470,"to":472,"buttons":["A"]},{"from":476,"to":478,"buttons":["A"]}]   # double jump attempt
TAIL=120
def emu(*a, timeout=400):
    r=subprocess.run(["python3",f"{REPO}/scripts/emu/jusemu.py",*a],capture_output=True,text=True,timeout=timeout)
    if r.returncode: raise SystemExit(f"jusemu {a} failed: {r.stdout[-400:]} {r.stderr[-400:]}")
    return r.stdout
def run(name,state):
    os.makedirs(OUT,exist_ok=True)
    emu("state","load",state); time.sleep(3)
    plan={"name":name,"segments":SEGS,"tail_frames":TAIL,
          "watches":[{"name":"p1","addr":P1,"len":0x40},{"name":"v","addr":V,"len":0x40}]}
    p=f"{OUT}/{name}.plan.json"; json.dump(plan,open(p,"w"),indent=1)
    out=emu("run",p,"--timeout","300"); log=[l for l in out.splitlines() if l.startswith("log:")][0].split()[1]
    rows=[json.loads(l) for l in open(log)]
    with gzip.open(f"{OUT}/{name}.jsonl.gz","wt") as f:
        for r in rows: f.write(json.dumps(r)+"\n")
    json.dump({"state":state,"plan":plan,"addresses":{"p1":hex(P1),"victim":hex(V)},"frames":len(rows)},
              open(f"{OUT}/{name}.meta.json","w"),indent=1)
def s16(b,o): return struct.unpack_from("<h",b,o)[0]
def s32(b,o): return struct.unpack_from("<i",b,o)[0]
def load(name):
    rows=[json.loads(l) for l in gzip.open(f"{OUT}/{name}.jsonl.gz","rt")]
    fr=[]
    for r in rows:
        p=bytes(r["w"]["p1"])
        fr.append(dict(f=r["f"],x=s32(p,0xc)/256,y=s32(p,0x10)/256,vx=s16(p,0x24),vy=s16(p,0x26),kx=p[0x3c],ky=p[0x3d],b3e=p[0x3e]))
    return fr
def fit_g(seg):
    """fit v' = v - (v*ky>>8) + g over airborne frames; return g estimates"""
    gs=[]
    for a,b in zip(seg,seg[1:]):
        if a["vy"]!=0 and b["vy"]!=0:
            gs.append(b["vy"]-(a["vy"]-((a["vy"]*a["ky"])>>8)))
    return gs
def summ(name):
    fr=load(name); f0=fr[0]
    print(f"{name}: kx={f0['kx']} ky={f0['ky']} +0x3e={f0['b3e']} start x={f0['x']:.3f} y={f0['y']:.3f}")
    # walk: frames 0..69
    w=[r for r in fr if r["f"]<70 and r["vx"]!=0]
    if w:
        acc=[b["vx"]-(a["vx"]-((a["vx"]*a["kx"])>>8)) for a,b in zip(w,w[1:]) if b["f"]<=25]
        print(f"  walk R: first vx {w[0]['vx']} at f{w[0]['f']}, max {max(r['vx'] for r in w)}, per-frame add (v'=v-(v*kx>>8)+a): {sorted(set(acc))}")
        coast=[r["vx"] for r in fr if 25<=r["f"]<70]
        print(f"  release: vx after release {coast[:12]}")
    d=[r for r in fr if 70<=r["f"]<150]
    print(f"  dash L: vx series {[r['vx'] for r in d if r['vx']!=0][:40]}")
    print(f"          x {d[0]['x']:.2f} -> {d[-1]['x']:.2f}")
    for lo,hi,lab in ((150,230,"tap jump"),(230,330,"held jump"),(330,470,"held jump+RIGHT"),(470,560,"double jump")):
        seg=[r for r in fr if lo<=r["f"]<hi and r["vy"]!=0]
        if not seg: print(f"  {lab}: no vertical motion"); continue
        ys=[r["y"] for r in seg]; peak=fr[0]["y"]-min(ys)
        print(f"  {lab}: f{seg[0]['f']}-f{seg[-1]['f']} ({len(seg)} frames airborne), vy0 {seg[0]['vy']}, peak {peak:.2f} px, vy at landing {seg[-1]['vy']}")
        print(f"      vy {[r['vy'] for r in seg][:24]}")
        if "RIGHT" in lab: print(f"      vx {[r['vx'] for r in seg][:30]}, x {seg[0]['x']:.2f}->{seg[-1]['x']:.2f}")
        gs=fit_g(seg); print(f"      g fit: {sorted(set(gs))}")
def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=ap.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("run"); s.add_argument("--state",required=True); s.add_argument("--name",required=True)
    m=sub.add_parser("summ"); m.add_argument("name")
    a=ap.parse_args()
    if a.cmd=="run": run(a.name,a.state)
    summ(a.name)
if __name__=="__main__": main()
