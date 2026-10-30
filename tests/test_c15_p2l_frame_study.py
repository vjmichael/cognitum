"""No real-frame scores may be reported in an unbacked environment."""
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from PIL import Image, ImageDraw
from cognitum.spatial_p2l_appearance import P2LRejected
from tools.run_c15_p2l_frame_study import study

SEQ='MOT17-02-DPM'

class P2LFrameTests(unittest.TestCase):
    def test_missing_real_frames_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            r=study(data_zip=root/'missing.zip',frames_dir=root/'no_frames',sequence=SEQ,
                    frames=2,output=root/'out')
            self.assertEqual(r['status'],'blocked_real_mot17_train_frames_missing')
            self.assertIsNone(r['official_metrics']);self.assertFalse((root/'out').exists())

    def test_single_synthetic_image_backed_staging_does_not_claim_official_scores(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);frame_dir=root/'img1';frame_dir.mkdir()
            img=Image.new('L',(180,50),128);ImageDraw.Draw(img).rectangle((0,10,11,21),fill=240)
            for f in (1,2):img.save(frame_dir/f'{f:06d}.jpg')
            source=''.join(f'{f},12,{f-1},10,12,12,1,-1,-1,-1\n' for f in (1,2)).encode()
            with zipfile.ZipFile(root/'source.zip','w') as z:
                z.writestr(f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{SEQ}.txt',source)
            r=study(data_zip=root/'source.zip',frames_dir=frame_dir,sequence=SEQ,
                    frames=2,output=root/'out')
            self.assertEqual(r['status'],'image_backed_research_outputs_ready_for_official_evaluator')
            self.assertIsNone(r['official_metrics'])
            self.assertEqual(r['boxes'],2)
            self.assertEqual(len(r['output_sha256']),4)
            out=(root/'out'/'CognitumP2LHistogram.txt').read_text().splitlines()
            self.assertTrue(all(int(v.split(',')[1]) != 12 for v in out))
            self.assertEqual([v.split(',')[2:] for v in out],[v.split(',')[2:] for v in source.decode().splitlines()])

    def test_output_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'out').mkdir();(root/'out'/'existing').write_text('x')
            with self.assertRaisesRegex(P2LRejected,'STAGING_DIRECTORY_NOT_EMPTY'):
                study(data_zip=root/'source.zip',frames_dir=root/'missing',sequence=SEQ,
                      frames=2,output=root/'out')

if __name__=='__main__':unittest.main()
