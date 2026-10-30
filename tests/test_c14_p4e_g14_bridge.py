"""G14 negative and research-only scientific evidence composition tests."""
import copy
import hashlib
import unittest
from cognitum import causal_genuine_worker_assurance as gate
from cognitum import causal_integrated_assurance as g13
from cognitum import causal_mature_backend as mature
from cognitum.proto import causal_genuine_worker_assurance_pb2 as pb
from cognitum.proto import causal_mature_pb2 as m
from tests.test_c14_p4e_g13_integration import request as g13_request
from tests.test_c14_p3c_mature_adapter import fixtures,encode


def fabricated_candidate(worker_req):
    """Demonstrates non-cryptographic shape check can be passed by a forger!"""
    raw=encode(worker_req)
    _,reference=mature._parse(raw)
    r=m.MatureCausalResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
      trace_id=worker_req.trace_id,backend=worker_req.backend,
      backend_id=mature.BACKEND_NAMES[worker_req.backend],
      status=m.MATURE_RESULT_CANDIDATE,reason_code='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF',
      assurance=mature.ASSURANCE,runtime_version=mature.BACKEND_PACKAGES[worker_req.backend][1])
    if worker_req.backend==m.ECONML_LINEAR_DML_0170:
        r.sample_count=sum(x.count for x in worker_req.conditional_effects.estimation.observations)
        for group in reference.subgroups:
            r.effects.add(modifier_states=group.modifier_states,
              observations=group.observations,estimated_effect=group.estimated_effect,
              reference_effect=group.estimated_effect,absolute_reference_difference='0')
    else:
        r.sample_count=len(worker_req.candidate_graph.observations)
        r.skeleton_edges.add(first=0,second=1)
    return encode(r)


def request(worker_req=None,worker_reply=None,intent=None):
    worker_req=worker_req or fixtures()[0]
    upstream=g13_request()
    upstream.trace_id=worker_req.trace_id
    if intent is not None: upstream.caller_intent=intent
    d,r=g13.calculate(upstream)
    return pb.WorkerAssuranceRequest(
      schema_version=1,trace_id=worker_req.trace_id,
      conversation_id=upstream.conversation_id,task_id=upstream.task_id,
      mature_request_frame=encode(worker_req),
      mature_result_frame=worker_reply if worker_reply is not None else fabricated_candidate(worker_req),
      integrated_request=upstream,integrated_decision=d,integrated_receipt=r)


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good=request()

    def decision(self,q):
        d,r=gate.calculate(q)
        self.assertTrue(gate.verify(q,d,r))
        self.assertFalse(any((d.worker_output_independently_authenticated,
          d.causal_identification_proven,d.calibrated_for_worker_dataset,
          d.authenticated_lu_host,d.may_trigger_external_action,
          d.may_issue_real_world_causal_claim,r.authenticated_lu_host)))
        return d,r

    def test_structurally_valid_forgery_not_authenticated(self):
        d,_=self.decision(self.good)
        # A FORGED result can pass shape checks: this is NOT worker authentication.
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_RESEARCH_DIAGNOSTIC_ONLY)
        self.assertTrue(d.genuine_worker_shape_verified)
        self.assertFalse(d.worker_output_independently_authenticated)
        self.assertFalse(d.calibrated_for_worker_dataset)
        self.assertIn('does not calibrate',d.safe_message)

    def test_other_backend_structural_only(self):
        q=request(fixtures()[1])
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_RESEARCH_DIAGNOSTIC_ONLY)

    def test_worker_result_tamper(self):
        q=copy.deepcopy(self.good)
        r=m.MatureCausalResult.FromString(q.mature_result_frame)
        r.effects[0].reference_effect='10000'
        q.mature_result_frame=encode(r)
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_REJECT_INVALID)

    def test_worker_claims_causal_proof(self):
        q=copy.deepcopy(self.good)
        r=m.MatureCausalResult.FromString(q.mature_result_frame)
        r.causal_assumptions_verified=True
        q.mature_result_frame=encode(r)
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_REJECT_INVALID)

    def test_worker_trace_cross_scope(self):
        q=copy.deepcopy(self.good);q.trace_id='different'
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_REJECT_INVALID)

    def test_g13_receipt_tamper(self):
        q=copy.deepcopy(self.good);q.integrated_receipt.decision_sha256=b'forged'
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_REJECT_INVALID)

    def test_g13_upstream_abstention(self):
        from cognitum.proto import causal_integrated_assurance_pb2 as ipb
        q=request(intent=ipb.CALLER_RECOMMEND_INTERVENTION)
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_ABSTAIN_CAUSAL_OR_ACTION)

    def test_worker_action_escalation(self):
        q=copy.deepcopy(self.good);q.caller_requests_real_world_action=True
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_ABSTAIN_CAUSAL_OR_ACTION)

    def test_caller_asserted_proof(self):
        q=copy.deepcopy(self.good);q.caller_claims_worker_proves_causality=True
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_ABSTAIN_CAUSAL_OR_ACTION)

    def test_cross_conversation_replay(self):
        d,r=self.decision(self.good)
        q=copy.deepcopy(self.good);q.conversation_id='other'
        self.assertFalse(gate.verify(q,d,r))
        d,_=self.decision(q)
        self.assertEqual(d.disposition,pb.WORKER_ASSURANCE_REJECT_INVALID)

    def test_cross_task_replay(self):
        d,r=self.decision(self.good)
        q=copy.deepcopy(self.good);q.task_id='other-task'
        self.assertFalse(gate.verify(q,d,r))

    def test_receipt_cannot_be_promoted(self):
        d,r=self.decision(self.good)
        forged=copy.deepcopy(d);forged.authenticated_lu_host=True
        self.assertFalse(gate.verify(self.good,forged,r))
        forged=copy.deepcopy(d);forged.may_trigger_external_action=True
        self.assertFalse(gate.verify(self.good,forged,r))

    def test_missing_or_oversized_frame(self):
        for raw in (b'',b'x'*(mature.MAX_FRAME+1)):
            q=copy.deepcopy(self.good);q.mature_request_frame=raw
            with self.assertRaisesRegex(ValueError,'G14_INVALID_BOUNDED_REQUEST'):
                gate.calculate(q)

    def test_replay_mutated_worker_response(self):
        d,r=self.decision(self.good)
        q=copy.deepcopy(self.good)
        q.mature_result_frame+=b'\x00'
        self.assertFalse(gate.verify(q,d,r))

if __name__=='__main__':unittest.main()
