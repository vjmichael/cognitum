"""C15 selective MOTChallenge historical parser and diagnostic parity."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from cognitum.spatial_mot_adapter import read_mot,evaluate,MOTRejected

class C15MOTDiagnosticsTests(unittest.TestCase):
    def test_real_mot_text_fixture_separates_gt_and_predictions(self):
        with TemporaryDirectory() as tmp:
            gt=Path(tmp)/"gt.txt"
            pred=Path(tmp)/"prediction.txt"
            gt.write_text("1,1,0,0,10,10,1,1,1\n"
                          "1,2,50,0,10,10,1,1,1\n"
                          "2,1,1,0,10,10,1,1,1\n"
                          "2,2,51,0,10,10,1,1,1\n")
            pred.write_text("1,10,0,0,10,10,1\n"
                            "1,20,50,0,10,10,1\n"
                            "2,20,1,0,10,10,1\n"
                            "2,10,51,0,10,10,1\n")
            truth,gt_hash=read_mot(gt,kind="gt")
            predicted,pred_hash=read_mot(pred,kind="prediction")
            self.assertNotEqual(gt_hash,pred_hash)
            report=evaluate(truth,predicted)
            self.assertEqual(report["matched_boxes"],4)
            self.assertEqual(report["id_switches_diagnostic"],2)
            self.assertEqual(report["false_positives"],0)
            self.assertEqual(report["false_negatives"],0)
            self.assertTrue(report["not_official_motchallenge_metrics"])

    def test_invalid_and_nonfinite_mot_refused(self):
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"bad.csv"
            file.write_text("1,1,nan,0,10,10,1\n")
            with self.assertRaises(MOTRejected):
                read_mot(file,kind="prediction")
            file.write_text("1,1,0,0,-10,10,1\n")
            with self.assertRaises(MOTRejected):
                read_mot(file,kind="prediction")
            with self.assertRaises(MOTRejected):
                read_mot(file,kind="unknown")


if __name__=="__main__":
    unittest.main()
