"""P3F Markov-equivalence enumeration: assumed skeleton != causal truth."""
import random
import unittest
from cognitum.proto import causal_ambiguity_pb2 as a, causal_discovery_pb2 as d
from cognitum.causal_discovery import run_discovery_frame
from cognitum.causal_ambiguity import run_ambiguity_frame,ambiguity_receipt
from tests.test_c14_p3_discovery import fixture


def case(skeleton='chain',selected=False,collider=False):
    if skeleton=='chain':
        base=fixture(seed=7)
    elif skeleton=='pair':
        r=random.Random(13)
        base=d.DiscoveryRequest(schema_version=1,trace_id='p3f-pair',
            method=d.REFERENCE_PC_STABLE_SKELETON,variable_ids=['X','Y'],
            alpha=0.01,max_conditioning=1,max_tests=80,timeout_ms=3000)
        for _ in range(200):
            x=r.gauss(0,1)
            base.observations.add(values=[x,x+r.gauss(0,0.3)])
    elif skeleton=='triangle':
        r=random.Random(19)
        base=d.DiscoveryRequest(schema_version=1,trace_id='p3f-triangle',
            method=d.REFERENCE_PC_STABLE_SKELETON,variable_ids=['X','Y','Z'],
            alpha=0.01,max_conditioning=1,max_tests=90,timeout_ms=3000)
        for _ in range(400):
            x=r.gauss(0,1)
            y=0.8*x+r.gauss(0,0.6)
            z=0.7*x+0.7*y+r.gauss(0,1.5)
            base.observations.add(values=[x,y,z])
    else:raise ValueError('unknown fixture')
    source_raw=base.SerializeToString(deterministic=True)
    result=run_discovery_frame(source_raw,host_authorized=True,enabled=True)
    got=d.DiscoveryResult.FromString(result)
    assert got.status==d.CANDIDATE_SKELETON_COMPUTED
    req=a.AmbiguityRequest(schema_version=1,trace_id=base.trace_id,source_request=base,
        source_result=result,select_declared_collider_signature=selected,
        max_orientations=128,timeout_ms=3500)
    if collider:req.declared_colliders.add(first=0,middle=1,last=2)
    return req


def evaluate(req,**kw):
    raw=req.SerializeToString(deterministic=True)
    reply=run_ambiguity_frame(raw,**kw)
    return raw,a.AmbiguityResult.FromString(reply),reply

class TestP3FAmbiguity(unittest.TestCase):
    def test_chain_two_equivalence_classes(self):
        raw,got,reply=evaluate(case(),host_authorized=True,enabled=True)
        self.assertEqual(got.status,a.AMBIGUITY_COMPUTED,got.reason_code)
        self.assertEqual(got.orientations_considered,4)
        self.assertEqual(got.acyclic_orientations,4)
        self.assertEqual([x.dag_count for x in got.classes],[3,1])
        self.assertEqual(len(got.classes[0].compelled_arrows_within_class),0)
        self.assertEqual(len(got.classes[1].unshielded_colliders),1)
        self.assertEqual([(e.source,e.target) for e in got.classes[1].compelled_arrows_within_class],[(0,1),(2,1)])
        self.assertTrue(ambiguity_receipt(raw,reply).enumeration_replay)
        self.assertFalse(ambiguity_receipt(raw,reply).causal_orientation_verified)
        self.assertFalse(got.causal_direction_established)
    def test_select_no_collider_class(self):
        _,got,_=evaluate(case(selected=True),host_authorized=True,enabled=True)
        self.assertEqual(got.status,a.AMBIGUITY_COMPUTED)
        self.assertEqual([g.dag_count for g in got.classes],[3])
        self.assertFalse(got.assumed_causal_sufficiency)
    def test_select_collider_class(self):
        _,got,_=evaluate(case(selected=True,collider=True),host_authorized=True,enabled=True)
        self.assertEqual(got.status,a.AMBIGUITY_COMPUTED)
        self.assertEqual([g.dag_count for g in got.classes],[1])
        self.assertEqual(len(got.classes[0].compelled_arrows_within_class),2)
    def test_two_node_bidirectional_ambiguity(self):
        _,got,_=evaluate(case('pair'),host_authorized=True,enabled=True)
        self.assertEqual(got.status,a.AMBIGUITY_COMPUTED)
        self.assertEqual(got.acyclic_orientations,2)
        self.assertEqual([g.dag_count for g in got.classes],[2])
        self.assertFalse(got.classes[0].compelled_arrows_within_class)
    def test_triangle_no_unshielded_colliders(self):
        req=case('triangle')
        skeleton=[(e.first,e.second) for e in d.DiscoveryResult.FromString(req.source_result).undirected_edges]
        self.assertEqual(skeleton,[(0,1),(0,2),(1,2)])
        _,got,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertEqual(got.status,a.AMBIGUITY_COMPUTED)
        self.assertEqual(got.orientations_considered,8)
        self.assertEqual(got.acyclic_orientations,6)
        self.assertEqual([g.dag_count for g in got.classes],[6])
        self.assertEqual(len(got.classes[0].compelled_arrows_within_class),0)
    def test_denied(self):
        self.assertEqual(evaluate(case(),enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_disabled(self):
        self.assertEqual(evaluate(case(),host_authorized=True)[1].reason_code,'AMBIGUITY_DISABLED')
    def test_signature_without_select_rejected(self):
        req=case(collider=True)
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'INVALID_DECLARED_COLLIDER')
    def test_invalid_collider(self):
        req=case(selected=True,collider=True);req.declared_colliders[0].last=1
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,a.AMBIGUITY_REJECTED)
    def test_duplicate_collider(self):
        req=case(selected=True,collider=True)
        req.declared_colliders.add(first=0,middle=1,last=2)
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'DUPLICATE_OR_NONCANONICAL_COLLIDERS')
    def test_capacity_limit(self):
        req=case();req.max_orientations=3
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].reason_code,'ORIENTATION_CAP_TOO_SMALL')
    def test_forged_skeleton(self):
        req=case();got=d.DiscoveryResult.FromString(req.source_result)
        got.undirected_edges[0].second=2
        req.source_result=got.SerializeToString(deterministic=True)
        _,out,_=evaluate(req,host_authorized=True,enabled=True)
        self.assertNotEqual(out.status,a.AMBIGUITY_COMPUTED)
        self.assertFalse(out.classes)
    def test_bad_trace(self):
        req=case();req.trace_id='mismatch'
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,a.AMBIGUITY_REJECTED)
    def test_wrong_reference_method(self):
        req=case();req.source_request.method=d.CAUSAL_LEARN_PC_OPTIONAL
        self.assertEqual(evaluate(req,host_authorized=True,enabled=True)[1].status,a.AMBIGUITY_REJECTED)
    def test_receipt_rejects_forged_compelled_arrow(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.classes[0].compelled_arrows_within_class.add(source=0,target=1)
        self.assertFalse(ambiguity_receipt(raw,got.SerializeToString(deterministic=True)).enumeration_replay)
    def test_receipt_rejects_forged_causality(self):
        raw,got,_=evaluate(case(),host_authorized=True,enabled=True)
        got.causal_direction_established=True
        self.assertFalse(ambiguity_receipt(raw,got.SerializeToString(deterministic=True)).enumeration_replay)
    def test_receipt_rejects_changed_request(self):
        raw,got,reply=evaluate(case(),host_authorized=True,enabled=True)
        req=case();req.timeout_ms+=1
        self.assertFalse(ambiguity_receipt(req.SerializeToString(deterministic=True),reply).enumeration_replay)
    def test_oversized_request(self):
        res=a.AmbiguityResult.FromString(run_ambiguity_frame(b'X'*185001,host_authorized=True,enabled=True))
        self.assertEqual(res.status,a.AMBIGUITY_REJECTED)

if __name__=='__main__': unittest.main()
