"""C14 P3B: PC-stable reference candidate undirected skeleton only."""
import math
import random
import unittest
from cognitum.proto import causal_discovery_pb2 as d
from cognitum.causal_discovery import (run_discovery_frame,verify_discovery_result,
                                        discovery_receipt,discovery_audit)

def fixture(seed=42):
    r=random.Random(seed)
    req=d.DiscoveryRequest(schema_version=1,trace_id='c14-p3',
        method=d.REFERENCE_PC_STABLE_SKELETON,variable_ids=['X','Y','Z'],alpha=0.01,
        max_conditioning=1,max_tests=100,timeout_ms=3000)
    for _ in range(250):
        x=r.gauss(0,1); y=x+r.gauss(0,.25); z=y+r.gauss(0,.25)
        req.observations.add(values=[x,y,z])
    return req

def run(req,**kwargs):
    raw=req.SerializeToString(deterministic=True)
    reply=run_discovery_frame(raw,**kwargs)
    return raw,d.DiscoveryResult.FromString(reply),reply

class TestC14P3Discovery(unittest.TestCase):
    def test_undirected_chain_candidate(self):
        raw,res,reply=run(fixture(),host_authorized=True,enabled=True)
        self.assertEqual(res.status,d.CANDIDATE_SKELETON_COMPUTED)
        self.assertFalse(res.orientations_inferred)
        self.assertEqual([(e.first,e.second) for e in res.undirected_edges],[(0,1),(1,2)])
        self.assertEqual([(e.first,e.second,tuple(e.conditioned_on)) for e in res.separations],[(0,2,(1,))])
        self.assertGreater(float(res.separations[0].independence_p_value),.01)
        self.assertTrue(verify_discovery_result(raw,reply))
        receipt=discovery_receipt(raw,reply)
        self.assertTrue(receipt.deterministic_replay_verified)
        self.assertFalse(receipt.causal_structure_verified)
        audit=discovery_audit(raw,reply)
        self.assertEqual(audit.trace_id,'c14-p3')
    def test_host_denied(self):
        self.assertEqual(run(fixture(),enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_disabled_by_default(self):
        self.assertEqual(run(fixture(),host_authorized=True)[1].reason_code,'DISCOVERY_DISABLED')
    def test_optional_causal_learn_unavailable(self):
        req=fixture();req.method=d.CAUSAL_LEARN_PC_OPTIONAL
        self.assertEqual(run(req,host_authorized=True,enabled=True)[1].status,d.DISCOVERY_BACKEND_UNAVAILABLE)
    def test_test_budget_no_partial_graph(self):
        req=fixture();req.max_tests=1
        res=run(req,host_authorized=True,enabled=True)[1]
        self.assertEqual(res.status,d.DISCOVERY_RESOURCE_LIMIT)
        self.assertFalse(res.undirected_edges)
    def test_invalid_alpha(self):
        req=fixture();req.alpha=0.8
        self.assertEqual(run(req,host_authorized=True,enabled=True)[1].status,d.DISCOVERY_REJECTED)
    def test_duplicate_variables(self):
        req=fixture();req.variable_ids[2]='X'
        self.assertEqual(run(req,host_authorized=True,enabled=True)[1].status,d.DISCOVERY_REJECTED)
    def test_nonfinite_data(self):
        req=fixture();req.observations[0].values[0]=float('nan')
        self.assertEqual(run(req,host_authorized=True,enabled=True)[1].status,d.DISCOVERY_REJECTED)
    def test_wrong_column_count(self):
        req=fixture();req.observations[0].values.pop()
        self.assertEqual(run(req,host_authorized=True,enabled=True)[1].status,d.DISCOVERY_REJECTED)
    def test_constant_column(self):
        req=fixture()
        for row in req.observations:row.values[2]=1
        self.assertEqual(run(req,host_authorized=True,enabled=True)[1].status,d.DISCOVERY_INCONCLUSIVE)
    def test_no_orientations_claimed(self):
        req=fixture()
        _,res,_=run(req,host_authorized=True,enabled=True)
        self.assertFalse(res.orientations_inferred)
        self.assertIn('UNTESTED',res.assumptions)
    def test_wrong_edge_fails_replay(self):
        raw,res,_=run(fixture(),host_authorized=True,enabled=True)
        res.undirected_edges[0].second=2
        self.assertFalse(verify_discovery_result(raw,res.SerializeToString(deterministic=True)))
    def test_forged_causal_orientation_fails_replay(self):
        raw,res,_=run(fixture(),host_authorized=True,enabled=True)
        res.orientations_inferred=True
        self.assertFalse(verify_discovery_result(raw,res.SerializeToString(deterministic=True)))
    def test_corrupted_digest_fails_replay(self):
        raw,res,_=run(fixture(),host_authorized=True,enabled=True)
        res.request_sha256=b'forged'
        self.assertFalse(verify_discovery_result(raw,res.SerializeToString(deterministic=True)))
    def test_failed_not_receipted(self):
        raw,res,reply=run(fixture())
        self.assertFalse(discovery_receipt(raw,reply).deterministic_replay_verified)
    def test_invalid_frame(self):
        self.assertEqual(d.DiscoveryResult.FromString(run_discovery_frame(b'\x00')).status,d.DISCOVERY_REJECTED)

if __name__=='__main__':unittest.main()
