"""C15 opt-in official TrackEval runner contract; mocked process != real run."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import unittest

from cognitum.spatial_official_trackeval import (
    MOTManifest,OfficialEvaluation,run,_validate,
)


def make(root:Path):
    data=root/"data"
    target="MOT17-train"
    gt=data/"gt"/target/"Seq1"/"gt"/"gt.txt"
    pred=data/"trackers"/target/"Candidate"/"data"/"Seq1.txt"
    seqmap=data/"gt"/"seqmaps"/(target+".txt")
    runner=root/"trackeval"/"scripts"/"run_mot_challenge.py"
    marker=root/"trackeval"/"trackeval"/"metrics"/"hota.py"
    entries={
        gt:"1,1,0,0,10,10,1,1,1\n",
        pred:"1,5,0,0,10,10,1\n",
        seqmap:"name\nSeq1\n",
        runner:"# test placeholder, never run\n",
        marker:"# TrackEval known package marker\n",
    }
    for filename,content in entries.items():
        filename.parent.mkdir(parents=True,exist_ok=True)
        filename.write_text(content)
    h=lambda path:sha256(path.read_bytes()).hexdigest()
    m=MOTManifest(data,(root/"trackeval"),"MOT17","train","Seq1","Candidate",
                  h(gt),h(pred),h(seqmap),h(runner))
    return m,gt,pred,runner


class C15OfficialTrackEvalAdapter(unittest.TestCase):
    def test_missing_tool_and_forged_inputs_are_blocked(self):
        with TemporaryDirectory() as tmp:
            m,gt,pred,runner=make(Path(tmp))
            self.assertEqual(run(replace(m,runner_sha256="0"*64)).status,
                             "BLOCKED_INPUT_OR_SOURCE_INTEGRITY")
            pred.write_text("1,7,7,7,10,10,1\n")
            self.assertEqual(run(m).status,"BLOCKED_INPUT_OR_SOURCE_INTEGRITY")
            with self.assertRaises(ValueError):
                _validate(replace(m,benchmark="../evil"))

    def test_stale_output_is_blocked_without_external_execution(self):
        with TemporaryDirectory() as tmp:
            m,_,_,_=make(Path(tmp))
            summary=m.data_root/"trackers"/"MOT17-train"/"Candidate"/"pedestrian_summary.txt"
            summary.write_text("HOTA MOTA IDF1\n90 80 70\n")
            with patch("cognitum.spatial_official_trackeval.subprocess.run") as proc:
                verdict=run(m)
            self.assertEqual(verdict.status,"BLOCKED_STALE_SUMMARY")
            proc.assert_not_called()

    def test_mock_acceptance_is_adapter_contract_not_real_evidence(self):
        with TemporaryDirectory() as tmp:
            m,_,_,_=make(Path(tmp))
            summary=m.data_root/"trackers"/"MOT17-train"/"Candidate"/"pedestrian_summary.txt"
            def pretend(command,**kwargs):
                self.assertIn("--GT_FOLDER",command)
                self.assertIn("--TRACKERS_FOLDER",command)
                # Pinned TrackEval CLI treats an explicitly supplied
                # SEQMAP_FILE as a list and its dataset expects one path.
                # The pinned evaluator uses GT_FOLDER/seqmaps by default.
                self.assertNotIn("--SEQMAP_FILE",command)
                self.assertTrue((m.data_root/"gt"/"seqmaps"/"MOT17-train.txt").is_file())
                self.assertIn("Candidate",command)
                summary.write_text("HOTA MOTA IDF1\n90 80 70\n")
                return subprocess.CompletedProcess(command,0,b"fake stdout",b"")
            with patch("cognitum.spatial_official_trackeval.subprocess.run",
                       side_effect=pretend) as mocked:
                r=run(m)
            self.assertEqual(r.status,"TRACK_EVAL_EXECUTED_SOURCE_UNATTESTED")
            self.assertEqual(dict(r.scores)["HOTA"],90)
            self.assertEqual(mocked.call_count,1)
            self.assertIn("dataset_license_and_source_attestation_not_checked",r.limitations)


if __name__=="__main__":
    unittest.main()
