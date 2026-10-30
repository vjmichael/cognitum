"""Synthetic defensive P2H checks; genuine input trial recorded separately."""
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path
from cognitum.spatial_mot17_realdata_gate import (stage_mot17,verify_staging,
      evaluate_with_official_trackeval,RealDataGateRejected,_validate_rows,verify_pinned_trackeval_source)
from cognitum.spatial_mot_adapter import read_mot,evaluate

SEQ='MOT17-02-DPM'
GT=f'data/gt/mot_challenge/MOT17-train/{SEQ}/gt/gt.txt'
INFO=f'data/gt/mot_challenge/MOT17-train/{SEQ}/seqinfo.ini'
PRED=f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{SEQ}.txt'
GM=f'train/{SEQ}/gt/gt.txt'
IM=f'train/{SEQ}/seqinfo.ini'
SEQMAP='data/gt/mot_challenge/seqmaps/MOT17-train.txt'
GT_BYTES=b'1,1,10,20,5,5,1,1,1\n2,1,10,20,5,5,1,1,1\n'
INFO_BYTES=(f'[Sequence]\nname={SEQ}\nframeRate=30\nseqLength=2\nimWidth=640\nimHeight=480\n').encode()
PRED_BYTES=b'1,0,10,20,5,5,1,-1,-1,-1\n2,0,10,20,5,5,1,-1,-1,-1\n'

class TestP2H(unittest.TestCase):
    def make_fixture(self,root,*,label_gt=None,pred=PRED_BYTES):
        a=root/'data.zip';b=root/'labels.zip'
        with zipfile.ZipFile(a,'w') as z:
            for name,data in [(GT,GT_BYTES),(INFO,INFO_BYTES),(PRED,pred),(SEQMAP,f'name\n{SEQ}\n'.encode())]:z.writestr(name,data)
        with zipfile.ZipFile(b,'w') as z:
            z.writestr(GM,GT_BYTES if label_gt is None else label_gt);z.writestr(IM,INFO_BYTES)
        return a,b
    def test_real_9_column_gt_and_zero_based_predictions_keep_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root)
            report=stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'staged')
            self.assertTrue(verify_staging(report))
            self.assertEqual((root/'staged/gt/MOT17-train'/SEQ/'gt/gt.txt').read_bytes(),GT_BYTES)
            self.assertEqual((root/'staged/trackers/MOT17-train/MPNTrack/data'/f'{SEQ}.txt').read_bytes(),PRED_BYTES)
            self.assertTrue(report['native_tracker_ids_preserved'])
            self.assertEqual(report['sequences'][0]['prediction']['min_track_id'],0)
            self.assertEqual(evaluate_with_official_trackeval(report)['status'],'blocked_official_evaluator_missing')
    def test_official_runner_uses_default_seqmap_path(self):
        """TrackEval's argparse treats explicit SEQMAP_FILE as a list; omit it."""
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root)
            report=stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'staged')
            checkout=root/'TrackEval'
            script=checkout/'scripts'/'run_mot_challenge.py';script.parent.mkdir(parents=True)
            script.write_text('pass\n')
            hota=checkout/'trackeval/metrics/hota.py';hota.parent.mkdir(parents=True)
            hota.write_text('pass\n')
            with mock.patch('cognitum.spatial_mot17_realdata_gate.subprocess.run',
                            return_value=mock.Mock(returncode=0)) as invoked:
                result=evaluate_with_official_trackeval(report,trackeval_root=checkout)
            argv=invoked.call_args.args[0]
            self.assertNotIn('--SEQMAP_FILE',argv)
            self.assertEqual(argv[argv.index('--DO_PREPROC')+1],'True')
            self.assertEqual(result['status'],'engine_summary_missing_or_invalid')

    def test_compat_launcher_is_explicit_and_preserves_official_script(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root)
            rep=stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'stage')
            checkout=root/'TrackEval'
            script=checkout/'scripts'/'run_mot_challenge.py';script.parent.mkdir(parents=True)
            script.write_text('pass\n'); original=script.read_bytes()
            hota=checkout/'trackeval/metrics/hota.py';hota.parent.mkdir(parents=True)
            hota.write_text('pass\n')
            with mock.patch('cognitum.spatial_mot17_realdata_gate.subprocess.run',
                            return_value=mock.Mock(returncode=0)) as invoked:
                outcome=evaluate_with_official_trackeval(rep,trackeval_root=checkout,
                    legacy_numpy_compat=True)
            argv=invoked.call_args.args[0]
            self.assertTrue(argv[1].endswith('c15_trackeval_legacy_numpy_compat.py'))
            self.assertEqual(argv[2],str(script))
            self.assertEqual(script.read_bytes(),original)
            self.assertEqual(outcome['status'],'engine_summary_missing_or_invalid')

    def test_corrupt_or_mismatched_pinned_source_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root)
            rep=stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'stage')
            checkout=root/'TrackEval'
            script=checkout/'scripts'/'run_mot_challenge.py';script.parent.mkdir(parents=True)
            script.write_text('pass\n')
            hota=checkout/'trackeval/metrics/hota.py';hota.parent.mkdir(parents=True)
            hota.write_text('pass\n')
            arc=root/'fake-source.zip'
            with zipfile.ZipFile(arc,'w') as z:z.writestr('TrackEval-master/scripts/run_mot_challenge.py','pass\n')
            with self.assertRaisesRegex(RealDataGateRejected,'SOURCE_GIT_TREE_MISMATCH'):
                verify_pinned_trackeval_source(source_zip=arc,checkout=checkout)
            outcome=evaluate_with_official_trackeval(rep,trackeval_root=checkout,source_zip=arc)
            self.assertEqual(outcome['status'],'blocked_unverified_trackeval_source')

    def test_independent_gt_archive_mismatch_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root,label_gt=b'different')
            with self.assertRaisesRegex(RealDataGateRejected,'INDEPENDENT_GT_MISMATCH'):
                stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'out')
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root);out=root/'out';out.mkdir();(out/'old').write_text('old')
            with self.assertRaisesRegex(RealDataGateRejected,'OUTPUT_DIRECTORY_MUST_BE_EMPTY'):
                stage_mot17(example_zip=a,mot17_labels_zip=b,output=out)
    def test_staged_tampering_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root);out=root/'out'
            report=stage_mot17(example_zip=a,mot17_labels_zip=b,output=out)
            (out/'gt/seqmaps/MOT17-train.txt').write_text('name\nother\n')
            with self.assertRaisesRegex(RealDataGateRejected,'STAGING_HASH_MISMATCH'):verify_staging(report)
            self.assertEqual(evaluate_with_official_trackeval(report)['status'],'blocked_staging_integrity_failure')
    def test_no_gt_as_predictions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root,pred=GT_BYTES)
            with self.assertRaisesRegex(RealDataGateRejected,'UNSUPPORTED_prediction_COLUMN_COUNT'):
                stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'out')
    def test_missing_official_checkout_honest_block(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root)
            report=stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'out')
            self.assertEqual(evaluate_with_official_trackeval(report,trackeval_root=root/'missing'),
                             {'status':'blocked_official_evaluator_missing','official_scores':None})
    def test_wrong_frame_number_denied(self):
        with self.assertRaisesRegex(RealDataGateRejected,'INVALID_prediction_ROW'):
            _validate_rows(b'3,0,10,20,5,5,1,-1,-1,-1\n',role='prediction',nframes=2)
    def test_prediction_negative_id_rejected(self):
        with self.assertRaisesRegex(RealDataGateRejected,'INVALID_prediction_ROW'):
            _validate_rows(b'1,-1,10,20,5,5,1,-1,-1,-1\n',role='prediction',nframes=2)
    def test_prediction_zero_id_diagnostic_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);gt=root/'gt.txt';pred=root/'pred.txt'
            gt.write_bytes(GT_BYTES);pred.write_bytes(PRED_BYTES)
            a,_=read_mot(gt,kind='gt');b,_=read_mot(pred,kind='prediction')
            self.assertEqual([r.track_id for r in b],[0,0]);self.assertEqual(evaluate(a,b)['matched_boxes'],2)
    def test_source_zip_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); z=root/'bad.zip'
            with zipfile.ZipFile(z,'w') as a:
                a.writestr('TrackEval-master/../evil.py','irrelevant')
            with self.assertRaisesRegex(RealDataGateRejected,'INVALID_SOURCE_ZIP_PATH'):
                verify_pinned_trackeval_source(source_zip=z,checkout=root)

    def test_source_archive_checkout_byte_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); z=root/'bad.zip'; checkout=root/'TrackEval'
            target=checkout/'scripts/run_mot_challenge.py'; target.parent.mkdir(parents=True)
            target.write_text('changed')
            with zipfile.ZipFile(z,'w') as a:
                a.writestr('TrackEval-master/scripts/run_mot_challenge.py','original')
            with self.assertRaisesRegex(RealDataGateRejected,'SOURCE_CHECKOUT_CONTENT_MISMATCH'):
                verify_pinned_trackeval_source(source_zip=z,checkout=checkout)

    def test_invalid_sequence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a,b=self.make_fixture(root)
            with self.assertRaisesRegex(RealDataGateRejected,'INVALID_SEQUENCE_NAME'):
                stage_mot17(example_zip=a,mot17_labels_zip=b,output=root/'out',sequences=['../../bad'])

if __name__=='__main__':unittest.main()
