"""Open every native image and map it to full-resolution inspection pages."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--unique', action='store_true', help='share a view only for byte-identical images')
    a = p.parse_args()
    out = a.root / 'views'
    out.mkdir(exist_ok=True)
    records, seen, pages = [], {}, {}
    sheet = None
    active_page, slot = None, 8
    page_counts = {}
    for folder in sorted((a.root / 'captures').iterdir()):
        rows = json.loads((folder / 'result.json').read_text())['validation']['rows']
        if not a.unique:
            slot = 8
        for i,row in enumerate(rows):
            source = folder / f'{i:06d}.ppm'
            raw = source.read_bytes()
            header = b'P6\n256 384\n255\n'
            if not raw.startswith(header) or len(raw) != len(header)+256*384*3:
                raise ValueError('invalid native PPM')
            digest = hashlib.sha256(raw).hexdigest()
            if row.get('image_sha256',digest) != digest:
                raise ValueError('recorded image hash differs')
            with Image.open(source) as im:
                image = im.convert('RGB')
                if image.size != (256,384) or image.tobytes() != raw[len(header):]:
                    raise ValueError('decoded pixels differ from raw image')
            if a.unique and digest in seen:
                representative = seen[digest]
                if representative['source'].read_bytes() != raw:
                    raise ValueError('hash collision')
                page, index = representative['page'], representative['slot']
            else:
                if slot == 8:
                    if sheet is not None:
                        sheet.save(out/active_page)
                    n = page_counts.get(folder.name,0)
                    page_counts[folder.name] = n+1
                    active_page = f'{folder.name}-{n:03d}.png'
                    sheet = Image.new('RGB',(1024,808),'#101010')
                    slot = 0
                page, index = active_page, slot
                x,y = slot%4*256,slot//4*404
                ImageDraw.Draw(sheet).text((x+4,y+2),f'{i} state {row["w"]["p1st"]} frame {row["nds_frame"]}',fill='white')
                sheet.paste(image,(x,y+20))
                pages[page] = True
                slot += 1
                seen.setdefault(digest,{'source':source,'page':page,'slot':index})
            records.append({'source':str(source.relative_to(a.root)), 'sequence':i,
                            'nds_frame':row['nds_frame'],'image_sha256':digest,'page':page,'slot':index})
    if sheet is not None:
        sheet.save(out/active_page)
    (out/'inspection.json').write_text(json.dumps({'opened_frames':len(records),'unique_images':len(seen),
        'mode':'byte-identical grouping' if a.unique else 'every-frame pages','pages':list(pages),
        'frames':records,'visual_review':'pending'},indent=2)+'\n')
    print(json.dumps({'opened_frames':len(records),'unique_images':len(seen),'pages':len(pages),'out':str(out)}))

if __name__ == '__main__': main()
