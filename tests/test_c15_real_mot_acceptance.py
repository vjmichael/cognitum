"""MOT17 acceptance harness tests: real independent detector input contract.

These are synthetic *tests of the harness*, NEVER benchmark evidence.
Real dataset evidence must come from c15-real-mot17.yml.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.c15_real_mot_acceptance import run,real_tracking
from cognitum.spatial_mot_adapter import Box


class C15RealMOTAcceptanceContract(unittest.TestCase):
    def test_detector_tracking_precedes_gt_and_writes_valid_mot_rows(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            gt=root/"gt.txt"
            det=root/"det.txt"
            result=root/"output.txt"
            gt.write_text("1,1,0,0,10,10,1,1,1\n"
                          "2,1,1,0,10,10,1,1,1\n")
            det.write_text("1,-1,0,0,10,10,0.85\n"
                           "2,-1,1,0,10,10,0.90\n")
            summary=run(gt,det,result,sequence_id="synthetic",
                        licensed_use=True)
            self.assertEqual(summary["status"],
                "REAL_DETECTION_INPUTS_EVALUATED_DIAGNOSTIC_ONLY")
            self.assertTrue(summary["metrics"]["not_official_motchallenge_metrics"])
            self.assertEqual(summary["prediction_rows"],2)
            self.assertEqual(summary["detector_rows_dropped_for_bounded_capacity"],0)
            rows=result.read_text().splitlines()
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0].split(",")[1],"1")
            self.assertEqual(rows[1].split(",")[1],"1")
            with self.assertRaises(ValueError):
                run(gt,det,result,sequence_id="same",licensed_use=True)

    def test_official_trackeval_staging_keeps_roles_and_versions(self):
        from tools.c15_stage_trackeval import stage
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            gt=root/"gt.txt"
            c15=root/"c15.txt"
            byte=root/"bytetrack.txt"
            gt.write_text("1,1,0,0,10,10,1,1,1\n")
            c15.write_text("1,3,0,0,10,10,0.8,-1,-1,-1\n")
            byte.write_text("1,4,0,0,10,10,0.8,-1,-1,-1\n")
            target=root/"stage"
            seqmap,hashes=stage(target,gt,c15,byte)
            self.assertTrue(seqmap.is_file())
            self.assertIn("MOT17-02-FRCNN",seqmap.read_text())
            self.assertEqual(len(hashes),3)
            self.assertNotEqual(hashes["gt"],hashes["c15"])
            self.assertTrue(
                (target/"trackers"/"MOT17-train"/"C15"/"data"/
                 "MOT17-02-FRCNN.txt").is_file())
            with self.assertRaises(ValueError):
                stage(target,gt,c15,byte)
            with self.assertRaises(ValueError):
                stage(root/"bad_stage",gt,gt,byte)

    def test_missing_rights_and_identical_path_block(self):
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"data.txt"
            file.write_text("1,1,0,0,10,10,1\n")
            with self.assertRaises(ValueError):
                run(file,file,Path(tmp)/"result.txt",sequence_id="invalid",licensed_use=False)
            with self.assertRaises(ValueError):
                run(file,file,Path(tmp)/"result.txt",sequence_id="invalid",licensed_use=True)

    def test_bounded_64_capacity_is_measured_not_hidden(self):
        det=tuple(Box(1,-1,float(i*15),0.,10.,10.,.9)
                  for i in range(70))
        pred,latency,dropped=real_tracking(det)
        self.assertGreater(dropped,0)
        self.assertLessEqual(len(pred),64)
        self.assertGreaterEqual(latency,0)


if __name__=="__main__":
    unittest.main()
