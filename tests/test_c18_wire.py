"""C18 candidate versus incumbent read-only evaluation Protobuf regression."""
import unittest
from dataclasses import replace

from cognitum.adaptation_policy import (
    RoutingPolicy,Trace,AdaptationProposal,seal,train,
)
from cognitum.proto import adaptation_pb2 as pb
from cognitum.adaptation_wire import execute_evaluation,verify_evaluation

SHA="a"*64

def input_set():
    base=seal(RoutingPolicy(
        1,"workspace_a","tool_router",("general",),2,
        ((0.,0.),(0.,0.),(0.,0.)),(.5,0.,0.),
        (0.,0.),(1.,1.),"b"*64,"base_origin","0"*64,"approved",""))
    p=AdaptationProposal("proposal_a","workspace_a","tool_router",2,SHA,
        "consent_a","public_synthetic",("general",),200000,
        61000,61000,base.digest,80,120000,base.digest)
    routes=("direct","specialist","abstain")
    rows=tuple(Trace("ev_"+str(i),1000*(i+1),
        (float((i%3-1)*3),float(i%3-1)),routes[i%3],SHA,
        "consent_a",200000,"public_synthetic","general")
        for i in range(90))
    candidate,holdout=train(p,rows,now_ms=100000,host_authorized=True)
    return p,base,candidate,holdout


def pack_policy(p,out):
    for name in ("policy_version","workspace_id","target","feature_count",
                 "training_digest","proposal_id","base_policy_digest",
                 "status","digest"):
        setattr(out,name,getattr(p,name))
    out.allowed_families.extend(p.allowed_families)
    out.intercepts.extend(p.intercepts)
    out.center.extend(p.center)
    out.scale.extend(p.scale)
    for row in p.coefficients:out.coefficients.add(values=row)


def pack():
    p,baseline,candidate,holdout=input_set()
    request=pb.EvaluateRequest(schema_version=1)
    for name in ("proposal_id","workspace_id","target","policy_version",
                 "source_digest","consent_receipt","privacy_class",
                 "retention_until_ms","train_before_ms","holdout_from_ms",
                 "base_policy_digest","maximum_training_rows",
                 "maximum_cpu_ms","rollback_policy_digest"):
        setattr(request.proposal,name,getattr(p,name))
    request.proposal.allowed_families.extend(p.allowed_families)
    pack_policy(candidate,request.candidate)
    pack_policy(baseline,request.incumbent)
    for t in holdout:
        row=request.holdout.add()
        for name in ("event_id","occurred_ms","expected_route","source_digest",
                     "consent_receipt","retention_until_ms",
                     "privacy_class","task_family"):
            setattr(row,name,getattr(t,name))
        row.features.extend(t.features)
    return request.SerializeToString(deterministic=True)


class C18WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import numpy,sklearn
        except ImportError:
            raise unittest.SkipTest("genuine optional scikit-learn unavailable")

    def test_real_trained_candidate_heldout_protobuf(self):
        request=pack()
        result=verify_evaluation(request,execute_evaluation(request))
        self.assertEqual(result.schema_version,1)
        self.assertEqual(result.status,"READY_FOR_HOST_APPROVAL")
        self.assertGreater(result.candidate_metrics.accuracy,
                           result.incumbent_metrics.accuracy)
        self.assertEqual(result.candidate_metrics.count,30)
        self.assertEqual(len(result.holdout_digest),64)

    def test_forged_reply_and_policy_digest_refused(self):
        req=pack()
        out=pb.EvaluateResult()
        out.ParseFromString(execute_evaluation(req))
        out.candidate_metrics.accuracy=0.
        with self.assertRaises(ValueError):
            verify_evaluation(req,out.SerializeToString(deterministic=True))
        r=pb.EvaluateRequest()
        r.ParseFromString(req)
        r.candidate.coefficients[0].values[0]+=2.
        with self.assertRaises(ValueError):
            execute_evaluation(r.SerializeToString(deterministic=True))

    def test_unknown_wire_and_training_effects_absent(self):
        request=pack()
        for bad in (b"",request+b"\x98\x06\x01",request+b"\x08\x01",
                    b"\x0a\xff",b"x"*200001):
            with self.subTest(prefix=bad[:10]),self.assertRaises(ValueError):
                execute_evaluation(bad)
        fields={x.name for x in pb.EvaluateRequest.DESCRIPTOR.fields}
        for unauthorized in ("execute_training","filesystem_path","shell",
                             "permission_grant","base_model_weights"):
            self.assertNotIn(unauthorized,fields)


if __name__=="__main__":
    unittest.main()
