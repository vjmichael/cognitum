"""P2U: dynamic/static separation, fresh-evidence, replay and safety invariants."""
import hashlib
import unittest

from cognitum.proto import spatial_dynamic_scene_mapping_pb2 as p
from cognitum.proto import spatial_volume_pb2 as v
from cognitum.spatial_dynamic_scene_mapping import map_scene, verify, DynamicSceneRejected
from cognitum.spatial_volume import classify
from tests.test_c15_t3_p2t_object_aware_volume import fixture, OLD, NEW


def digest(m):
    return hashlib.sha256(m.SerializeToString(deterministic=True)).digest()


def shifted(base, offset=100):
    """Independent synthetic capture window, same declared object, fresh frames."""
    q = type(base)();q.CopyFrom(base)
    for capture in q.temporal_request.captures:
        d = capture.depth
        d.capture_id = f'{d.capture_id}-epoch{offset}'
        d.evaluation_tick += offset
        for px in d.pixels:
            px.tick += offset
            px.depth_frame_sha256 = hashlib.sha256(px.depth_frame_sha256 + str(offset).encode()).digest()
    q.temporal_request.evaluation_tick += offset
    for tr in q.tracks:
        for sm in tr.samples:
            sm.capture_id += f'-epoch{offset}'
            sm.tick += offset
            sm.depth_frame_sha256 = hashlib.sha256(sm.depth_frame_sha256 + str(offset).encode()).digest()
    for obj in q.scene.objects:
        obj.last_observed_tick += offset
    q.scene.revision += 1
    q.scene_sha256 = digest(q.scene)
    return q


def request():
    q = p.P2UDynamicSceneRequest(schema_version=1,conversation_id='chat',volume_id='vox',
        min_motion_windows=2,min_stationary_windows=2,dynamic_hold_ticks=25,
        max_object_gap_ticks=30,research_only=True)
    a=fixture()
    q.windows.add().CopyFrom(a)
    q.windows.add().CopyFrom(shifted(a))
    return q


def get_cell(out, xyz):
    return next(x for x in out.cells if (x.x,x.y,x.z)==xyz)

class DynamicMappingTests(unittest.TestCase):
    def rejected(self,req,fragment):
        with self.assertRaises(DynamicSceneRejected) as err:map_scene(req)
        self.assertIn(fragment,str(err.exception))

    def test_fresh_motion_persists_and_unmeasured(self):
        q=request(); result=map_scene(q)
        self.assertEqual(result.unique_capture_count,10)
        self.assertEqual(len(result.p2t_result_sha256),2)
        self.assertEqual(len(result.objects),1)
        obj=result.objects[0]
        self.assertEqual((obj.object_id,obj.state,obj.distinct_motion_windows,obj.distinct_motion_links),
                         ('moving1',p.P2U_PERSISTENT,2,2))
        for xyz in (OLD,NEW):
            c=get_cell(result,xyz)
            self.assertEqual(c.state,p.P2U_DYNAMIC_HYPOTHESIS)
            self.assertFalse(c.static_handoff_allowed)
        self.assertTrue(result.stationary_hypothetical_volume.research_only)
        self.assertFalse(result.stationary_hypothetical_volume.grants_authority)
        self.assertTrue(all(e.kind in (v.VOLUME_PREDICTED_FREE,v.VOLUME_PREDICTED_OCCUPIED)
                         for e in result.stationary_hypothetical_volume.evidence))
        self.assertTrue(all(c.state==v.CELL_UNKNOWN for c in classify(result.stationary_hypothetical_volume).cells))
        self.assertTrue(verify(q,result))

    def test_static_handoff_requires_two_windows(self):
        out=map_scene(request())
        static=[c for c in out.cells if c.state==p.P2U_STATIC_HYPOTHESIS]
        self.assertGreater(len(static),0)
        self.assertTrue(all(c.consecutive_static_windows>=2 and c.static_handoff_allowed for c in static))
        selected={(e.x,e.y,e.z) for e in out.stationary_hypothetical_volume.evidence}
        self.assertEqual(selected,{(c.x,c.y,c.z) for c in static})

    def test_repeat_window_does_not_count_motion_again(self):
        q=request();a=q.windows[0]
        again=type(a)();again.CopyFrom(a)
        again.temporal_request.evaluation_tick=60
        # Extend repeated window by one genuine capture; old motion is not new.
        capture=again.temporal_request.captures.add()
        capture.CopyFrom(again.temporal_request.captures[-2])
        capture.depth.capture_id='capture60'
        capture.depth.evaluation_tick=60
        for px in capture.depth.pixels:
            px.tick=60
            px.depth_frame_sha256=hashlib.sha256(b'frame:60').digest()
        q.windows[1].CopyFrom(again)
        out=map_scene(q)
        self.assertEqual(out.unique_capture_count,6)
        self.assertEqual(out.objects[0].distinct_motion_links,1)
        self.assertEqual(out.objects[0].distinct_motion_windows,1)
        self.assertEqual(out.objects[0].state,p.P2U_TENTATIVE)
        self.assertEqual(get_cell(out,OLD).state,p.P2U_RECENTLY_DYNAMIC)

    def test_different_capture_same_frame_rejected(self):
        q=request()
        q.windows[1].temporal_request.captures[0].depth.pixels[0].depth_frame_sha256=(
            q.windows[0].temporal_request.captures[0].depth.pixels[0].depth_frame_sha256)
        q.windows[1].temporal_request.captures[0].depth.pixels[1].depth_frame_sha256=(
            q.windows[0].temporal_request.captures[0].depth.pixels[0].depth_frame_sha256)
        self.rejected(q,'FRAME_RELABELED_OR_REPLAYED')

    def test_old_capture_redefined_rejected(self):
        q=request()
        capture=q.windows[0].temporal_request.captures[0]
        first=q.windows[1].temporal_request.captures[0]
        first.CopyFrom(capture)
        first.assumed_within_capture_rho=.99
        self.rejected(q,'CAPTURE_REDEFINED')

    def test_cross_conversation_and_volume_rejected(self):
        q=request();q.windows[1].conversation_id='other';self.rejected(q,'CROSS_SCOPE_P2T_WINDOW')
        q=request();q.windows[0].volume_id='other';self.rejected(q,'CROSS_SCOPE_P2T_WINDOW')

    def test_scene_namespace_change_rejected(self):
        q=request();q.windows[1].scene.scene_id='other'
        q.windows[1].scene_sha256=digest(q.windows[1].scene)
        self.rejected(q,'SCENE_ID_CHANGED')

    def test_decreasing_tick_rejected(self):
        q=request();q.windows.reverse();self.rejected(q,'NONMONOTONIC_WINDOW_TICK')

    def test_invalid_policies(self):
        q=request();q.min_stationary_windows=1;self.rejected(q,'INVALID_P2U_POLICY')
        q=request();q.min_motion_windows=5;self.rejected(q,'IMPOSSIBLE_P2U_POLICY')
        q=request();q.dynamic_hold_ticks=0;self.rejected(q,'INVALID_P2U_POLICY')

    def test_wrong_schema_unknown_fields_and_authority(self):
        q=request();q.grants_authority=True;self.rejected(q,'INVALID_P2U_CONTRACT')
        q=request();q.schema_version=9;self.rejected(q,'INVALID_P2U_CONTRACT')
        q=request();bad=p.P2UDynamicSceneRequest.FromString(q.SerializeToString()+b'\x98\x06\x01')
        self.rejected(bad,'INVALID_P2U_CONTRACT')

    def test_replay_tampering(self):
        q=request();out=map_scene(q)
        out.cells[0].static_handoff_allowed=not out.cells[0].static_handoff_allowed
        with self.assertRaisesRegex(DynamicSceneRejected,'P2U_REPLAY_MISMATCH'):verify(q,out)
        out=map_scene(q);out.objects[0].state=p.P2U_TENTATIVE
        with self.assertRaisesRegex(DynamicSceneRejected,'P2U_REPLAY_MISMATCH'):verify(q,out)

    def test_no_static_volume_mutation_of_p2t(self):
        from cognitum.spatial_object_aware_volume import analyze
        q=request(); snapshot=analyze(q.windows[-1])
        baseline=snapshot.SerializeToString(deterministic=True)
        map_scene(q)
        self.assertEqual(baseline,analyze(q.windows[-1]).SerializeToString(deterministic=True))

    def test_disappearing_object_becomes_dormant_then_retired(self):
        for offset, expected in ((130,p.P2U_DORMANT),(300,p.P2U_RETIRED)):
            q=request()
            third=shifted(q.windows[0],offset)
            third.tracks[0].object_id='new_object'
            third.scene.objects[0].object_id='new_object'
            third.scene_sha256=digest(third.scene)
            q.windows.add().CopyFrom(third)
            out=map_scene(q)
            obj={x.object_id:x for x in out.objects}
            self.assertEqual(obj['moving1'].state,expected)
            self.assertEqual(obj['new_object'].state,p.P2U_TENTATIVE)
            self.assertFalse(out.grants_authority)

    def test_output_order_and_hash_deterministic(self):
        q=request();a=map_scene(q);b=map_scene(q)
        self.assertEqual(a.SerializeToString(deterministic=True),
                         b.SerializeToString(deterministic=True))
        self.assertEqual([tuple((c.x,c.y,c.z)) for c in a.cells],
                         sorted((c.x,c.y,c.z) for c in a.cells))
        self.assertEqual(len(a.request_sha256),32)
        self.assertTrue(all(len(h)==32 for h in a.p2t_result_sha256))

    def test_no_measured_evidence_from_p2u(self):
        q=request();out=map_scene(q)
        from cognitum.spatial_structural_audit import audit
        from cognitum.proto import spatial_structural_audit_pb2 as ap
        from tests.test_c15_t2_composition import fixture as graph_fixture
        graph=graph_fixture();graph.conversation_id='chat'
        inp=ap.StructuralAuditRequest(schema_version=1,conversation_id='chat',graph_id=graph.graph_id,
            volume_id='vox',research_only=True)
        claim=inp.claims.add(claim_id='some_wall',node_id='wall',source_ref='provisional',expected=ap.SPATIAL_EXPECT_OCCUPIED)
        claim.box.min_x=claim.box.max_x=OLD[0]
        claim.box.min_y=claim.box.max_y=OLD[1]
        claim.box.min_z=claim.box.max_z=OLD[2]
        result=audit(graph,out.stationary_hypothetical_volume,inp)
        self.assertEqual(result.audits[0].state,ap.SPATIAL_AUDIT_INDETERMINATE)

if __name__=='__main__':unittest.main()
