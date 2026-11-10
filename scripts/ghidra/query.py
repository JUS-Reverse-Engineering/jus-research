#!/usr/bin/env python3
"""CLI for the persistent JUS Ghidra project; full results are written as JSON."""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
from analysis import AddressResolutionError,GhidraQuery,ROOT
DEFAULT_OUT=ROOT/"jus_files/analysis/ghidra"
def number(v):return int(v,0)
def output_name(q,o,v):return f"{q.replace('_','-')}-{o or 'all'}-{v:08x}.json"
def parser():
 p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="command",required=True)
 def common(n,h):
  q=sub.add_parser(n,help=h);q.add_argument("value",type=number);q.add_argument("--overlay");q.add_argument("--out-dir",type=Path,default=DEFAULT_OUT);return q
 for n in ("callers","callees","xrefs-to","xrefs-from"):common(n,n)
 q=common("decompile","decompile; prints the C to stdout");q.add_argument("--max-lines",type=int,default=200,help="cap on C lines printed (full C is always in the JSON)")
 q=common("field-writes","P-code field stores");q.add_argument("--base-hint",type=number);q.add_argument("--function",type=number);q.add_argument("--max-results",type=int,default=500)
 return p
def main(argv=None):
 a=parser().parse_args(argv)
 try:
  with GhidraQuery() as g:
   n=a.command.replace("-","_");r=g.find_field_writes(a.value,a.base_hint,overlay=a.overlay,function=a.function,max_results=a.max_results) if n=="field_writes" else getattr(g,n)(a.value,a.overlay)
   env={**g.metadata,"generated_at":datetime.now(timezone.utc).isoformat(),"result":r}
  a.out_dir.mkdir(parents=True,exist_ok=True); pair=r.get("target") or r.get("source") or r.get("scope") or {};o=a.overlay or pair.get("overlay")
  path=a.out_dir/output_name(r["query"],o,a.value);path.write_text(json.dumps(env,indent=2,sort_keys=True)+"\n")
  rows=r.get("results",[]);count=(1 if r["query"]=="decompile" and r.get("completed") else len(rows));print(f"# {count} result(s) for {r['query']} -> {path}")
  for row in rows[:5]:print(json.dumps(row,sort_keys=True))
  if r["query"]=="decompile":print(f"# completed={r['completed']} function={r['function']}")
  if r["query"]=="decompile" and r.get("c"):
   lines=r["c"].strip().splitlines();print("\n".join(lines[:a.max_lines]))
   if len(lines)>a.max_lines:print(f"# truncated: {len(lines)-a.max_lines} more line(s) in {path}")
  return 0
 except (AddressResolutionError,ValueError,RuntimeError) as e:print(f"error: {e}",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
