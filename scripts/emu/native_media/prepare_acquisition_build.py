"""Recreate the pinned hooks source, then add the j6acq host-side polygon observer.

Build under a private directory. The installed hooks instrument stays unchanged.
J6ACQ_POLYGONS selects the output directory. No observer member is serialized.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def replace(path,old,new):
    text=path.read_text()
    if text.count(old)!=1:
        raise ValueError('source anchor changed: '+str(path)+' '+repr(old[:80]))
    path.write_text(text.replace(old,new))


def instrument(out):
    src=out/'src'
    shutil.copyfile(HERE/'AcquisitionPolygons.h',src/'AcquisitionPolygons.h')
    replace(src/'GPU3D.h','    void VBlank() noexcept;',
        '    void AcquisitionDump(const char* directory, unsigned sequence, unsigned gfc) const;\n    void VBlank() noexcept;')
    replace(src/'GPU3D.cpp','#include "GPU3D.h"',
        '#include "GPU3D.h"\n#include "AcquisitionPolygons.h"\n#include <fstream>\n#include <filesystem>')
    method='''
void GPU3D::AcquisitionDump(const char* directory,unsigned sequence,unsigned gfc) const
{
    if (!directory || sequence < 80 || sequence > 100) return;
    std::filesystem::create_directories(directory);
    std::vector<AcquisitionPolygon> polys;
    for(unsigned i=0;i<RenderNumPolygons;i++) {
        const auto& p=*RenderPolygonRAM[i];
        AcquisitionPolygon q;
        q.index=i; q.attr=p.Attr; q.tex=p.TexParam; q.palette=p.TexPalette;
        q.wbuffer=p.WBuffer; q.facing=p.FacingView;
        for(unsigned j=0;j<p.NumVertices;j++) {
            const auto& v=*p.Vertices[j]; AcquisitionVertex u;
            for(unsigned k=0;k<4;k++) u.position[k]=v.Position[k];
            for(unsigned k=0;k<2;k++) { u.screen[k]=v.FinalPosition[k]; u.texture[k]=v.TexCoords[k]; }
            for(unsigned k=0;k<3;k++) u.color[k]=v.FinalColor[k];
            u.z=p.FinalZ[j]; u.w=p.FinalW[j]; q.vertices.push_back(u);
        }
        polys.push_back(q);
    }
    std::array<int32_t,16> projection;
    for(unsigned i=0;i<16;i++) projection[i]=ProjMatrix[i];
    auto base=std::filesystem::path(directory)/std::to_string(sequence);
    std::ofstream json(base.string()+".json");
    acquisitionPolygons(json,sequence,gfc,RenderDispCnt,RenderClearAttr2,projection,polys);
    std::ofstream texture(base.string()+".texture",std::ios::binary);
    std::ofstream palette(base.string()+".palette",std::ios::binary);
    for(unsigned i=0;i<512*1024;i++) texture.put(char(GPU.ReadVRAMFlat_Texture<u8>(i)));
    for(unsigned i=0;i<128*1024;i++) palette.put(char(GPU.ReadVRAMFlat_TexPal<u8>(i)));
    if(!json || !texture || !palette) throw std::runtime_error("polygon dump IO failure");
}
'''
    replace(src/'GPU3D.cpp','void GPU3D::VBlank() noexcept',method+'\nvoid GPU3D::VBlank() noexcept')
    emu=src/'frontend/qt_sdl/EmuThread.cpp'
    replace(emu,'                nlines = nds->RunFrame();',
        '''                nlines = nds->RunFrame();
                if (nativeCapture.active())
                    nds->GPU.GPU3D.AcquisitionDump(std::getenv("J6ACQ_POLYGONS"),nativeCapture.sequence(),nds->ARM9Read32(0x020A0F10));''')


def instrument_spu(out):
    src=out/'src'
    shutil.copyfile(HERE/'AcquisitionSpu.h',src/'AcquisitionSpu.h')
    replace(src/'SPU.cpp','#include "SPU.h"','#include "SPU.h"\n#include "AcquisitionSpu.h"')
    replace(src/'SPU.cpp','    s32 left = 0, right = 0;','    std::array<int32_t,32> acqChannels{};\n    s32 left = 0, right = 0;')
    # Preserve each original DoRun/PanOutput pair and observe the exact delta
    # added to the mixer. The first four channels have separate routing bits.
    for n in (0,2):
        old=f'        Channels[{n}].PanOutput(ch{n}, left, right);'
        new=f'''        {{ auto l=left,r=right;
{old}
          acqChannels[{2*n}]=left-l; acqChannels[{2*n+1}]=right-r; }}'''
        replace(src/'SPU.cpp',old,new)
    for n,bit in ((1,12),(3,13)):
        old=f'        if (!(Cnt & (1<<{bit}))) Channels[{n}].PanOutput(ch{n}, left, right);'
        new=f'''        {{ auto l=left,r=right;
{old}
          acqChannels[{2*n}]=left-l; acqChannels[{2*n+1}]=right-r; }}'''
        replace(src/'SPU.cpp',old,new)
    replace(src/'SPU.cpp','            chan->PanOutput(channel, left, right);',
        '''            auto acqL=left,acqR=right;
            chan->PanOutput(channel, left, right);
            acqChannels[i*2]=left-acqL; acqChannels[i*2+1]=right-acqR;''')
    replace(src/'SPU.cpp','        // sound capture',
        '''        std::array<uint32_t,16> acqCnt;
        for(unsigned i=0;i<16;i++) acqCnt[i]=Channels[i].Cnt;
        acquisitionSpuSampleAll(NDS.SchedList[Event_SPU].Timestamp,spucycles<<1,left,right,
            acqCnt,acqChannels,[&](){ return NDS.ARM9Read32(0x020A0F10); });
        // sound capture''')
    for n,ty in ((8,'u8'),(16,'u16'),(32,'u32')):
        old=f'void SPU::Write{n}(u32 addr, {ty} val)\n{{'
        replace(src/'SPU.cpp',old,old+f'\n    AcquisitionRegisterGuard<SPUChannel> acqReg(NDS.ARM7Timestamp,addr,val,{n//8},&Channels[0]);')
    emu=src/'frontend/qt_sdl/EmuThread.cpp'
    replace(emu,'#include "SPU.h"','#include "SPU.h"\n#include "../../AcquisitionSpu.h"')
    replace(emu,'                nlines = nds->RunFrame();',
        '''                if(nativeCapture.active() && std::getenv("J6ACQ_SPU"))
                    acquisitionSpuBegin(nativeCapture.sequence(),nds->ARM9Read32(0x020A0F10));
                nlines = nds->RunFrame();
                acquisitionSpuEnd();''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--spu',action='store_true')
    a=p.parse_args()
    subprocess.run([sys.executable,str(HERE/'prepare_hooks_build.py'),'--repository',str(a.repository),'--out',str(a.out)],check=True)
    instrument(a.out)
    if a.spu: instrument_spu(a.out)
    for rel in ('src/GPU3D.h','src/GPU3D.cpp','src/AcquisitionPolygons.h','src/frontend/qt_sdl/EmuThread.cpp'):
        print(hashlib.sha256((a.out/rel).read_bytes()).hexdigest(),rel)
