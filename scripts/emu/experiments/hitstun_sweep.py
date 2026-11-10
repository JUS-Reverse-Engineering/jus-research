"""Scripted hitstun sweep (tracker item jus-hitstun-types-0nxs).

load a state -> optionally poke the victim's HP -> run a plan (approach +
attack) with per-frame watches on the victim's fighter element, ColPrm
scratch, hit object and HP -> summarise the hit: HP drop frame, knockback
velocity series, frames in the hitstun state byte, and every countdown field
that starts on the hit frame. The real hitstun timer is hit+0x114 (s16 8.8
frames, idles at -1.0 so the zero-start candidate scan below does NOT catch it;
jus-9lp.2.2 closed). Guard flag H+0x7b, guard gauge hit+0x102/+0x104.
Output lands in docs/research/feel-captures/ root; move it into the campaign dir.

Addresses are the live ones of the owner's Dark Tournament states
(pc-kenshin-npc-*, ds8t_jj_battle_darktournament): victim element 0x0220C0A8,
victim scratch H 0x0220F494 (state byte H+0x78: 0x22 ground, 0xC0 hitstun),
victim hit object 0x02230D60. Verify with --check if you use another state.

  python3 hitstun_sweep.py run --state pc-kenshin-npc-luffy-dark-tournament \
      --name hs01-kenB-luffy --approach LEFT:20 --attack B:22-25 [--hp 76]
  python3 hitstun_sweep.py summ hs01-kenB-luffy
"""
import json, os, struct, subprocess, sys, time, gzip
import os; REPO=os.environ.get("JUS_REPO", "."); OUT=f"{REPO}/docs/research/feel-captures"
ELEM=0x0220C0A8; H=0x0220F494; HIT=0x02230D60; P1ELEM=0x0220C068
def emu(*a, timeout=400):
    r=subprocess.run(["python3",f"{REPO}/scripts/emu/jusemu.py",*a],capture_output=True,text=True,timeout=timeout)
    if r.returncode: raise SystemExit(f"jusemu {a} failed: {r.stdout[-400:]} {r.stderr[-400:]}")
    return r.stdout
def peek(addr,n):
    v=json.loads(emu("peek",hex(addr),str(n)))["result"]["value"]
    return bytes(v) if isinstance(v,list) else struct.pack("<I",v)[:n]
def watches(hp_addr):
    return [{"name":"elem","addr":ELEM,"len":0x40},{"name":"p1elem","addr":P1ELEM,"len":0x30},
            {"name":"h60","addr":H+0x60,"len":0x60},{"name":"h130","addr":H+0x130,"len":0x58},
            {"name":"hit","addr":HIT+0x100,"len":0x20},{"name":"hp","addr":hp_addr,"len":2}]
def run(name,state,segs,tail,hp,hp_addr,pokes):
    emu("state","load",state); time.sleep(3)
    if hp is not None:
        raw=hp*64; emu("poke",hex(hp_addr),struct.pack("<H",raw).hex()); time.sleep(0.3)
        got=struct.unpack("<H",peek(hp_addr,2))[0]; assert got==raw,(got,raw)
    for a,b in pokes: emu("poke",hex(a),b.hex()); time.sleep(0.2)
    plan={"name":name,"segments":segs,"tail_frames":tail,"watches":watches(hp_addr)}
    p=f"{OUT}/{name}.plan.json"; json.dump(plan,open(p,"w"),indent=1)
    out=emu("run",p,"--timeout","300"); log=[l for l in out.splitlines() if l.startswith("log:")][0].split()[1]
    rows=[json.loads(l) for l in open(log)]
    with gzip.open(f"{OUT}/{name}.jsonl.gz","wt") as f:
        for r in rows: f.write(json.dumps(r)+"\n")
    json.dump({"state":state,"plan":plan,"hp_poke":hp,"pokes":[[hex(a),b.hex()] for a,b in pokes],
               "addresses":{"elem":hex(ELEM),"H":hex(H),"hit":hex(HIT),"hp":hex(hp_addr)},"frames":len(rows)},
              open(f"{OUT}/{name}.meta.json","w"),indent=1)
    return rows
# HP comes from scratch H+0x17c inside the h130 block; the 2-byte "hp" watch is returned by the bridge as a scalar.
def s16(b,o): return struct.unpack_from("<h",b,o)[0]
def s32(b,o): return struct.unpack_from("<i",b,o)[0]
def summ(name,show=True):
    rows=[json.loads(l) for l in gzip.open(f"{OUT}/{name}.jsonl.gz","rt")]
    fr=[]
    for r in rows:
        w=r["w"]; e=bytes(w["elem"]); h60=bytes(w["h60"]); h130=bytes(w["h130"]); hit=bytes(w["hit"]); p1=bytes(w["p1elem"])
        fr.append(dict(f=r["f"],fc=r["fc"],x=s32(e,0xc)/256,y=s32(e,0x10)/256,vx=s16(e,0x24),vy=s16(e,0x26),
                       st=h60[0x18],hp=struct.unpack_from("<I",h130,0x4c)[0]/64,h60=h60,h130=h130,hit=hit,p1x=s32(p1,0xc)/256))
    drops=[(a["f"],b["hp"],a["hp"]) for b,a in zip(fr,fr[1:]) if a["hp"]!=b["hp"]]
    if not drops:
        if show: print(f"{name}: NO HIT ({len(fr)} frames); P1 x {fr[0]['p1x']:.1f}->{fr[-1]['p1x']:.1f}, victim x {fr[0]['x']:.1f}")
        return None
    hf=drops[0][0]
    stun=[r for r in fr if r["f"]>=hf and r["st"]!=0x22]
    stun_frames=0
    for r in fr:
        if r["f"]>=hf:
            if r["st"]==0x22 and stun_frames>0: break
            if r["st"]!=0x22: stun_frames+=1
    vel=[(r["f"],r["vx"],r["vy"]) for r in fr if hf-1<=r["f"]<hf+40]
    # countdown candidates: bytes/halfwords that are 0 the frame before the hit, nonzero after, and reach 0 later
    cands=[]
    pre=fr[hf-1] if hf>=1 else fr[0]
    for blk,base in (("h60",0x60),("h130",0x130),("hit",0x100)):
        for o in range(0,len(pre[blk])-1,2):
            v0=s16(pre[blk],o); vh=s16(fr[hf][blk],o); vh1=s16(fr[hf+1][blk],o) if hf+1<len(fr) else vh
            if v0==0 and (vh!=0 or vh1!=0):
                series=[s16(r[blk],o) for r in fr[hf:]]
                start=max(series[:2],key=abs)
                zero=next((i for i,v in enumerate(series) if v==0 and i>0),None)
                if zero and all(abs(series[i])>=abs(series[i+1]) for i in range(min(zero,len(series)-1)-1)):
                    cands.append((f"{blk}+{o:#x} (H+{base+o:#x})" if blk!="hit" else f"hit+{base+o:#x}",start,zero))
    res=dict(hit_frame=hf,damage=round(drops[0][1]-drops[0][2],3),drops=drops[:6],state_bytes=[r["st"] for r in fr[hf-1:hf+stun_frames+2]],
             stun_frames=stun_frames,vel=vel,cands=cands,p1x=fr[hf]["p1x"],vx0=fr[hf]["x"])
    if show:
        print(f"{name}: hit f{hf} dmg {res['damage']} | dist {abs(res['p1x']-res['vx0']):.1f}px | state {[hex(s) for s in res['state_bytes'][:6]]}.. non-0x22 for {stun_frames} frames")
        print("  vel (f,vx,vy):", [(f,a,b) for f,a,b in vel[:14]])
        print("  countdown candidates (field, start, frames->0):", cands)
    return res
def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=ap.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("run"); s.add_argument("--state",required=True); s.add_argument("--name",required=True)
    s.add_argument("--approach",default=None,help="BUTTONS:frames, e.g. LEFT:20 (omit for none)")
    s.add_argument("--attack",required=True,help="BUTTONS:from-to, e.g. B:22-25 or UP+X:110-113")
    s.add_argument("--tail",type=int,default=150); s.add_argument("--hp",type=int,default=None)
    s.add_argument("--hp-addr",default="0x021DF7F0"); s.add_argument("--poke",action="append",default=[])
    m=sub.add_parser("summ"); m.add_argument("name")
    a=ap.parse_args()
    if a.cmd=="summ": summ(a.name); return
    segs=[]
    if a.approach: b,n=a.approach.split(":"); segs.append({"from":0,"to":int(n),"buttons":b.split("+")})
    kb,kr=a.attack.split(":"); k0,k1=[int(x) for x in kr.split("-")]; segs.append({"from":k0,"to":k1,"buttons":kb.split("+")})
    pokes=[(int(x.split("=")[0],16),bytes.fromhex(x.split("=")[1])) for x in a.poke]
    run(a.name,a.state,segs,a.tail,a.hp,int(a.hp_addr,16),pokes); summ(a.name)
if __name__=="__main__": main()
