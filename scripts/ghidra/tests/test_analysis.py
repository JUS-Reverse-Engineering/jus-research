import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import *
from query import output_name
class Pure(unittest.TestCase):
 def test_topology(self):
  s=load_program_specs();self.assertEqual(len(s),13);self.assertEqual(resolve_specs(s,0x02078488)[0].overlay,"arm9")
  with self.assertRaises(AddressResolutionError):resolve_specs(s,0x0214CD20)
  self.assertEqual(resolve_specs(s,0x0214CD20,"ov06")[0].overlay,"ov6")
 def test_names(self):self.assertEqual(normalize_overlay("ov06.bin"),"ov6");self.assertEqual(output_name("xrefs_to","arm9",0x20783cc),"xrefs-to-arm9-020783cc.json")
 def test_classes(self):
  d=[{"op":"INT_ADD","inputs":["r","(const, 0x18, 4)"],"output":"u","address":1,"time":0}];self.assertEqual(classify_store_slice(d,"u",0x18)[0],RESOLVED_OFFSET_ONLY)
  h=[{"op":"COPY","inputs":["(const, 0x23d2a74, 4)"],"output":"base","address":1,"time":0}];self.assertEqual(classify_store_slice(d,"u",0x18,high=h,high_root="base",base_hint=0x23D2A74)[0],PROVEN_BASE)
  x=d+[{"op":"INT_ADD","inputs":["u","i"],"output":"v","address":1,"time":1}];self.assertEqual(classify_store_slice(x,"v",0x18)[0],RANKED_CANDIDATE)
  p=[{"op":"COPY","inputs":["r1"],"output":"old","address":1,"time":0},{"op":"INT_ADD","inputs":["r1","(const, 0x4, 4)"],"output":"r1","address":1,"time":1}];self.assertIsNone(classify_store_slice(p,"old",4)[0])
if __name__=="__main__":unittest.main()
