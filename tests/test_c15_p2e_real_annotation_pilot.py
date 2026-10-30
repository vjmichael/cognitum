import tempfile
import unittest
from pathlib import Path
from cognitum.spatial_mot_adapter import MOTRejected
from tools.c15_real_annotation_pilot import run, git_blob_id

class RealAnnotationPilotTests(unittest.TestCase):
    def _files(self,dir):
        # Small MOT-format fixture, synthetic, used for isolated pipeline tests ONLY.
        p=Path(dir);g=p/'gt.txt';t=p/'pred.txt'
        g.write_text('1,1,0,0,10,10,1,1,1,1\n2,1,1,0,10,10,1,1,1,1\n3,1,2,0,10,10,1,1,1,1\n')
        t.write_text('1,3,0,0,10,10,-1,-1,-1,-1\n2,3,1,0,10,10,-1,-1,-1,-1\n3,3,2,0,10,10,-1,-1,-1,-1\n')
        return g,t
    def test_known_git_blob_hash(self):
        import hashlib
        self.assertEqual(git_blob_id(b'abc'),hashlib.sha1(b'blob 3\0abc').hexdigest())
    def test_diagnostic_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            g,t=self._files(d)
            a=run(g,t,pin_tud=False)
            self.assertEqual(a['diagnostic']['matched_boxes'],3)
            self.assertEqual(a['diagnostic']['false_negatives'],0)
            self.assertEqual(a['diagnostic']['false_positives'],0)
            self.assertEqual(a['diagnostic']['id_switches_diagnostic'],0)
            self.assertFalse(a['official_motchallenge_metrics'])
            self.assertFalse(a['deep_sort_executed'])
    def test_identical_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            g,t=self._files(d)
            with self.assertRaisesRegex(MOTRejected,'INPUT_ROLES_MUST_BE_DISTINCT'):run(g,g,pin_tud=False)
    def test_pin_rejects_other_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            g,t=self._files(d)
            with self.assertRaisesRegex(MOTRejected,'SOURCE_GIT_BLOB_MISMATCH'):run(g,t)
    def test_identity_switch_detected(self):
        with tempfile.TemporaryDirectory() as d:
            g,t=self._files(d)
            t.write_text('1,3,0,0,10,10,-1,-1,-1,-1\n2,4,1,0,10,10,-1,-1,-1,-1\n3,4,2,0,10,10,-1,-1,-1,-1\n')
            self.assertEqual(run(g,t,pin_tud=False)['diagnostic']['id_switches_diagnostic'],1)
    def test_bad_predictions_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            g,t=self._files(d)
            t.write_text('2,3,0,0,0,10,1,-1,-1,-1\n')
            with self.assertRaises(MOTRejected):run(g,t,pin_tud=False)

if __name__=='__main__':unittest.main()
