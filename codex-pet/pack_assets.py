"""Package original rendered frames; keep one fixed canvas per model."""
import json
from bisect import bisect_right
from itertools import accumulate
from pathlib import Path
import sys
from PIL import Image, ImageChops, ImageDraw

ROOT=Path(__file__).resolve().parent
output=ROOT/'sprites'; output.mkdir(exist_ok=True)
manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8')) if (output/'manifest.json').exists() else {'fps':30,'models':{}}
contacts=[]
requested=set(sys.argv[1:] or ('chest','roaming'))
if requested-{'chest','roaming'}:raise SystemExit('Unknown model')
for model in ('chest','roaming'):
    selected={'defaultwait01_loop','glad01','notice01','finish01'}
    if model=='chest':
        selected.update({'defaultidle01','hate01','focus01_start','focus01_loop','focus01_end',
                         'focus01_ack','focus01_glance',
                         'sleep01_start','sleep01_loop','sleep01_end','sleep01_cancel'})
    else:
        selected.update({'battlewait01_loop','defaultidle02','refresh01','rest01_start','rest01_loop','rest01_end','rest01_cancel'})
    folders=sorted(p for p in (ROOT/'rendered'/model).iterdir() if p.name in selected and (p/'metadata.json').exists())
    missing=selected-{p.name for p in folders}
    if missing:raise RuntimeError('Missing original clips for '+model+': '+', '.join(sorted(missing)))
    union=None
    for folder in folders:
        for p in folder.glob('*.png'):
            with Image.open(p) as im:
                box=im.getchannel('A').getbbox()
            if box:
                union=box if union is None else (min(union[0],box[0]),min(union[1],box[1]),max(union[2],box[2]),max(union[3],box[3]))
    if union is None:raise RuntimeError('No rendered model: '+model)
    size=max(union[2]-union[0],union[3]-union[1])+24
    cx=(union[0]+union[2])/2;cy=(union[1]+union[3])/2
    crop=(round(cx-size/2),round(cy-size/2),round(cx-size/2)+size,round(cy-size/2)+size)
    target=output/model;target.mkdir(exist_ok=True)
    manifest['models'][model]={}
    for folder in folders:
        meta=json.loads((folder/'metadata.json').read_text())
        files=sorted(folder.glob('*.png'))
        if len(files)!=meta['frames']:raise RuntimeError('Incomplete '+str(folder))
        frames=[]
        for path in files:
            with Image.open(path) as im:frames.append(im.convert('RGBA').crop(crop))
        loop=folder.name.endswith('_loop')
        fps=meta.get('fps',30)
        duration=[round((i+1)*1000/fps)-round(i*1000/fps) for i in range(len(frames))]
        if model in requested:
            frames[0].save(target/(folder.name+'.webp'),format='WEBP',save_all=True,
                append_images=frames[1:],duration=duration,loop=0 if loop else 1,
                lossless=True,method=4)
        elif not (target/(folder.name+'.webp')).exists():
            raise RuntimeError('Missing cached clip: '+folder.name)
        ends=list(accumulate(duration));encoded_indices=[];elapsed=0
        with Image.open(target/(folder.name+'.webp')) as encoded:
            for index in range(encoded.n_frames):
                encoded.seek(index);encoded.load()
                encoded_indices.append(min(len(frames)-1,bisect_right(ends,elapsed)))
                elapsed+=encoded.info['duration']
        details={'frames':len(encoded_indices),'duration_ms':sum(duration),'loop':loop,'size':size,'fps':fps}
        if len(encoded_indices)!=len(frames):details['frame_indices']=encoded_indices
        if 'source_indices' in meta:
            details.update(source=meta['source'],source_indices=[meta['source_indices'][i] for i in encoded_indices])
        manifest['models'][model][folder.name]=details
        # Contact strip of original poses; no composite limbs or modified motion.
        strip=Image.new('RGB',(720,160),'#1d2b32');draw=ImageDraw.Draw(strip)
        draw.text((8,5),model+' / '+folder.name,fill='#d9c28a')
        for k in range(5):
            frame=frames[round((len(frames)-1)*k/4)].copy();frame.thumbnail((124,124))
            strip.paste(frame,(k*144+(144-frame.width)//2,28),frame)
        contacts.append(strip)
        print(model,folder.name,len(frames),'frames',flush=True)
(output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(720,len(contacts)*160),'#1d2b32')
for i,strip in enumerate(contacts):sheet.paste(strip,(0,i*160))
sheet.save(ROOT/'animation-contact-sheet.jpg',quality=90)
print('PACK COMPLETE',flush=True)
