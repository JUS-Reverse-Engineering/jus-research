import importlib.util, json, struct, tempfile, unittest, zlib
from pathlib import Path
spec = importlib.util.spec_from_file_location("native_validator", Path(__file__).with_name("validate_capture.py"))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
class NativeValidatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.watches = [{"name":"p1input", "addr":0x02100000,"len":4},{"name":"p2input","addr":0x02100004,"len":4},{"name":"p1st","addr":0x02100008,"len":1}]
        (self.root/'watches.tsv').write_text('address\tlength\n34603008\t4\n34603012\t4\n34603016\t1\n')
        (self.root/'audio-options.tsv').write_text('period\tinterpolation\tdegrade_10bit\tapply_bias\n1024\t0\t1\t1\n')
        (self.root/'frames.tsv').write_text('sequence\tnds_frame\tstart_tick\tend_tick\tkey_mask\taudio_offset\taudio_count\tram_hex\theld_left\theld_right\n0\t77\t100\t2148\t4095\t0\t2\t000000000000000000\t0\t0\n1\t78\t2148\t4196\t4095\t2\t2\t000000000000000000\t3\t4\n')
        (self.root/'audio.bin').write_bytes(b''.join(struct.pack('<QIhh',t,1024,i*2+1,i*2+2) for i,t in enumerate([1124,2148,3172,4196])))
        (self.root/'status.json').write_text(json.dumps({'state':'complete','error':'','frames':2,'audio_packets':4}))
        for i in range(2):(self.root/f'{i:06d}.ppm').write_bytes(b'P6\n256 384\n255\n'+bytes(256*384*3))
    def tearDown(self):self.tmp.cleanup()
    def test_valid(self):
        r=v.validate(self.root,2,self.watches,4095)
        self.assertEqual(r['audio_packets'],4)
        self.assertEqual(r['rows'][1]['w']['p1st'],0)
    def test_missing_image(self):
        (self.root/'000001.ppm').unlink()
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_shifted_audio_clock(self):
        (self.root/'audio.bin').write_bytes(b''.join(struct.pack('<QIhh',t,1024,i*2+1,i*2+2) for i,t in enumerate([1124,2148,3173,4196])))
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_wrong_input(self):
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,3967)
    def test_wrong_watch_registration(self):
        (self.root/'watches.tsv').write_text('address\tlength\n34603012\t4\n34603012\t4\n34603016\t1\n')
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_broken_frame_clock(self):
        p=self.root/'frames.tsv';p.write_text(p.read_text().replace('1\t78\t2148','1\t80\t2148'))
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_trailing_audio(self):
        p=self.root/'audio.bin';p.write_bytes(p.read_bytes()+b'\0')
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_lost_initial_audio_state(self):
        p=self.root/'frames.tsv';p.write_text(p.read_text().replace('\t3\t4\n','\t0\t0\n'))
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_missing_first_audio_packet(self):
        p=self.root/'audio.bin';p.write_bytes(p.read_bytes()[16:])
        p=self.root/'frames.tsv';p.write_text(p.read_text().replace('4095\t0\t2','4095\t0\t1').replace('4095\t2\t2','4095\t1\t2'))
        p=self.root/'status.json';s=json.loads(p.read_text());s['audio_packets']=3;p.write_text(json.dumps(s))
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_missing_last_audio_packet(self):
        p=self.root/'audio.bin';p.write_bytes(p.read_bytes()[:-16])
        p=self.root/'frames.tsv';p.write_text(p.read_text().replace('4095\t2\t2','4095\t2\t1'))
        p=self.root/'status.json';s=json.loads(p.read_text());s['audio_packets']=3;p.write_text(json.dumps(s))
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_supported_gaussian_interpolation(self):
        p=self.root/'audio-options.tsv';p.write_text(p.read_text().replace('1024\t0','1024\t4'))
        self.assertEqual(v.validate(self.root,2,self.watches,4095)['audio_options']['interpolation'],4)
    def test_wrong_audio_config(self):
        p=self.root/'audio-options.tsv';p.write_text(p.read_text().replace('1024','704'))
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
SHOTS=[{'name':'shots','address':0x02100000,'offsets':[0],'next':0,'limit':2,
        'fields':[{'name':'life','path':[0x18],'length':2},{'name':'x','path':[0x2C,0x10,0xC],'length':4,'optional':True}]}]
class NativeHooksValidatorTest(unittest.TestCase):
    """calls.tsv / list-frames.tsv / list-nodes.tsv written by NativeHooks.h (rows match test_native_hooks.cpp)."""
    def setUp(self):
        NativeValidatorTest.setUp(self)
        r=self.root
        (r/'hooks.json').write_text('{"version":1,"call_pcs":1,"lists":1}\n')
        (r/'call-pcs.tsv').write_text('pc\n34026668\n')
        (r/'calls.tsv').write_text('sequence\tnds_frame\tpc\tinsn\tr0\tr1\tr2\tr3\tr4\tr5\tr6\tr7\tlr\n'
            '0\t77\t34026668\t3813670913\t1\t2\t3\t4\t5\t6\t7\t8\t15\n'
            '1\t78\t34026668\t3813670913\t0\t2\t3\t4\t5\t6\t7\t8\t15\n')
        (r/'lists.tsv').write_text('list\taddress\toffsets\tnext\tlimit\tfields\n0\t34603008\t0\t0\t2\t24:2:0;44,16,12:4:1\n')
        (r/'list-frames.tsv').write_text('sequence\tnds_frame\tlist\tpresent\tcount\ttruncated\thead_path\n'
            '0\t77\t0\t1\t2\t0\t34603008:35651584,35651584:35651840\n'
            '1\t78\t0\t0\t0\t0\t34603008:0\n')
        (r/'list-nodes.tsv').write_text('sequence\tnds_frame\tlist\tnode\taddress\tnext\tfield_present\tfield_addresses\tdata_hex\n'
            '0\t77\t0\t0\t35651840\t35652096\t11\t35651864,36700172\t170034120000\n'
            '0\t77\t0\t1\t35652096\t0\t10\t35652120,0\tffff00000000\n')
    def tearDown(self):self.tmp.cleanup()
    def run_v(self,calls=(0x020734AC,),lists=SHOTS):return v.validate(self.root,2,self.watches,4095,calls=list(calls),lists=lists)
    def edit(self,name,old,new):
        p=self.root/name;t=p.read_text();self.assertIn(old,t);p.write_text(t.replace(old,new,1))
    def test_valid_decodes_calls_and_nodes(self):
        r=self.run_v()
        self.assertEqual([(c['sequence'],c['pc'],c['r0'],c['r5'],c['r6']) for c in r['calls']],[(0,0x020734AC,1,6,7),(1,0x020734AC,0,6,7)])
        f0,f1=r['lists']['shots']
        self.assertEqual((f0['present'],f0['count'],f0['truncated']),(True,2,False))
        self.assertEqual(f0['nodes'][0],{'address':0x02200100,'next':0x02200200,'life':23,'x':0x1234})
        self.assertEqual(f0['nodes'][1],{'address':0x02200200,'next':0,'life':0xFFFF,'x':None})
        self.assertEqual((f1['present'],f1['nodes']),(False,[]))
    def test_hook_files_without_expectation_reject(self):
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_expectation_without_hook_files_rejects(self):
        (self.root/'hooks.json').unlink()
        with self.assertRaises(ValueError):self.run_v()
    def test_wrong_pc_registration(self):
        with self.assertRaises(ValueError):self.run_v(calls=(0x0206C7FC,))
    def test_call_row_for_unregistered_pc(self):
        self.edit('calls.tsv','1\t78\t34026668','1\t78\t34026672')
        with self.assertRaises(ValueError):self.run_v()
    def test_call_row_misaligned_to_frame(self):
        self.edit('calls.tsv','1\t78\t','1\t79\t')
        with self.assertRaises(ValueError):self.run_v()
    def test_call_rows_out_of_order(self):
        self.edit('calls.tsv','0\t77\t34026668','2\t79\t34026668')
        with self.assertRaises(ValueError):self.run_v()
    def test_list_recipe_mismatch(self):
        bad=[dict(SHOTS[0],limit=3)]
        with self.assertRaises(ValueError):self.run_v(lists=bad)
    def test_missing_list_frame_row(self):
        self.edit('list-frames.tsv','1\t78\t0\t0\t0\t0\t34603008:0\n','')
        with self.assertRaises(ValueError):self.run_v()
    def test_node_count_disagrees(self):
        self.edit('list-frames.tsv','0\t77\t0\t1\t2\t0','0\t77\t0\t1\t1\t0')
        with self.assertRaises(ValueError):self.run_v()
    def test_broken_node_link(self):
        self.edit('list-nodes.tsv','0\t1\t35652096\t0','0\t1\t35652100\t0')
        with self.assertRaises(ValueError):self.run_v()
    def test_head_not_first_node(self):
        self.edit('list-frames.tsv','35651584:35651840','35651584:35651844')
        with self.assertRaises(ValueError):self.run_v()
    def test_absent_field_with_bytes(self):
        self.edit('list-nodes.tsv','ffff00000000','ffff01000000')
        with self.assertRaises(ValueError):self.run_v()
    def test_required_field_absent(self):
        self.edit('list-nodes.tsv','\t10\t35652120,0','\t00\t0,0')
        with self.assertRaises(ValueError):self.run_v()
    def test_truncated_flag_needs_full_walk(self):
        self.edit('list-frames.tsv','0\t77\t0\t1\t2\t0','0\t77\t0\t1\t2\t1')
        self.edit('list-nodes.tsv','\t35652096\t0\t10','\t35652096\t35651840\t10')
        self.assertTrue(self.run_v()['lists']['shots'][0]['truncated'])
        self.edit('list-frames.tsv','0\t77\t0\t1\t2\t1','0\t77\t0\t1\t2\t0')
        with self.assertRaises(ValueError):self.run_v()
def write_gpu(root, nds_frames, oam_versions=None):
    """A NativeGpuMedia.h bundle written independently of the C++ writer.

    oam_versions[seq] is a list of (first_line, last_line, oam_bytes) for engine 0 obj;
    everything else is one span per frame. Sequence 0 obj line 0 is unobserved.
    """
    blobs, index, data = {}, ['blob\tkind\toffset\tlength\tcrc32'], bytearray()
    def blob(kind, b):
        if (kind, b) not in blobs:
            blobs[(kind, b)] = len(blobs)
            index.append(f'{len(blobs)-1}\t{kind}\t{len(data)}\t{len(b)}\t{zlib.crc32(b)}')
            data.extend(b)
        return blobs[(kind, b)]
    pages = {e: [blob('page', bytes([(p + e) % 256]) * 1023 + bytes([e])) for p in range((256, 128)[e])] for e in (0, 1)}
    sets = ['set\tengine\tpages'] + [f'{e}\t{e}\t' + ','.join(map(str, pages[e])) for e in (0, 1)]
    spans = ['sequence\tnds_frame\tengine\tstream\tfirst_line\tlast_line\tobserved\toam\tvram_set\tpal\textpal\tregs_hex']
    frames, post = ['sequence\tnds_frame\tpost_crc32\tpost_regs_hex'], bytearray()
    sreg, creg = '00' * 12, '00' * 36
    for seq, nds in enumerate(nds_frames):
        for e in (0, 1):
            default = [(0, 191, bytes([e + 1]) * 1024)]
            versions = (oam_versions or {}).get(seq, default) if e == 0 else default
            for k, (first, last, oam) in enumerate(versions):
                if seq == 0 and k == 0 and first == 0:
                    spans.append(f'0\t{nds}\t{e}\tobj\t0\t0\t0\t-\t-\t-\t-\t-')
                    first = 1
                spans.append(f'{seq}\t{nds}\t{e}\tobj\t{first}\t{last}\t1\t{blob("oam", oam)}\t{e}\t-\t-\t{sreg}')
            spans.append(f'{seq}\t{nds}\t{e}\tcompose\t0\t191\t1\t-\t-\t{blob("pal", bytes([7 + e]) * 512)}\t{blob("extpal", bytes(8192))}\t{creg}')
        record = bytes([seq + 1]) * 1024 + bytes([seq + 2]) * 1024 + bytes(2048)
        post.extend(record)
        frames.append(f'{seq}\t{nds}\t{zlib.crc32(record)}\t' + '00' * 18)
    (root / 'gpu-media.json').write_text(json.dumps({'version': 1, 'frames': len(nds_frames), 'page_bytes': 1024,
        'vram_pages': [256, 128], 'sprite_reg_bytes': 12, 'compose_reg_bytes': 36, 'post_reg_bytes': 18}))
    (root / 'gpu-blobs.bin').write_bytes(bytes(data))
    for name, lines in (('gpu-blobs.tsv', index), ('gpu-vram-sets.tsv', sets), ('gpu-spans.tsv', spans), ('gpu-frames.tsv', frames)):
        (root / name).write_text('\n'.join(lines) + '\n')
    (root / 'gpu-post.bin').write_bytes(bytes(post))
class NativeGpuValidatorTest(unittest.TestCase):
    """gpu-*.tsv/bin written by NativeGpuMedia.h (scenarios mirror test_native_capture.cpp)."""
    def setUp(self):
        NativeValidatorTest.setUp(self)
        write_gpu(self.root, [77, 78])
    def tearDown(self):self.tmp.cleanup()
    def run_v(self):return v.validate(self.root,2,self.watches,4095,gpu=True)['gpu']
    def edit(self,name,old,new):
        p=self.root/name;t=p.read_text();self.assertIn(old,t);p.write_text(t.replace(old,new,1))
    def rows(self,name='gpu-spans.tsv'):return (self.root/name).read_text().splitlines()
    def put(self,rows,name='gpu-spans.tsv'):(self.root/name).write_text('\n'.join(rows)+'\n')
    def bad(self):
        with self.assertRaises(ValueError):self.run_v()
    def test_valid_round_trip(self):
        g=self.run_v()
        f0,f1=g['frames']
        self.assertEqual(f1['post_oam'],(bytes([2])*1024,bytes([3])*1024))
        self.assertEqual([s['observed'] for s in f0['spans'][(0,'obj')]],[False,True])
        self.assertEqual(g['blobs'][f1['spans'][(1,'obj')][0]['oam']],bytes([2])*1024)
        self.assertEqual(v.gpu_vram(g,f1['spans'][(0,'obj')][0]['vram_set'])[5*1024],5)
        self.assertEqual(len(v.gpu_vram(g,1)),128*1024)
        phase=v.gpu_phase(g)
        self.assertEqual([(r['sequence'],r['engine'],r['line0_eq_prev_post']) for r in phase],
                         [(0,0,None),(0,1,None),(1,0,True),(1,1,True)])
        self.assertEqual([r['eq_post'] for r in phase],[None,None,False,False])
    def test_scanline_versions(self):
        write_gpu(self.root,[77,78],{1:[(0,99,bytes([1])*1024),(100,191,bytes([9])*1024)]})
        g=self.run_v()
        self.assertEqual([(s['first'],s['last']) for s in g['frames'][1]['spans'][(0,'obj')]],[(0,99),(100,191)])
        self.assertEqual(v.gpu_phase(g)[2]['oam_versions'],2)
    def test_consumed_post_frame_mismatch(self):
        write_gpu(self.root,[77,78],{1:[(0,191,bytes([9])*1024)]})
        g=self.run_v();row=v.gpu_phase(g)[2]
        self.assertEqual((row['line0_eq_prev_post'],row['eq_post']),(False,False))
        self.assertEqual(g['frames'][0]['post_oam'][0],bytes([1])*1024)
    def test_gpu_files_without_expectation_reject(self):
        with self.assertRaises(ValueError):v.validate(self.root,2,self.watches,4095)
    def test_expectation_without_gpu_files_rejects(self):
        (self.root/'gpu-media.json').unlink();self.bad()
    def test_corrupted_blob_byte(self):
        p=self.root/'gpu-blobs.bin';b=bytearray(p.read_bytes());b[5000]^=1;p.write_bytes(bytes(b));self.bad()
    def test_truncated_blob_file(self):
        p=self.root/'gpu-blobs.bin';p.write_bytes(p.read_bytes()[:-1]);self.bad()
    def test_extra_blob_bytes(self):
        p=self.root/'gpu-blobs.bin';p.write_bytes(p.read_bytes()+b'\0');self.bad()
    def test_torn_post_frame_record(self):
        p=self.root/'gpu-post.bin';b=bytearray(p.read_bytes());b[4096+100]^=0x80;p.write_bytes(bytes(b));self.bad()
    def test_missing_post_frame_record(self):
        p=self.root/'gpu-post.bin';p.write_bytes(p.read_bytes()[:4096]);self.bad()
    def test_missing_middle_scanline(self):
        write_gpu(self.root,[77,78],{1:[(0,99,bytes([1])*1024),(100,191,bytes([9])*1024)]})
        self.edit('gpu-spans.tsv','1\t78\t0\tobj\t0\t99','1\t78\t0\tobj\t0\t98');self.bad()
    def test_dropped_compose_stream(self):
        self.put([r for r in self.rows() if not r.startswith('1\t78\t1\tcompose')]);self.bad()
    def test_unobserved_line_after_start(self):
        rows=self.rows();i=next(k for k,r in enumerate(rows) if r.startswith('1\t78\t0\tobj\t0\t191'))
        rows[i:i+1]=['1\t78\t0\tobj\t0\t0\t0\t-\t-\t-\t-\t-',rows[i].replace('\t0\t191\t','\t1\t191\t')]
        self.put(rows);self.bad()
    def test_unmerged_identical_spans(self):
        write_gpu(self.root,[77,78],{1:[(0,99,bytes([1])*1024),(100,191,bytes([1])*1024)]});self.bad()
    def test_span_references_wrong_kind(self):
        rows=self.rows();i=next(k for k,r in enumerate(rows) if r.startswith('1\t78\t0\tobj'))
        cols=rows[i].split('\t');cols[7]='0';rows[i]='\t'.join(cols)  # blob 0 is a page, not an OAM bank
        self.put(rows);self.bad()
    def test_frame_row_misaligned(self):
        self.edit('gpu-frames.tsv','1\t78\t','1\t79\t');self.bad()
    def test_rows_out_of_order(self):
        rows=self.rows();rows[1],rows[3]=rows[3],rows[1];self.put(rows);self.bad()
    def test_vram_set_wrong_page_count(self):
        self.edit('gpu-vram-sets.tsv','1\t1\t','1\t1\t0,');self.bad()
    def test_duplicate_blob(self):
        rows=self.rows('gpu-blobs.tsv');data=(self.root/'gpu-blobs.bin').read_bytes()
        n=len(rows)-1;rows.append(f'{n}\tpage\t{len(data)}\t1024\t{zlib.crc32(data[:1024])}')
        self.put(rows,'gpu-blobs.tsv');(self.root/'gpu-blobs.bin').write_bytes(data+data[:1024]);self.bad()
if __name__=='__main__':unittest.main()
