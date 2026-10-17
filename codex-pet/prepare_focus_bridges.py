"""Build exactly matching pose paths from continuous original animation frames."""
import json
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parent / 'rendered'


def extract(model, name, source, indices, fps=30):
    files = sorted((ROOT / model / source).glob('*.png'))
    if not files: raise RuntimeError('Missing original source: '+source)
    target = ROOT / model / name
    target.mkdir(exist_ok=True)
    for old in target.glob('*.png'): old.unlink()
    for index, source_index in enumerate(indices):
        shutil.copy2(files[source_index], target / f'{index:04}.png')
    (target / 'metadata.json').write_text(json.dumps({
        'duration': len(indices)/fps, 'frames': len(indices), 'fps': fps,
        'source': source, 'source_indices': indices,
    }, indent=2), encoding='utf-8')
    print(name, len(indices), 'original frames', flush=True)


# Entry -> loop -> exit share the exact same source pose, not nearest poses
# from different clips. The quiet middle segment plays back and forth slowly.
extract('chest', 'focus01_start', 'notice01', list(range(25)))
extract('chest', 'focus01_loop', 'notice01', list(range(24, 11, -1))+list(range(13, 25)), fps=15)
extract('chest', 'focus01_end', 'notice01', list(range(24, -1, -1)))
# A focused pet answers a tap by lifting its lid slightly and looking up,
# without returning to the closed idle pose. The opening prefix also lets a
# tap interrupt entry/exit at any original frame, including frames 0..7.
extract('chest', 'focus01_ack', 'notice01', list(range(25))+list(range(23, 7, -1))+list(range(9, 25)))
extract('chest', 'focus01_glance', 'notice01', list(range(24, 11, -1))+list(range(13, 25)), fps=24)
for model, source, target in [('chest','sleep01_start','sleep01_cancel'),
                              ('roaming','rest01_start','rest01_cancel')]:
    count = len(list((ROOT/model/source).glob('*.png')))
    extract(model, target, source, list(range(count-1, -1, -1)))
for model, source in [('chest','defaultidle02'),('roaming','roar01')]:
    count = len(list((ROOT/model/source).glob('*.png')))
    extract(model, 'finish01', source, list(range(count)))
