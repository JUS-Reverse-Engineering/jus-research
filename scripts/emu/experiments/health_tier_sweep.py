"""Scripted launch/health sweep (tracker item jus-launch-hp-tiers-u1jw).

load a battle savestate -> optionally poke the victim's HP -> arm capture_feel
against a KNOWN live position block -> run a button plan (approach + attack) ->
stop -> summarise HP drops and the victim's per-frame velocity.

Why it exists: attacker-victim distance moved hand-played launches by ~20%,
more than the gap between health models (feel-captures/m06 notes). A plan run
from a savestate lands the same hit at the same distance every time, so the
only thing that varies between runs is what you poke.

Usage (emulator already launched under your HOLDER, states restored):
  python3 health_tier_sweep.py sweep --state ds8t_jj_battle_darktournament \
      --pos-base 0x220c074 --prefix hx20 --hp 152,120,90,60,30 \
      --approach LEFT:100 --attack UP+X:110-113
  python3 health_tier_sweep.py summ hx20-hp120

Pos-base MUST be the live block: verify it moved across a walk (RAM diff), the
signature candidates in capture_feel.find_pos_array can all be frozen copies.
Never run this while another tail is active (`jusemu tail stop` first).
"""
import json, os, subprocess, struct, sys, time, gzip
import os; REPO=os.environ.get("JUS_REPO", "."); OUT=f"{REPO}/docs/research/feel-captures"
STATE="ds8t_jj_battle_noheal"; POS_BASE="0x220c074"; EXPECT="28,14,36,46"; OPP_HP=0x021DF7F0
# capture_feel watch order: pos, timer, sp1, then p1s0, ops0, p1s1, ops1, ... so ops<slot> = 4 + 2*slot
VICTIM_SLOT=0
EXTRA_POKES=[]  # [(addr, bytes)] applied after state load, before capture
def emu(*a, timeout=120):
    r=subprocess.run(["python3",f"{REPO}/scripts/emu/jusemu.py",*a],capture_output=True,text=True,timeout=timeout)
    if r.returncode: raise SystemExit(f"jusemu {a} failed: {r.stdout[-400:]} {r.stderr[-400:]}")
    return r.stdout
def cf(*a):
    r=subprocess.run(["python3",f"{REPO}/scripts/emu/capture_feel.py",*a],capture_output=True,text=True)
    print(r.stdout[-600:], r.stderr[-600:]); 
    if r.returncode: raise SystemExit("capture_feel failed")
def peek(addr,n):
    return bytes(json.loads(emu("peek",hex(addr),str(n)))["result"]["value"])
def run(match, plan, hp=None):
    emu("state","load",STATE); time.sleep(0.5)
    if hp is not None:
        raw=hp*64; emu("poke",hex(OPP_HP),struct.pack("<H",raw).hex()); time.sleep(0.2)
        got=struct.unpack("<H",peek(OPP_HP,4)[:2])[0]; assert got==raw,(got,raw)
    for addr,b in EXTRA_POKES:
        emu("poke",hex(addr),b.hex()); time.sleep(0.2); assert peek(addr,len(b))[:len(b)]==b, ("poke did not stick",hex(addr))
    cf("start","--match",match,"--expect",EXPECT,"--pos-base",POS_BASE)
    p=f"{OUT}/{match}.plan.json"; json.dump(plan,open(p,"w"),indent=1)
    out=emu("run",p,"--timeout","300",timeout=400)
    cf("stop","--match",match)
    return summarize(match)
def rows(match):
    path=f"{OUT}/{match}.jsonl.gz"; op=gzip.open if path.endswith(".gz") else open
    if not os.path.exists(path): path=path[:-3]; op=open
    for line in op(path,"rt"):
        yield json.loads(line)
def summarize(match, show=True):
    fr=[]
    for r in rows(match):
        v=r["v"]; pos=bytes(v[0]); ops0=bytes(v[4+2*VICTIM_SLOT])
        fr.append((r["fc"], struct.unpack_from("<i",pos,0)[0]/256, struct.unpack_from("<i",pos,4)[0]/256,
                   struct.unpack_from("<i",pos,0x40)[0]/256, struct.unpack_from("<i",pos,0x44)[0]/256,
                   struct.unpack_from("<H",ops0,0)[0]/64))
    if not fr: print("no rows"); return None
    # HP drops and opp velocity
    drops=[(fr[i][0],fr[i-1][5],fr[i][5]) for i in range(1,len(fr)) if fr[i][5]!=fr[i-1][5]]
    vx=[(fr[i][0], fr[i][3]-fr[i-1][3], fr[i][4]-fr[i-1][4]) for i in range(1,len(fr))]
    peak=max(vx,key=lambda t:abs(t[1])) if vx else None
    if show:
        print(f"{match}: {len(fr)} frames fc {fr[0][0]}..{fr[-1][0]}; P1 x {fr[0][1]:.2f}->{fr[-1][1]:.2f}; opp x {fr[0][3]:.2f}->{fr[-1][3]:.2f}")
        print("  HP changes (fc, before, after):", drops[:12], "..." if len(drops)>12 else "")
        print("  peak |opp vx|:", peak)
        if drops:
            last=drops[-1][0]
            print("  opp vx/vy for 8 frames after last drop:", [(f,round(a,3),round(b,3)) for f,a,b in vx if last<=f<last+8])
            # distance at last drop
            d=[abs(t[1]-t[3]) for t in fr if t[0]==last]; print("  |P1-opp| at last drop:", d)
    return fr, drops, vx
def _peek(addr,n):
    v=json.loads(emu("peek",hex(addr),str(n)))["result"]["value"]
    return bytes(v) if isinstance(v,list) else struct.pack("<I",v)
peek=_peek

def launch_after_first_hit(fr,drops,vx,window=60):
    """Peak victim velocity in the frames after the FIRST HP drop (the hit);
    later drops are burn ticks and must not be used as the launch frame."""
    hit=drops[0][0]; win=[(f,a,b) for f,a,b in vx if hit<=f<hit+window]
    return hit, max(win,key=lambda t:abs(t[1]))[1], min(win,key=lambda t:t[2])[2]

def main():
    global STATE,POS_BASE,OPP_HP,EXPECT,VICTIM_SLOT,EXTRA_POKES
    import argparse
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=ap.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("sweep"); s.add_argument("--state",required=True); s.add_argument("--pos-base",required=True)
    s.add_argument("--prefix",required=True); s.add_argument("--hp",required=True,help="comma list; 'full' = no poke")
    s.add_argument("--approach",default="LEFT:100",help="BUTTON:frames"); s.add_argument("--attack",default="UP+X:110-113")
    s.add_argument("--tail",type=int,default=120); s.add_argument("--victim-hp-addr",default=None,help="defaults to opp slot array + 0x50*victim-slot")
    s.add_argument("--victim-slot",type=int,default=0,help="opp slot holding the ACTIVE victim (slot 0 is the deck leader, not necessarily active)")
    s.add_argument("--expect",default=EXPECT,help="player runtime chr_b roster for capture_feel --expect")
    s.add_argument("--approach-none",action="store_true",help="skip the approach segment")
    s.add_argument("--poke",action="append",default=[],help="ADDR=HEXBYTES applied after state load (repeatable), e.g. 0x021DB65C=40000000")
    m=sub.add_parser("summ"); m.add_argument("match"); m.add_argument("--victim-slot",type=int,default=0)
    a=ap.parse_args()
    VICTIM_SLOT=a.victim_slot
    if a.cmd=="summ": summarize(a.match); return
    STATE=a.state; POS_BASE=a.pos_base; EXPECT=a.expect
    EXTRA_POKES=[(int(x.split("=")[0],16),bytes.fromhex(x.split("=")[1])) for x in a.poke]
    OPP_HP=int(a.victim_hp_addr,16) if a.victim_hp_addr else 0x021DF7F0+0x50*a.victim_slot
    ab,af=a.approach.split(":"); kb,kr=a.attack.split(":"); k0,k1=[int(x) for x in kr.split("-")]
    for tok in a.hp.split(","):
        hp=None if tok=="full" else int(tok); name=f"{a.prefix}-hp{tok if hp is None else '%03d'%hp}"
        segs=([] if a.approach_none else [{"from":0,"to":int(af),"buttons":ab.split("+")}])+[{"from":k0,"to":k1,"buttons":kb.split("+")}]
        plan={"name":name,"segments":segs,"tail_frames":a.tail,"watches":[]}
        fr,drops,vx=run(name,plan,hp=hp)
        if drops:
            hit,pvx,pvy=launch_after_first_hit(fr,drops,vx)
            print(f"  -> {name}: hit fc {hit} dmg {drops[0][1]-drops[0][2]:.4f} peak vx {pvx:.4f} ({round(pvx*256)}) peak vy {pvy:.4f} ({round(pvy*256)})")
        else: print(f"  -> {name}: no hit")

if __name__=="__main__":
    main()
