import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL=Path(__file__).with_name('view_frames.py')

class ViewFramesTests(unittest.TestCase):
    def run_view(self,unique):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'captures'/'case';folder.mkdir(parents=True)
            rows=[]
            for i in range(9):
                rgb=bytes([i%2,0,0])*(256*384)
                (folder/f'{i:06d}.ppm').write_bytes(b'P6\n256 384\n255\n'+rgb)
                rows.append({'sequence':i,'nds_frame':100+i,'w':{'p1st':0}})
            (folder/'result.json').write_text(json.dumps({'validation':{'rows':rows}}))
            args=[sys.executable,str(TOOL),str(root)]+(['--unique'] if unique else [])
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            path=root/'views'/'inspection.json'
            self.assertTrue(path.exists(),'every opened native frame needs a view mapping')
            data=json.loads(path.read_text())
            self.assertEqual(data['opened_frames'],9)
            self.assertEqual(len(data['frames']),9)
            self.assertEqual(len({x['page'] for x in data['frames']}),1 if unique else 2)
            self.assertEqual(data['unique_images'],2)
            self.assertEqual(data['frames'][0]['image_sha256'],data['frames'][8]['image_sha256'])
            self.assertEqual(data['frames'][0]['page'],data['frames'][8]['page'] if unique else 'case-000.png')

    def test_every_frame_is_opened_and_paginated(self): self.run_view(False)
    def test_exact_pixel_duplicates_share_a_view_with_per_frame_proof(self): self.run_view(True)

if __name__=='__main__':unittest.main()
