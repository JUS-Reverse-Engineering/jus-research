"""Read the host-side acquisition tap. Contributions retain the mixer's Q8 precision.

The sample packet is <QIIIiiII32i: clock, completed-frame sequence, GFC, period,
raw mixer left/right, channel 10/11 CNT, then 16 stereo contribution pairs.
The current observer reads GFC at each sample; the separately labeled initial
pilot used frame-start GFC. Matrix tick is live GFC minus the receipt first_gfc.
PCM quantizes one channel to stereo signed 16-bit with an arithmetic shift.
"""
import struct

PACKET=struct.Struct('<QIIIiiII32i')


def rows(data):
    if len(data)%PACKET.size:
        raise ValueError('partial SPU tap packet')
    return PACKET.iter_unpack(data)


def sum_errors(samples):
    out=[]
    for row in samples:
        for side,name in ((0,'left'),(1,'right')):
            error=row[4+side]-sum(row[8+side::2])
            if error:
                out.append([row[0],name,error])
    return out


def pcm(samples,channel):
    if channel not in range(16):
        raise ValueError('SPU channel outside 0..15')
    out=bytearray()
    for row in samples:
        left,right=row[8+2*channel:10+2*channel]
        out.extend(struct.pack('<hh',max(-32768,min(32767,left>>8)),max(-32768,min(32767,right>>8))))
    return bytes(out)


def capture_tick(clock,frames):
    found=[int(f['sequence']) for f in frames if int(f['start_tick'])<clock<=int(f['end_tick'])]
    if len(found)!=1:
        raise ValueError('sample clock outside one capture frame')
    return found[0]


def rates(period,timer):
    return dict(pcm_rate=[33513982,period],source_rate=[33513982,2*(65536-timer)])
