import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import io
from cognitum import spatial_p2m_pipeline as p
from cognitum.proto import spatial_appearance_pipeline_pb2 as pb
from cognitum.proto import spatial_composition_pb2 as t2
from cognitum import spatial_composition


def picture(value=70):
    im=Image.new('RGB',(64,48),(value,20,120))
    b=io.BytesIO();im.save(b,'PNG');return b.getvalue()


def request(n=2):
    r=pb.P2MFeatureRequest(schema_version=1,conversation_id='thread.1',
          sequence_id='MOT17-02-DPM',request_id='req.1',research_only=True)
    r.model.CopyFrom(p.histogram_model())
    for i in range(1,n+1):
        f=r.frames.add(frame=i,encoded_image=picture(60+i),source_ref=f'frame.{i}')
        f.boxes.add(x=8+i,y=4,w=22,h=24)
    return r


class P2MTests(unittest.TestCase):
    def test_typed_feature_request_binds_frame_and_scope(self):
        r=request();v=p.extract(r)
        self.assertEqual(len(v.descriptors),2)
        self.assertEqual(v.descriptors[0].conversation_id,'thread.1')
        self.assertEqual(v.descriptors[0].frame_sha256,hashlib.sha256(r.frames[0].encoded_image).digest())
        self.assertTrue(p.check_response(r,v))
        self.assertNotIn(r.frames[0].encoded_image, v.SerializeToString())
        self.assertFalse(v.grants_authority)

    def test_full_t1_t2_t3_research_handoff(self):
        r=request(3)
        resp,handoff,count=p.research_pipeline(r)
        self.assertEqual(len(handoff.candidates),3)
        self.assertEqual(count['input_boxes'],3)
        self.assertTrue(handoff.t1_identity_candidate_only)
        self.assertTrue(handoff.t3_projection_blocked_without_calibration)
        self.assertTrue(handoff.canonical_scene_mutation_blocked)
        self.assertFalse(handoff.grants_authority)
        nodes,parents,_,_=spatial_composition.validate(handoff.t2_hypothetical_graph)
        self.assertEqual(len(nodes),1);self.assertEqual(len(parents),0)
        # T2 explicitly excludes hypothetical identity nodes from the default view.
        query=t2.StructureQuery(schema_version=1,graph_id=handoff.t2_hypothetical_graph.graph_id,
             conversation_id='thread.1',target_id=next(iter(nodes)))
        out=spatial_composition.query(handoff.t2_hypothetical_graph,query)
        self.assertIn('HYPOTHETICAL_TARGET_NOT_ADMITTED',out.warnings)
        self.assertEqual(len(handoff.t2_hypothetical_graph.edges),0)

    def test_conversation_or_image_tampering(self):
        r=request();resp=p.extract(r)
        for mutation in ('conversation','pixels','box','descriptor'):
            altered=copy.deepcopy(r);res=copy.deepcopy(resp)
            if mutation=='conversation':altered.conversation_id='other'
            if mutation=='pixels':altered.frames[0].encoded_image=picture(12)
            if mutation=='box':altered.frames[0].boxes[0].x=12
            if mutation=='descriptor':res.descriptors[0].vector[0]+=0.15
            with self.subTest(mutation=mutation),self.assertRaises(p.P2MRejected):
                p.check_response(altered,res)

    def test_model_loading_declared_but_external_execution_blocked(self):
        m=p.histogram_model();m.backend=pb.P2M_EXTERNAL_LEARNED_DISABLED
        m.model_id='osnet_x1_0';m.weights_sha256=hashlib.sha256(b'weights').digest()
        self.assertEqual(p.inspect_model(m)['status'],'blocked_external_weights_missing')
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'weights.bin';path.write_bytes(b'weights')
            assert p.inspect_model(m,weights_path=path)['weights_digest_verified']
            path.write_bytes(b'tampered')
            with self.assertRaisesRegex(p.P2MRejected,'WEIGHT_DIGEST_MISMATCH'):
                p.inspect_model(m,weights_path=path)
        r=request();r.model.CopyFrom(m)
        with self.assertRaisesRegex(p.P2MRejected,'EXTERNAL_EXECUTION_DISABLED'):
            p.extract(r)

    def test_undocumented_or_unpinned_model_rejected(self):
        r=request();r.model.model_id='wrong'
        with self.assertRaisesRegex(p.P2MRejected,'UNPINNED_HISTOGRAM_MODEL'):p.extract(r)
        r=request();r.model.grants_authority=True
        with self.assertRaises(p.P2MRejected):p.extract(r)

    def test_limits_fail_closed_and_no_identity_overlap(self):
        r=request(2)
        r.frames[0].boxes.add(x=24,y=4,w=22,h=24)
        resp=p.extract(r)
        with self.assertRaisesRegex(p.P2MRejected,'ASSIGNMENT_SET_MISMATCH'):
            p.integration_handoff(r,resp,{(1,0):1,(2,0):1})
        with self.assertRaisesRegex(p.P2MRejected,'INVALID_CANDIDATE_LABELS'):
            p.integration_handoff(r,resp,{(1,0):1,(1,1):1,(2,0):1})
        r=request(5)
        with self.assertRaisesRegex(p.P2MRejected,'FRAME_BATCH_LIMIT'):p.extract(r)
        r=request(2);r.frames[0].boxes[0].w=float('nan')
        with self.assertRaisesRegex(p.P2MRejected,'INVALID_IMAGE_BOUND_BOX'):p.extract(r)
        r=request(2);r.frames[0].encoded_image=b'not-an-image'
        with self.assertRaisesRegex(p.P2MRejected,'UNSUPPORTED_IMAGE_FORMAT'):p.extract(r)

    def test_unknown_protobuf_fields_rejected(self):
        r=request()
        raw=r.SerializeToString()+b'\xc0\x3e\x01'
        alt=pb.P2MFeatureRequest.FromString(raw)
        with self.assertRaisesRegex(p.P2MRejected,'INVALID_REQUEST'):p.extract(alt)

    def test_failed_calibration_is_not_hidden(self):
        r=request();resp=p.extract(r)
        handoff=p.integration_handoff(r,resp,{(1,0):5,(2,0):5})
        self.assertIn('T3_REQUIRES_DEPTH_AND_CAMERA_CALIBRATION',handoff.warnings)
        self.assertEqual(handoff.t2_hypothetical_graph.nodes[0].evidence,t2.EVIDENCE_HYPOTHETICAL)

    def test_local_frame_directory_safe_loader(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);(folder/'000001.jpg').write_bytes(picture())
            self.assertEqual(p.load_named_frames(folder,[1])[1],picture())
            with self.assertRaisesRegex(p.P2MRejected,'TRAINING_FRAME_UNAVAILABLE'):
                p.load_named_frames(folder,[2])
            (folder/'000002.jpg').symlink_to(folder/'000001.jpg')
            with self.assertRaisesRegex(p.P2MRejected,'TRAINING_FRAME_UNAVAILABLE'):
                p.load_named_frames(folder,[2])

    def test_deterministic_result_binary(self):
        r=request()
        a,b=p.research_pipeline(r),p.research_pipeline(r)
        self.assertEqual(a[0].SerializeToString(deterministic=True),b[0].SerializeToString(deterministic=True))
        self.assertEqual(a[1].SerializeToString(deterministic=True),b[1].SerializeToString(deterministic=True))

if __name__=='__main__':unittest.main()


def test_request_builder_image_frame_binding():
    from cognitum.spatial_p2k_dense_identity import Detection
    req=p.build_request_from_frames(conversation_id='chat.1',sequence_id='seq_1',
        request_id='run.1',image_bytes={1:picture(10)},
        boxes={1:[Detection(1,8,8,20,20)]})
    assert p.extract(req).descriptors[0].conversation_id=='chat.1'


def test_no_fabricated_detector_observation_from_frame_without_boxes():
    from cognitum.spatial_p2k_dense_identity import Detection
    import pytest
    with pytest.raises(p.P2MRejected,match='INVALID_FRAME_BATCH'):
        p.build_request_from_frames(conversation_id='chat.1',sequence_id='seq_1',
            request_id='run.1',image_bytes={1:picture()},boxes={1:[]})


def test_reject_decoded_image_bomb_before_full_decode():
    import pytest
    im=Image.new('RGB',(4096,4096),(10,10,10));out=io.BytesIO();im.save(out,'PNG')
    r=request(1);r.frames[0].encoded_image=out.getvalue()
    with pytest.raises(p.P2MRejected,match='DECODED_PIXEL_LIMIT'):
        p.extract(r)


def test_benchmark_backlog_is_preserved_and_deferred():
    import json
    b=json.loads((Path(__file__).resolve().parents[1]/'docs/components/spatial/C15-benchmark-backlog-v1.json').read_text())
    assert len(b['deferred_experiments'])==6
    assert all(x['status'].startswith('deferred_') for x in b['deferred_experiments'])
    assert b['completed_reference_checkpoints'][1]['metrics_0_to_100']['CognitumP2KVelocity']['IDSW']==186
    assert b['completed_reference_checkpoints'][1]['status']=='measured_negative_research_result'


def test_reproducible_smoke_has_no_fake_external_metrics():
    from tools.run_c15_p2m_interface_smoke import run
    a,b=run(),run()
    assert a==b
    assert a['status']=='synthetic_interface_smoke_passed'
    assert a['t3_projection_blocked'] and a['t2_edges']==0
    assert a['real_video_metrics'] is None
