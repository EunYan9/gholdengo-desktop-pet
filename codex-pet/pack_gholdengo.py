"""Install the verified native render byte-for-byte; do not synthesize actions."""
import hashlib,json,shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
source=ROOT/'model-source/gholdengo/ready-made/scarlet-front.webp'
target=ROOT/'sprites/gholdengo/defaultwait01_loop.webp'
target.parent.mkdir(exist_ok=True)
with Image.open(source) as movie:
    assert movie.size==(512,512) and movie.n_frames==80 and movie.info.get('loop')==0
    durations=[]
    for i in range(movie.n_frames):
        movie.seek(i);movie.load();durations.append(movie.info['duration'])
    movie.seek(0);movie.convert('RGBA').save(ROOT/'gholdengo-preview.png')
shutil.copy2(source,target)
shutil.copy2(source,ROOT/'gholdengo-preview.webp')
digest=hashlib.sha256(source.read_bytes()).hexdigest()
assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
manifest_path=ROOT/'sprites/manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['models']['gholdengo']={'defaultwait01_loop':{
    'frames':len(durations),'duration_ms':sum(durations),'loop':True,
    'size':512,'fps':30,'source':'scarlet-violet-native-surfing'}}
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
sources={
    'active':{'page':'https://pokestats.gg/sprites/gholdengo',
        'url':'https://assets.pokestats.gg/pokeapi/orig/pokemon/versions/generation-ix/scarlet-violet/1000.webp',
        'sha256':digest,'dimensions':[512,512],'frames':len(durations),'duration_ms':sum(durations),
        'body_actions':['native-surfing-loop'],'feedback':'Qt badge and tap ring; body loop stays unchanged',
        'credit':'PokeStats / Pokémon Scarlet & Violet; Pokémon / Nintendo / Creatures / GAME FREAK'},
    'examined':[
        {'page':'https://www.smogon.com/forums/threads/custom-3d-animated-renders.3526922/page-25',
         'urls':['https://i.imgur.com/CdsS47K.gif','https://i.imgur.com/lBv9YDH.gif','https://i.imgur.com/kRwXLf8.gif','https://i.imgur.com/JtQcx2R.gif'],
         'result':'35-frame standing and 80-frame surfing previews; 39x76 to 68x81; not selected because of low resolution and different shading'},
        {'url':'https://play.pokemonshowdown.com/sprites/ani/gholdengo.gif',
         'result':'63x82 surfing loop; not an extra action; not selected'},
        {'page':'https://models.spriters-resource.com/nintendo_switch/pokemonlegendsza/asset/576688/page-1/',
         'result':'Model and texture archive; no verified ready-to-use action set'},
    ],
    'removed':['procedural wave','procedural annoyed','procedural focus','procedural celebration','procedural sleep'],
}
(ROOT/'gholdengo-sources.json').write_text(json.dumps(sources,indent=2,ensure_ascii=False),encoding='utf-8')
print('Native Gholdengo only:',len(durations),'frames,',sum(durations),'ms; source bytes preserved')
