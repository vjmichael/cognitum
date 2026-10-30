"""P1 additive 2D contract + P2F independent evaluator readiness gates."""
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
from google.protobuf.internal.encoder import _VarintBytes

from cognitum.proto import benchmark_observation_pb2 as pb
from cognitum.spatial_benchmark_observation import (
    ObservationRejected, make_observation, validate, validate_sequence, read_mot_benchmark,
    export_mot_rows, parse_coco_video_uncompressed, validate_frame,
)
from cognitum.spatial_trackeval_bridge import stage_motchallenge, run_trackeval, read_summary


def obs(role=pb.GROUND_TRUTH,**changes):
    d=dict(seq='test1',frame=1,observation_id='o1',role=role,class_id=1,class_label='pedestrian',
      image_width=640,image_height=480,source_bytes=b'fixture bytes',dataset_id='fixture',
      dataset_version='1',source_uri='fixture:///data',box=(10,20,30,40),
      track_id=1 if role!=pb.DETECTION else None,confidence=None if role==pb.GROUND_TRUTH else 0.8)
    d.update(changes)
    return make_observation(**d)

class TestP2FObservation(unittest.TestCase):
    def test_bbox_and_provenance(self):
        o=obs();validate(o)
        self.assertEqual(o.provenance.source_sha256,hashlib.sha256(b'fixture bytes').digest())
        self.assertEqual((o.bbox.x,o.bbox.height),(10,40))
    def test_timestamp_zero_rejected(self):
        with self.assertRaisesRegex(ObservationRejected,'INVALID_TIMESTAMP'):obs(timestamp_ns=0)
    def test_optional_timestamp(self):
        o=obs();self.assertFalse(o.HasField('timestamp_ns'))
        o.timestamp_ns=1;self.assertTrue(o.HasField('timestamp_ns'))
    def test_missing_and_zero_confidence_different(self):
        o=obs(role=pb.GROUND_TRUTH);self.assertFalse(o.HasField('confidence'))
        o.confidence=0;validate(o);self.assertTrue(o.HasField('confidence'))
    def test_zero_confidence_prediction_accepted(self):validate(obs(role=pb.TRACKER_PREDICTION,confidence=0))
    def test_prediction_unknown_confidence_allowed(self):
        o=obs(role=pb.TRACKER_PREDICTION);o.ClearField('confidence')
        validate(o);self.assertFalse(o.HasField('confidence'))
    def test_detection_missing_confidence_rejected(self):
        o=obs(role=pb.DETECTION);o.ClearField('confidence')
        with self.assertRaisesRegex(ObservationRejected,'MISSING_CONFIDENCE'):validate(o)
    def test_missing_track_id_gt_rejected(self):
        o=obs();o.ClearField('track_id')
        with self.assertRaisesRegex(ObservationRejected,'MISSING_TRACK_ID'):validate(o)
    def test_track_id_zero_rejected(self):
        with self.assertRaisesRegex(ObservationRejected,'INVALID_TRACK_ID'):obs(track_id=0)
    def test_detection_no_identity(self):
        with self.assertRaisesRegex(ObservationRejected,'DETECTION_MUST_NOT_HAVE_IDENTITY'):obs(pb.DETECTION,track_id=2)
    def test_unknown_role(self):
        o=obs();o.role=0
        with self.assertRaisesRegex(ObservationRejected,'INVALID_ROLE'):validate(o)
    def test_role_gate(self):
        with self.assertRaisesRegex(ObservationRejected,'INVALID_ROLE'):validate(obs(),expected_role=pb.TRACKER_PREDICTION)
    def test_authority_rejected(self):
        o=obs();o.grants_authority=True
        with self.assertRaisesRegex(ObservationRejected,'INVALID_RESEARCH_CONTRACT'):validate(o)
    def test_unsupported_schema_rejected(self):
        o=obs();o.schema_version=2
        with self.assertRaisesRegex(ObservationRejected,'INVALID_RESEARCH_CONTRACT'):validate(o)
    def test_unknown_wire_field_rejected(self):
        o=obs();wire=o.SerializeToString()+_VarintBytes((1000<<3)|0)+b'\x01'
        z=pb.BenchmarkObservation.FromString(wire)
        with self.assertRaisesRegex(ObservationRejected,'UNKNOWN_PROTOBUF_FIELD'):validate(z)
    def test_bad_source_hash(self):
        o=obs();o.provenance.source_sha256=b'bad'
        with self.assertRaisesRegex(ObservationRejected,'INVALID_PROVENANCE'):validate(o)
    def test_duplicate_observation(self):
        with self.assertRaisesRegex(ObservationRejected,'DUPLICATE_OBSERVATION'):validate_sequence([obs(),obs()])
    def test_duplicate_track_in_frame(self):
        with self.assertRaisesRegex(ObservationRejected,'DUPLICATE_TRACK_ID_IN_FRAME'):validate_sequence([obs(),obs(observation_id='o2')])
    def test_nonmonotonic_frame_time(self):
        with self.assertRaisesRegex(ObservationRejected,'NONMONOTONIC_TIMESTAMP'):
            validate_sequence([obs(timestamp_ns=100),obs(frame=2,observation_id='o2',timestamp_ns=99)])
    def test_different_time_same_frame(self):
        with self.assertRaisesRegex(ObservationRejected,'INCONSISTENT_FRAME_TIMESTAMP'):
            validate_sequence([obs(timestamp_ns=100),obs(observation_id='o2',track_id=2,timestamp_ns=101)])
    def test_multiple_sequences_rejected(self):
        with self.assertRaisesRegex(ObservationRejected,'MULTIPLE_SEQUENCES'):
            validate_sequence([obs(),obs(seq='test2')])
    def test_legal_partly_outside_bbox(self):validate(obs(box=(-20,20,30,40)))
    def test_nan_bbox_rejected(self):
        o=obs();o.bbox.width=float('nan')
        with self.assertRaisesRegex(ObservationRejected,'INVALID_BOX'):validate(o)
    def test_empty_geometry_rejected(self):
        o=obs();o.ClearField('bbox')
        with self.assertRaisesRegex(ObservationRejected,'MISSING_GEOMETRY'):validate(o)
    def test_rle_background_foreground_valid(self):
        o=obs(image_width=2,image_height=2,box=None,mask_counts=[1,3]);validate(o)
        self.assertEqual(sum(o.mask.counts),4)
    def test_rle_starts_foreground(self):validate(obs(image_width=2,image_height=2,box=None,mask_counts=[0,4]))
    def test_rle_total_rejected(self):
        with self.assertRaisesRegex(ObservationRejected,'INVALID_RLE_TOTAL'):obs(image_width=2,image_height=2,box=None,mask_counts=[2,1])
    def test_noncanonical_rle(self):
        with self.assertRaisesRegex(ObservationRejected,'NONCANONICAL_RLE'):obs(image_width=2,image_height=2,box=None,mask_counts=[1,0,3])
    def test_ignore_only_gt(self):
        with self.assertRaisesRegex(ObservationRejected,'IGNORE_ONLY_IN_GROUND_TRUTH'):obs(pb.TRACKER_PREDICTION,ignore=True)
    def test_gt_visibility_preserved_when_supplied(self):
        self.assertIn(",1,0.25,-1",export_mot_rows([obs(visibility=.25)],role=pb.GROUND_TRUTH))
    def test_visibility_never_promoted_to_prediction(self):
        with self.assertRaisesRegex(ObservationRejected,"INVALID_GT_VISIBILITY"):
            obs(pb.TRACKER_PREDICTION,visibility=.5)
    def test_mot_export_gt(self):
        s=export_mot_rows([obs()],role=pb.GROUND_TRUTH)
        self.assertEqual(s.strip(),'1,1,10.0,20.0,30.0,40.0,1,1,-1,-1')
    def test_mot_export_mask_rejected(self):
        with self.assertRaisesRegex(ObservationRejected,'MOTS_MASK_CANNOT_BE_DISCARDED'):
            export_mot_rows([obs(image_width=2,image_height=2,mask_counts=[4])],role=pb.GROUND_TRUTH)
    def test_mot_export_role_leak_rejected(self):
        with self.assertRaisesRegex(ObservationRejected,'INVALID_ROLE'):
            export_mot_rows([obs()],role=pb.TRACKER_PREDICTION)
    def test_mot_parser_modern(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gt.txt';p.write_text('1,1,10,20,30,40,1,1,0.8,-1\n')
            got=read_mot_benchmark(p,seq='test1',role=pb.GROUND_TRUTH,width=640,height=480,
                 dataset_id='fixture',dataset_version='1',source_uri='fixture://mot')
            self.assertEqual(len(got),1)
            self.assertEqual(got[0].track_id,1)
            self.assertAlmostEqual(got[0].visibility,.8)
    def test_mot_legacy_gate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gt.txt';p.write_text('1,1,-20,20,30,40,1,-1,-1,-1\n')
            args=dict(seq='test1',role=pb.GROUND_TRUTH,width=640,height=480,dataset_id='fixture',dataset_version='1',source_uri='fixture://mot')
            with self.assertRaisesRegex(ObservationRejected,'INVALID_MODERN_GT'):
                read_mot_benchmark(p,**args)
            got=read_mot_benchmark(p,legacy_gt=True,**args)
            self.assertEqual(got[0].bbox.x,-20)
    def test_mot_prediction_minus_one_confidence_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.txt';p.write_text('1,500,10,20,30,40,-1,-1,-1,-1\n')
            got=read_mot_benchmark(p,seq='test1',role=pb.TRACKER_PREDICTION,width=640,height=480,dataset_id='fixture',dataset_version='1',source_uri='fixture://pred')
            self.assertFalse(got[0].HasField('confidence'))
            self.assertIn(',-1,-1,-1,-1',export_mot_rows(got,role=pb.TRACKER_PREDICTION))
    def test_frame_contract(self):
        fr=pb.BenchmarkFrame(schema_version=1,sequence_id='test1',frame_index=1,observations=[obs()])
        self.assertEqual(validate_frame(fr),1)
        fr.frame_index=2
        with self.assertRaisesRegex(ObservationRejected,'FRAME_OBSERVATION_MISMATCH'):validate_frame(fr)
    def test_mot_det_identity_stripped(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'det.txt';p.write_text('1,500,10,20,30,40,0.2,-1,-1,-1\n')
            got=read_mot_benchmark(p,seq='test1',role=pb.DETECTION,width=640,height=480,dataset_id='fixture',dataset_version='1',source_uri='fixture://det')
            self.assertFalse(got[0].HasField('track_id'))
    def test_mot_missing_columns_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.txt';p.write_text('1,1,0,0,10,10,1\n')
            with self.assertRaisesRegex(ObservationRejected,'MOT_EXPECTED_TEN_COLUMNS'):
                read_mot_benchmark(p,seq='test1',role=pb.GROUND_TRUTH,width=100,height=100,dataset_id='fixture',dataset_version='1',source_uri='fixture://mot')
    def test_coco_uncompressed(self):
        payload={'images':[{'id':9,'video_id':2,'frame_index':1,'width':2,'height':2,'timestamp_ns':100}],
           'categories':[{'id':4,'name':'drone'}],
           'annotations':[{'id':1,'image_id':9,'category_id':4,'track_id':7,'bbox':[0,0,2,2],
               'segmentation':{'size':[2,2],'counts':[1,3]}}]}
        got=parse_coco_video_uncompressed(payload,seq='seq1',dataset_id='fixture',dataset_version='1',source_uri='fixture://coco',role=pb.GROUND_TRUTH)
        self.assertEqual(got[0].track_id,7)
        self.assertEqual(got[0].mask.height,2)
        self.assertEqual(got[0].timestamp_ns,100)
    def test_coco_compressed_unsupported(self):
        payload={'images':[{'id':9,'video_id':2,'frame_index':1,'width':2,'height':2}],
          'annotations':[{'id':1,'image_id':9,'category_id':1,'track_id':1,'segmentation':{'size':[2,2],'counts':'coded'}}]}
        with self.assertRaisesRegex(ObservationRejected,'COMPRESSED_OR_INVALID_COCO_RLE'):
            parse_coco_video_uncompressed(payload,seq='seq1',dataset_id='fixture',dataset_version='1',source_uri='fixture://coco',role=pb.GROUND_TRUTH)
    def test_coco_no_video_id_rejected(self):
        payload={'images':[{'id':9,'frame_index':1,'width':2,'height':2}],'annotations':[]}
        with self.assertRaisesRegex(ObservationRejected,'IMAGE_FRAME_METADATA_REQUIRED'):
            parse_coco_video_uncompressed(payload,seq='seq1',dataset_id='fixture',dataset_version='1',source_uri='fixture://coco',role=pb.GROUND_TRUTH)
    def test_coco_prediction_without_id_rejected(self):
        payload={'images':[{'id':9,'video_id':2,'frame_index':1,'width':2,'height':2}],
          'annotations':[{'id':1,'image_id':9,'category_id':1,'score':.5,'bbox':[0,0,1,1]}]}
        with self.assertRaisesRegex(ObservationRejected,'COCO_TRACK_ID_REQUIRED'):
            parse_coco_video_uncompressed(payload,seq='seq1',dataset_id='fixture',dataset_version='1',source_uri='fixture://coco',role=pb.TRACKER_PREDICTION)

class TestTrackEvalBridge(unittest.TestCase):
    def test_staging_generates_expected_structure(self):
        with tempfile.TemporaryDirectory() as d:
            m=stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION)],root=d,sequence='TUD-Campus',tracker='P2F')
            self.assertTrue((Path(d)/'gt/MOT17-train/TUD-Campus/gt/gt.txt').is_file())
            self.assertTrue((Path(d)/'gt/MOT17-train/TUD-Campus/seqinfo.ini').is_file())
            self.assertTrue((Path(d)/'gt/seqmaps/MOT17-train.txt').is_file())
            self.assertTrue((Path(d)/'trackers/MOT17-train/P2F/data/TUD-Campus.txt').is_file())
            self.assertTrue(m['data_roles_separated'])
            self.assertEqual(len(m['file_sha256']),4)
    def test_gt_prediction_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'INPUT_SEQUENCE_MISMATCH'):
                stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION,seq='other')],root=d)
    def test_nonpedestrian_requires_other_dataset_evaluator(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'MOT_PEDESTRIAN_ONLY_CLASS_REQUIRED'):
                stage_motchallenge([obs(class_id=2,class_label='drone')],[obs(pb.TRACKER_PREDICTION,class_id=2,class_label='drone')],root=d)
    def test_masks_require_mots(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'MOTS_MASK_CANNOT_BE_DISCARDED'):
                stage_motchallenge([obs(mask_counts=[640*480])],[obs(pb.TRACKER_PREDICTION)],root=d)
    def test_incorrect_input_role_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'INVALID_ROLE'):
                stage_motchallenge([obs()],[obs()],root=d)
    def test_engine_absent_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            m=stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION)],root=d)
            self.assertEqual(run_trackeval(m)['status'],'blocked_external_engine_missing')
            self.assertFalse(run_trackeval(m)['official_evaluator_ran'])
            self.assertEqual(run_trackeval(m,trackeval_root=Path(d)/'missing')['status'],'blocked_external_engine_missing')

    def test_frame_resolution_mismatch_blocks_staging(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'INPUT_FRAME_METADATA_MISMATCH'):
                stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION,image_width=1280)],root=d)
    def test_dataset_mismatch_blocks_staging(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'INPUT_DATASET_PROVENANCE_MISMATCH'):
                stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION,dataset_version='other')],root=d)
    def test_camera_frame_mismatch_blocks_staging(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'INPUT_FRAME_METADATA_MISMATCH'):
                stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION,camera_frame='camera1')],root=d)
    def test_timestamp_mismatch_blocks_staging(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ObservationRejected,'INPUT_FRAME_TIMESTAMP_MISMATCH'):
                stage_motchallenge([obs(timestamp_ns=100)],[obs(pb.TRACKER_PREDICTION,timestamp_ns=99)],root=d)
    def test_summary_rejects_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pedestrian_summary.txt'
            p.write_text('HOTA MOTA IDF1\nNaN 20 50\n')
            with self.assertRaisesRegex(ObservationRejected,'TRACK_EVAL_NONFINITE_SCORE'):read_summary(p)
    def test_staged_inputs_modified_before_engine_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            m=stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION)],root=d)
            p=Path(d)/'gt/MOT17-train/CognitumPilot/gt/gt.txt'
            p.write_text('altered\n')
            result=run_trackeval(m,trackeval_root=d)
            self.assertEqual(result['status'],'blocked_staging_integrity_failure')
            self.assertFalse(result['official_evaluator_ran'])
    def test_stale_summary_blocked_even_if_external_files_present(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            m=stage_motchallenge([obs()],[obs(pb.TRACKER_PREDICTION)],root=base/'stage')
            checkout=base/'engine';(checkout/'scripts').mkdir(parents=True)
            (checkout/'trackeval/metrics').mkdir(parents=True)
            (checkout/'scripts/run_mot_challenge.py').write_text('# pinned stub; must not run\n')
            (checkout/'trackeval/metrics/hota.py').write_text('# file availability only\n')
            summary=Path(m['trackers_root'])/'MOT17-train/CognitumCandidate/pedestrian_summary.txt'
            summary.write_text('HOTA MOTA IDF1\n100 100 100\n')
            result=run_trackeval(m,trackeval_root=checkout)
            self.assertEqual(result['status'],'blocked_stale_summary_file')
            self.assertFalse(result['official_evaluator_ran'])
    def test_parse_realistic_summary(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pedestrian_summary.txt';p.write_text('HOTA DetA AssA MOTA IDF1 IDSW\n53.1 60.2 47.0 42.3 49.2 12\n')
            scores=read_summary(p)
            self.assertEqual(scores['IDSW'],12)
            self.assertEqual(scores['HOTA'],53.1)
    def test_bad_summary_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('MOTA IDF1\n30 40\n')
            with self.assertRaisesRegex(ObservationRejected,'TRACK_EVAL_INCOMPLETE_METRICS'):read_summary(p)

if __name__=='__main__':unittest.main()
