"""Exact request extraction from full-precision, all-channel host SPU packets.

Packet v2 is <QIIIii16I32i: SPU clock, completed sequence, live GFC, period,
mixer L/R, all CNT words, then each channel's stereo Q8 contribution.
Voice ownership comes from the independently committed ARM7 request receipts.
"""
import bisect
import struct

PACKET=struct.Struct('<QIIIii16I32i')

def read(data):
    if len(data)%PACKET.size:raise ValueError('partial v2 SPU packet')
    return list(PACKET.iter_unpack(data))

def residuals(rows):
    return [[r[0],s,r[4+s]-sum(r[22+s::2])] for r in rows for s in (0,1) if r[4+s]!=sum(r[22+s::2])]

def starts(r):
    offset=r['address']&15;w=r['width'];v=r['value']
    return (offset==3 and w==1 and v&128) or (offset==2 and w==2 and v&32768) or (offset==0 and w==4 and v&0x80000000)

def bind_voices(rows,regs,expected,first_gfc):
    clocks=[r[0] for r in rows];events=[r for r in regs if starts(r)];voices=[]
    for number,e in enumerate(expected):
        candidates=[r for r in events if r['channel']==e['ch'] and r['registers']['SAD']==e['sad'] and rows[bisect.bisect_left(clocks,r['clock'])][2]-first_gfc==e['start']]
        if len(candidates)!=1:raise ValueError(('voice start not unique',number,e,len(candidates)))
        start=candidates[0];ch=e['ch'];first=bisect.bisect_left(clocks,start['clock'])
        if not rows[first][6+ch]&0x80000000:raise ValueError('selected start not active at next mixer sample')
        next_start=min([r['clock'] for r in events if r['channel']==ch and r['clock']>start['clock']]+[clocks[-1]+1])
        limit=bisect.bisect_left(clocks,next_start)
        off=next((i for i in range(first,limit) if not rows[i][6+ch]&0x80000000),limit)
        if off==len(rows):raise ValueError('voice end outside capture')
        if off<=first:raise ValueError('empty voice')
        changed=[r for r in regs if r['channel']==ch and start['clock']<=r['clock']<=clocks[off-1] and r['registers']['SAD']!=e['sad']]
        if changed:raise ValueError('source changed during isolated voice')
        voices.append(dict(number=number,channel=ch,first=first,stop=off,start_write=start,expected=e))
    for a in voices:
        for b in voices:
            if a['number']<b['number'] and a['channel']==b['channel'] and max(a['first'],b['first'])<min(a['stop'],b['stop']):raise ValueError('request voices overlap on one hardware channel')
    return voices

def contribution(row,ch):return row[22+2*ch:24+2*ch]

def quantize(pairs):
    return b''.join(struct.pack('<hh',*[max(-32768,min(32767,x>>8)) for x in pair]) for pair in pairs)

def request_inputs(rows,voices):
    sums=[[0,0] for r in rows]
    for v in voices:
        for i in range(v['first'],v['stop']):
            c=contribution(rows[i],v['channel']);sums[i][0]+=c[0];sums[i][1]+=c[1]
    return sums

def render(rows,voices):return quantize(request_inputs(rows,voices))

def volume_writes(rows,regs,v):
    clocks=[r[0] for r in rows];lo=rows[v['first']][0];hi=rows[v['stop']-1][0]
    return [(bisect.bisect_left(clocks,r['clock'])-v['first'],r['value']) for r in regs if r['channel']==v['channel'] and r['address']&15==0 and r['width']==2 and lo<=r['clock']<=hi]

def jitter(left,right,lwrites,rwrites):
    if [v for i,v in lwrites]!=[v for i,v in rwrites]:raise ValueError('volume write sequences differ')
    windows=[(min(a[0],b[0]),max(a[0],b[0]),a[1]) for a,b in zip(lwrites,rwrites) if a[0]!=b[0]]
    different=[];unexplained=[]
    for i in range(max(len(left),len(right))):
        a=tuple(left[i]) if i<len(left) else (0,0);b=tuple(right[i]) if i<len(right) else (0,0)
        if a!=b:
            different.append(i)
            if not any(lo<=i<hi for lo,hi,value in windows):unexplained.append(i)
    return dict(different_frames=different,unexplained=unexplained,brackets=windows,left_frames=len(left),right_frames=len(right),comparison_origin='each voice first active mixer sample; zero padding only beyond an observed stop')
