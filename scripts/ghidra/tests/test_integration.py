import os,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import GhidraQuery,RESOLVED_OFFSET_ONLY,RANKED_CANDIDATE
@unittest.skipUnless(os.environ.get("JUS_GHIDRA_INTEGRATION")=="1","integration opt-in")
class Live(unittest.TestCase):
 @classmethod
 def setUpClass(c):c.q=GhidraQuery()
 @classmethod
 def tearDownClass(c):c.q.close()
 def test_decompile(self):
  r=self.q.decompile(0x02078488,"arm9");self.assertTrue(r["completed"])
  for t in ("+ 0x18","+ 0x16","< 0","!= 0"):self.assertIn(t,r["c"])
 def test_calls(self):
  rows=self.q.callers(0x020783CC,"arm9")["results"];o=[r for r in rows if r["source"]["overlay"]=="ov6"];self.assertEqual(len(o),14);self.assertIn((0x02150DD8,"thumb"),[(r["source"]["address"],r["mode"]) for r in o])
  a=self.q.callers(0x02078CB8,"arm9")["results"];got=[(r["source"]["overlay"],r["source"]["address"],r["mode"]) for r in a];self.assertIn(("ov5",0x02156C70,"arm"),got);self.assertIn(("ov6",0x021540AA,"thumb"),got)
  c=self.q.callees(0x021540AA,"ov6")["results"];self.assertTrue(any(r["source"]["address"]==0x021540AA and r["target"]=={"overlay":"arm9","address":0x02078CB8} for r in c))
 def test_fields(self):
  def row(off,ov,fn,site):return next((r for r in self.q.find_field_writes(off,overlay=ov,function=fn)["results"] if r["store"]["address"]==site),None)
  self.assertEqual(row(0x18,"arm9",0x02078488,0x020784A0)["category"],RESOLVED_OFFSET_ONLY);self.assertIsNone(row(0x16,"arm9",0x02078488,0x020784A0));self.assertEqual(row(0x4c,"ov6",0x0214FD84,0x0214FDAA)["category"],RANKED_CANDIDATE);self.assertEqual(row(0x44,"arm9",0x02081DDC,0x02081F68)["category"],RESOLVED_OFFSET_ONLY);self.assertIsNone(row(4,"ov5",0x0214E5F0,0x0214E62C))
if __name__=="__main__":unittest.main()
