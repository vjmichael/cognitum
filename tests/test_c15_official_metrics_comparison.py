"""Evidence-only parser tests; never substitute synthetic fixtures for MOT17 benchmark."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.c15_compare_official_trackeval import read_summary, compare


class OfficialTrackEvalMetricExtractor(unittest.TestCase):
    def test_exact_columns_and_deltas(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            a=root/"c15.txt"; b=root/"byte.txt"
            a.write_text("HOTA DetA MOTA IDF1\n45.5 55.0 28.5 49.0\n")
            b.write_text("HOTA DetA MOTA IDF1\n48.0 57.0 31.0 52.0\n")
            result=compare(a,b)
            self.assertEqual(result["c15"],{"HOTA":45.5,"MOTA":28.5,"IDF1":49.0})
            self.assertEqual(result["c15_minus_bytetrack"],
                             {"HOTA":-2.5,"MOTA":-2.5,"IDF1":-3.0})
            self.assertFalse(result["official_leaderboard_submission"])

    def test_missing_nonnumeric_nan_duplicate_and_reused_summary_rejected(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/"summary.txt"
            for content in ("", "HOTA MOTA\n45 20\n",
                            "HOTA MOTA IDF1\n50 nan 30\n",
                            "HOTA HOTA MOTA IDF1\n50 50 30 40\n",
                            "HOTA MOTA IDF1\n110 40 50\n",
                            "HOTA MOTA IDF1\n40 30\n"):
                with self.subTest(content=content):
                    path.write_text(content)
                    with self.assertRaises(ValueError):
                        read_summary(path)
            path.write_text("HOTA MOTA IDF1\n50 30 40\n")
            with self.assertRaises(ValueError):
                compare(path,path)


if __name__=="__main__":
    unittest.main()
