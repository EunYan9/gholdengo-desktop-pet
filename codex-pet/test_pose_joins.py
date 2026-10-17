"""Check decoded pixels at actual animation seams, not only clip names."""
import json
from pathlib import Path
import unittest
from PIL import Image, ImageChops, ImageStat

ROOT=Path(__file__).resolve().parent/'sprites'
MANIFEST=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))['models']


def frames(model, clip):
    result=[]
    with Image.open(ROOT/model/(clip+'.webp')) as movie:
        for index in range(movie.n_frames):
            movie.seek(index)
            frame=Image.new('RGBA',movie.size)
            frame.alpha_composite(movie.convert('RGBA'))
            result.append(frame.tobytes())
    return result


class PoseJoins(unittest.TestCase):
    def test_opening_has_real_in_between_frames(self):
        # A renderer returning the idle pose for frames 0..8 used to pass all
        # boundary checks, while visibly teleporting to the open lid at 9.
        with Image.open(ROOT/'chest/focus01_start.webp') as movie:
            opening=[]
            for index in range(10):
                movie.seek(index);opening.append(movie.convert('RGBA').copy())
        self.assertGreaterEqual(len({frame.tobytes() for frame in opening[:8]}),7)
        changes=[sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/4
                 for a,b in zip(opening,opening[1:])]
        self.assertLess(max(changes),14,'Opening contains a missing-frame jump')

    def test_focus_matches_exactly(self):
        start=frames('chest','focus01_start');loop=frames('chest','focus01_loop');end=frames('chest','focus01_end')
        self.assertEqual(start[-1],loop[0])
        self.assertEqual(loop[-1],loop[0])
        self.assertEqual(loop[0],end[0])
        self.assertEqual(end[-1],start[0])
        self.assertGreater(len(set(loop)),2)
        entry_meta=MANIFEST['chest']['focus01_loop'];end_meta=MANIFEST['chest']['focus01_end']
        for index,source_frame in enumerate(entry_meta['source_indices']):
            target=end_meta['source_indices'].index(source_frame)
            self.assertEqual(loop[index],end[target],f'Wrong exit pose at loop frame {index}')

    def test_work_reactions_join_without_closing(self):
        source=frames('chest','notice01')
        loop=frames('chest','focus01_loop')
        for name in ('focus01_ack','focus01_glance'):
            reaction=frames('chest',name)
            indices=MANIFEST['chest'][name]['source_indices']
            for image,index in zip(reaction,indices):self.assertEqual(image,source[index])
            self.assertEqual(reaction[-1],loop[0])
            for index in MANIFEST['chest']['focus01_loop']['source_indices']:
                offset=24 if name=='focus01_ack' else 0
                start=indices.index(index,offset)
                self.assertTrue(all(8<=frame<=24 for frame in indices[start:]))
                self.assertEqual(reaction[start],source[index])

    def test_cancel_matches_original_pose(self):
        for model,original,cancel in [('chest','sleep01_start','sleep01_cancel'),
                                      ('roaming','rest01_start','rest01_cancel')]:
            opening=frames(model,original);closing=frames(model,cancel)
            self.assertEqual(opening[-1],closing[0])
            self.assertEqual(opening[0],closing[-1])

    def test_completion_is_not_happy(self):
        for model in ('chest','roaming'):
            self.assertNotEqual(MANIFEST[model]['finish01']['source'],'glad01')
            self.assertNotEqual(frames(model,'finish01'),frames(model,'glad01'))

    def test_encoded_source_indices(self):
        for model,clips in MANIFEST.items():
            for clip,metadata in clips.items():
                if 'source_indices' in metadata:
                    with Image.open(ROOT/model/(clip+'.webp')) as movie:
                        self.assertEqual(len(metadata['source_indices']),movie.n_frames)


if __name__=='__main__':unittest.main()
