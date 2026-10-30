"""P2B: typed, bounded identity hypotheses without trusted IDs or auto updates."""
import unittest
from cognitum import spatial_identity_association as identity
from cognitum import spatial_scene_reference as scene_engine
from cognitum.proto import spatial_scene_pb2 as s
from cognitum.proto import spatial_identity_pb2 as p


def observed(oid, x, *, category='drone', source='sensor_a', tick=1):
    o=s.SceneObject(object_id=oid, category=category, display_name=oid,
                    frame_id='world', observation_source_id=source,
                    last_observed_tick=tick, confidence=0.9, visibility=s.VISIBILITY_VISIBLE)
    o.position_m.x=x;o.rotation_xyzw.w=1
    return o


def seed(items):
    c=s.SceneCommand(schema_version=1,scene_id='scene_x',conversation_id='conv_x',
                     task_id='task_x',trace_id='trace_x',request_id='seed_0')
    for item in items:
        m=c.mutations.add(kind=s.MUTATION_OBSERVE,object_id=item.object_id,
                          tick=item.last_observed_tick)
        m.observed.CopyFrom(item)
    snap,_=scene_engine.apply(None,c,admit=lambda *x:True)
    return snap


def request(snap, observations, *, sigma=0.5, speed=3, cost=9, margin=0.5, k=4):
    r=p.AssociationRequest(schema_version=1,scene_id=snap.scene_id,
                           conversation_id=snap.conversation_id,
                           task_id='task_x',trace_id='trace_p2b',request_id='assoc_1',
                           scene_sha256=identity.digest(snap),measurement_sigma_m=sigma,
                           max_speed_m_per_tick=speed,unmatched_cost=cost,
                           ambiguity_cost_margin=margin,top_k=k)
    for j,(label,x,*extra) in enumerate(observations):
        source=extra[0] if extra else 'sensor_a'
        category=extra[1] if len(extra)>1 else 'drone'
        tick=extra[2] if len(extra)>2 else 2
        obs=r.observations.add(observation_id=label,category=category,
                               source_id=source,frame_id='world',observed_tick=tick)
        obs.position_m.x=x
    return r


class C15P2BIdentity(unittest.TestCase):
    def one(self): return seed([observed('a',0)])
    def two(self): return seed([observed('a',0),observed('b',10)])
    def test_01_one_track_candidate_not_approval(self):
        snap=self.one();result=identity.propose(snap,request(snap,[('obs',0.1)]))
        self.assertEqual(result.decision,p.ASSOCIATION_CANDIDATE_ONLY)
        self.assertEqual(result.hypotheses[0].pairs[0].object_id,'a')
        self.assertFalse(result.grants_authority)
    def test_02_observations_do_not_mutate_canonical_scene(self):
        snap=self.two();original=snap.SerializeToString(deterministic=True)
        identity.propose(snap,request(snap,[('b_obs',10),('a_obs',0)]))
        self.assertEqual(original,snap.SerializeToString(deterministic=True))
    def test_03_near_tie_reports_ambiguous(self):
        snap=seed([observed('a',-0.2),observed('b',0.2)])
        out=identity.propose(snap,request(snap,[('o',0)],sigma=0.5))
        self.assertEqual(out.decision,p.ASSOCIATION_AMBIGUOUS)
        self.assertIn('NEAR_TIED_GLOBAL_ASSIGNMENT',out.warnings)
        self.assertEqual(set(h.pairs[0].object_id for h in out.hypotheses[:2]),{'a','b'})
    def test_04_same_class_swap_not_falsely_certified(self):
        snap=self.two();out=identity.propose(snap,request(snap,[('obs_a',10),('obs_b',0)]))
        self.assertEqual(out.decision,p.ASSOCIATION_AMBIGUOUS)
        self.assertIn('SAME_CLASS_GEOMETRY_CANNOT_PROVE_IDENTITY',out.warnings)
        self.assertEqual({a.object_id for a in out.hypotheses[0].pairs},{'a','b'})
    def test_05_no_gated_edge_is_no_match(self):
        snap=self.one();out=identity.propose(snap,request(snap,[('new',999)]))
        self.assertEqual(out.decision,p.ASSOCIATION_NO_COMPATIBLE_MATCH)
        self.assertEqual(out.hypotheses[0].pairs[0].object_id,'')
    def test_06_score_above_unmatched_prefers_abstention(self):
        snap=self.one();out=identity.propose(snap,request(snap,[('new',2)],sigma=0.1,speed=10))
        self.assertEqual(out.decision,p.ASSOCIATION_NO_COMPATIBLE_MATCH)
    def test_07_source_mismatch_blocks_reassociation(self):
        snap=self.one();out=identity.propose(snap,request(snap,[('obs',0,'sensor_b')]))
        self.assertEqual(out.decision,p.ASSOCIATION_NO_COMPATIBLE_MATCH)
    def test_08_category_mismatch_blocks_reassociation(self):
        snap=self.one();out=identity.propose(snap,request(snap,[('obs',0,'sensor_a','person')]))
        self.assertEqual(out.decision,p.ASSOCIATION_NO_COMPATIBLE_MATCH)
    def test_09_observation_reordering_preserves_assignments(self):
        snap=self.two();r1=request(snap,[('z',10),('a',0)])
        r2=request(snap,[('a',0),('z',10)])
        a=identity.propose(snap,r1);b=identity.propose(snap,r2)
        self.assertEqual([(x.observation_id,x.object_id) for x in a.hypotheses[0].pairs],
                         [(x.observation_id,x.object_id) for x in b.hypotheses[0].pairs])
    def test_10_one_to_one_in_all_hypotheses(self):
        snap=self.two();out=identity.propose(snap,request(snap,[('o1',0),('o2',0.5)]))
        for hyp in out.hypotheses:
            linked=[x.object_id for x in hyp.pairs if x.object_id]
            self.assertEqual(len(linked),len(set(linked)))
    def test_11_tampered_hash_rejected(self):
        snap=self.one();r=request(snap,[('obs',0)]);r.scene_sha256=b'0'*32
        with self.assertRaisesRegex(identity.AssociationRejected,'SCENE_HASH_MISMATCH'):
            identity.propose(snap,r)
    def test_12_other_conversation_rejected(self):
        snap=self.one();r=request(snap,[('obs',0)]);r.conversation_id='other'
        with self.assertRaisesRegex(identity.AssociationRejected,'SCENE_OR_CONVERSATION_SCOPE_MISMATCH'):
            identity.propose(snap,r)
    def test_13_old_observation_rejected(self):
        snap=self.one();r=request(snap,[('obs',0,'sensor_a','drone',1)])
        with self.assertRaisesRegex(identity.AssociationRejected,'STALE_OBSERVATION_TICK'):
            identity.propose(snap,r)
    def test_14_duplicate_observation_rejected(self):
        snap=self.one();r=request(snap,[('x',0),('x',1)])
        with self.assertRaisesRegex(identity.AssociationRejected,'DUPLICATE_OBSERVATION_IDS'):
            identity.propose(snap,r)
    def test_15_nan_noise_rejected(self):
        snap=self.one();r=request(snap,[('obs',0)]);r.measurement_sigma_m=float('nan')
        with self.assertRaisesRegex(identity.AssociationRejected,'INVALID_MEASUREMENT_SCALE'):
            identity.propose(snap,r)
    def test_16_zero_speed_rejected(self):
        snap=self.one();r=request(snap,[('obs',0)]);r.max_speed_m_per_tick=0
        with self.assertRaisesRegex(identity.AssociationRejected,'INVALID_SPEED_BOUND'):
            identity.propose(snap,r)
    def test_17_excessive_observations_rejected(self):
        snap=self.one();r=request(snap,[(f'o{i}',i) for i in range(7)])
        with self.assertRaisesRegex(identity.AssociationRejected,'OBSERVATION_LIMIT'):
            identity.propose(snap,r)
    def test_18_invalid_reference_frame_rejected(self):
        snap=self.one();r=request(snap,[('o',0)]);r.observations[0].frame_id='unknown'
        with self.assertRaisesRegex(identity.AssociationRejected,'INVALID_OBSERVATION_FRAME'):
            identity.propose(snap,r)
    def test_19_hypothesis_tamper_rejected(self):
        snap=self.one();r=request(snap,[('o',0)])
        h=identity.propose(snap,r);h.hypotheses[0].pairs[0].object_id='someone_else'
        self.assertFalse(identity.verify_proposal(snap,r,h))
    def test_20_verifier_replays_exact_output(self):
        snap=self.one();r=request(snap,[('o',0)])
        out=identity.propose(snap,r)
        self.assertTrue(identity.verify_proposal(snap,r,out))
    def test_21_claimed_authority_rejected(self):
        snap=self.one();r=request(snap,[('o',0)])
        out=identity.propose(snap,r);out.grants_authority=True
        self.assertFalse(identity.verify_proposal(snap,r,out))
    def test_22_same_request_id_as_scene_mutation_rejected(self):
        snap=self.one();r=request(snap,[('o',0)]);r.request_id='seed_0'
        with self.assertRaisesRegex(identity.AssociationRejected,'REPLAYED_SCENE_REQUEST'):
            identity.propose(snap,r)
    def test_23_no_active_objects_returns_unmatched(self):
        snap=self.one();c=s.SceneCommand(schema_version=1,scene_id=snap.scene_id,
             conversation_id=snap.conversation_id,task_id='task_x',trace_id='trace_x',
             request_id='delete_1',expected_scene_revision=snap.revision)
        c.mutations.add(kind=s.MUTATION_DELETE,object_id='a',expected_object_version=1,tick=2)
        state,_=scene_engine.apply(snap,c,admit=lambda *x: True)
        out=identity.propose(state,request(state,[('o',0,'sensor_a','drone',3)]))
        self.assertEqual(out.decision,p.ASSOCIATION_NO_COMPATIBLE_MATCH)
    def test_24_occluded_historical_pose_not_proof(self):
        snap=self.two();c=s.SceneCommand(schema_version=1,scene_id=snap.scene_id,
             conversation_id=snap.conversation_id,task_id='task_x',trace_id='trace_x',
             request_id='occ_1',expected_scene_revision=snap.revision)
        c.mutations.add(kind=s.MUTATION_OCCLUDE,object_id='a',expected_object_version=1,tick=2)
        state,_=scene_engine.apply(snap,c,admit=lambda *x:True)
        out=identity.propose(state,request(state,[('o1',0,'sensor_a','drone',3),('o2',10,'sensor_a','drone',3)]))
        self.assertEqual(out.decision,p.ASSOCIATION_AMBIGUOUS)
        self.assertIn('POSITION_ONLY_NO_APPEARANCE_OR_CONTINUOUS_TRAJECTORY',out.warnings)
    def test_25_pose_frame_transform(self):
        snap=self.one();c=s.SceneCommand(schema_version=1,scene_id=snap.scene_id,
             conversation_id=snap.conversation_id,task_id='task_x',trace_id='trace_x',
             request_id='frame_1',expected_scene_revision=snap.revision)
        f=c.add_frames.add(frame_id='cam',parent_frame_id='world');f.translation_m.x=10;f.rotation_xyzw.w=1
        new,_=scene_engine.apply(snap,c,admit=lambda *x:True)
        r=request(new,[('o',-10)]);r.observations[0].frame_id='cam'
        out=identity.propose(new,r)
        self.assertEqual(out.hypotheses[0].pairs[0].object_id,'a')
    def test_26_structural_scores_not_probabilistic_truth(self):
        snap=self.one();out=identity.propose(snap,request(snap,[('o',0)]))
        self.assertAlmostEqual(sum(x.relative_weight for x in out.hypotheses),1)
        self.assertIn('TOP_K_WEIGHTS_ARE_NOT_CALIBRATED_POSTERIORS',out.warnings)
    def test_27_no_tool_or_external_action_in_schema(self):
        fields=p.AssociationHypothesisSet.DESCRIPTOR.fields_by_name
        self.assertFalse({'tool_call','action_grant','authorization'} & set(fields))
    def test_28_geometry_only_kinematics_cannot_claim_true_swap(self):
        snap=self.two();out=identity.propose(snap,request(snap,[('front',0),('back',10)]))
        self.assertEqual(out.decision,p.ASSOCIATION_AMBIGUOUS)
        # The best assignment is not a verified physical track identity.
        self.assertFalse(out.grants_authority)

if __name__=='__main__': unittest.main()
