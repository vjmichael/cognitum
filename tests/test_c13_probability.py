"""C13 focused functional tests; no model/runtime or comparative performance claims."""
import hashlib
import random
import unittest
from fractions import Fraction

from cognitum.proto import probability_pb2 as p
from cognitum import probability as c


def example(method=p.EXACT_VARIABLE_ELIMINATION):
    """Rain -> WetGround, where likelihoods are exactly encoded ppm."""
    q = p.InferenceRequest(schema_version=1, trace_id='c13-smoke', method=method,
                           timeout_ms=5000, max_verifier_assignments=512)
    q.model.nodes.add(id='rain', states=['no', 'yes'], cpt_ppm=[800000,200000])
    q.model.nodes.add(id='wet', states=['no', 'yes'], parents=[0],
                      cpt_ppm=[900000,100000,200000,800000])
    q.targets.append(0)
    return q


def ask(req, authorized=True, enabled=True):
    raw = req.SerializeToString(deterministic=True)
    answer_frame = c.infer_frame(raw, host_authorized=authorized, enabled=enabled)
    return p.InferenceResult.FromString(answer_frame), raw, answer_frame


def probs(answer):
    return {tuple(x.states): x.probability for x in answer.posterior}


class TestC13Probability(unittest.TestCase):
    def test_prior(self):
        result, raw, output = ask(example())
        self.assertEqual(result.status, p.EXACT_POSTERIOR)
        self.assertEqual(probs(result), {(0,): '4/5', (1,): '1/5'})
        self.assertEqual(result.evidence_probability, '1')
        self.assertTrue(result.independent_posterior_verified)
        self.assertTrue(c.verify_receipt(raw, output).exact_posterior_verified)

    def test_hard_evidence_bayes(self):
        req = example()
        req.hard_evidence.add(node=1,state=1)
        result, raw, output = ask(req)
        # P(rain=yes | wet=yes)=0.16/(0.08+0.16)=2/3.
        self.assertEqual(probs(result), {(0,): '1/3', (1,): '2/3'})
        self.assertEqual(result.evidence_probability,'6/25')
        self.assertTrue(c.verify_receipt(raw, output).evidence_valid)

    def test_soft_evidence(self):
        req = example()
        req.soft_evidence.add(node=1, likelihood_ppm=[200000,1000000])
        result,raw,output=ask(req)
        # P(no | evidence) = 0.8*(0.9*0.2+0.1*1) = .224
        # P(yes | evidence)=0.2*(0.2*0.2+0.8*1) = .168
        self.assertEqual(probs(result), {(0,):'4/7',(1,):'3/7'})
        self.assertEqual(result.evidence_probability,'49/125')
        self.assertTrue(c.verify_receipt(raw,output).exact_posterior_verified)

    def test_joint_query_conditioned(self):
        req=example()
        req.targets[:]=[0,1]
        req.hard_evidence.add(node=1,state=1)
        result, raw, out=ask(req)
        self.assertEqual(probs(result), {(0,0):'0',(0,1):'1/3',(1,0):'0',(1,1):'2/3'})
        self.assertTrue(c.verify_receipt(raw,out).exact_posterior_verified)

    def test_impossible_evidence_is_exact_not_synthetic(self):
        req=example()
        req.model.nodes[1].cpt_ppm[:]=[1000000,0,1000000,0]
        req.hard_evidence.add(node=1,state=1)
        result,raw,out=ask(req)
        self.assertEqual(result.status,p.IMPOSSIBLE_EVIDENCE)
        self.assertFalse(result.posterior)
        self.assertFalse(result.independent_posterior_verified)
        self.assertTrue(c.verify_receipt(raw,out).exact_posterior_verified)

    def test_soft_and_hard_evidence_same_node(self):
        req=example()
        req.hard_evidence.add(node=1,state=1)
        req.soft_evidence.add(node=1, likelihood_ppm=[0,600000])
        result,raw,out=ask(req)
        self.assertEqual(probs(result)[(1,)],'2/3')
        self.assertTrue(c.verify_receipt(raw,out).exact_posterior_verified)

    def test_cycle_rejected(self):
        req=example()
        req.model.nodes[0].parents.append(1)
        req.model.nodes[0].cpt_ppm[:]=[800000,200000,800000,200000]
        self.assertEqual(ask(req)[0].status,p.REJECTED_INFERENCE)

    def test_invalid_probability_row(self):
        req=example();req.model.nodes[0].cpt_ppm[0]=700000
        self.assertEqual(ask(req)[0].reason_code,'INVALID_CPT_NORMALIZATION')

    def test_invalid_parent_index(self):
        req=example();req.model.nodes[1].parents[:]=[4]
        self.assertEqual(ask(req)[0].reason_code,'INVALID_PARENTS')

    def test_malformed_cpt(self):
        req=example();req.model.nodes[1].cpt_ppm.pop()
        self.assertEqual(ask(req)[0].reason_code,'INVALID_CPT_SIZE')

    def test_duplicate_evidence(self):
        req=example();req.hard_evidence.add(node=0,state=1);req.hard_evidence.add(node=0,state=0)
        self.assertEqual(ask(req)[0].reason_code,'INVALID_HARD_EVIDENCE')

    def test_zero_soft_likelihoods(self):
        req=example();req.soft_evidence.add(node=1,likelihood_ppm=[0,0])
        self.assertEqual(ask(req)[0].reason_code,'INVALID_SOFT_EVIDENCE')

    def test_unauthorized(self):
        result,_,_=ask(example(),authorized=False)
        self.assertEqual(result.status,p.REJECTED_INFERENCE)
        self.assertEqual(result.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_disabled(self):
        self.assertEqual(ask(example(),enabled=False)[0].reason_code,'PROBABILITY_DISABLED')

    def test_sampling_reproducible_but_not_verified(self):
        req=example(p.SEEDED_LIKELIHOOD_WEIGHTING)
        req.samples=2000
        req.random_seed=73
        req.hard_evidence.add(node=1,state=1)
        a,raw,out=ask(req)
        b,_,out2=ask(req)
        self.assertEqual(a.status,p.APPROXIMATE_POSTERIOR)
        self.assertEqual(probs(a),probs(b))
        self.assertFalse(a.independent_posterior_verified)
        self.assertFalse(c.verify_receipt(raw,out).evidence_valid)
        self.assertLess(abs(float(probs(a)[(1,)])-2/3), .065)
        self.assertEqual(a.samples_drawn,2000)
        self.assertGreater(a.effective_samples,0)

    def test_sampling_no_positive_weights_is_unknown(self):
        req=example(p.SEEDED_LIKELIHOOD_WEIGHTING)
        req.samples=100
        req.model.nodes[1].cpt_ppm[:]=[1000000,0,1000000,0]
        req.hard_evidence.add(node=1,state=1)
        answer,_,_=ask(req)
        self.assertEqual(answer.status,p.UNKNOWN_INFERENCE)

    def test_samples_not_allowed_for_exact(self):
        req=example();req.samples=2
        self.assertEqual(ask(req)[0].reason_code,'EXACT_REJECTS_SAMPLING')

    def test_factor_limit_returns_unknown_not_unsat(self):
        req=example();req.max_factor_entries=1
        res,_,_=ask(req)
        self.assertEqual(res.status,p.UNKNOWN_INFERENCE)
        self.assertEqual(res.reason_code,'FACTOR_LIMIT')

    def test_verifier_limit_does_not_falsely_certify(self):
        req=example();req.max_verifier_assignments=2
        answer,raw,out=ask(req)
        self.assertEqual(answer.status,p.EXACT_POSTERIOR)
        self.assertFalse(answer.independent_posterior_verified)
        self.assertFalse(c.verify_receipt(raw,out).evidence_valid)

    def test_forged_posterior_rejected(self):
        req=example();answer,raw,out=ask(req)
        answer.posterior[0].probability='1'
        self.assertFalse(c.verify_receipt(raw,answer.SerializeToString(deterministic=True)).evidence_valid)

    def test_forged_assurance_rejected(self):
        req=example();answer,raw,out=ask(req)
        answer.independent_posterior_verified=False
        self.assertFalse(c.verify_receipt(raw,answer.SerializeToString(deterministic=True)).evidence_valid)

    def test_unknown_field_rejected(self):
        req=example();frame=req.SerializeToString(deterministic=True)
        self.assertEqual(p.InferenceResult.FromString(c.infer_frame(frame+b'\xf8\x07\x01',enabled=True,host_authorized=True)).status,p.REJECTED_INFERENCE)

    def test_forged_receipt_cannot_poison_audit(self):
        req=example();_,raw,out=ask(req)
        receipt=c.verify_receipt(raw,out)
        receipt.enumerated_assignments=999
        with self.assertRaisesRegex(ValueError,'FORGED_RECEIPT'):
            c.make_audit(raw,out,receipt)

    def test_audit_has_no_original_observations(self):
        req=example();ans,raw,out=ask(req)
        receipt=c.verify_receipt(raw,out)
        audit=c.make_audit(raw,out,receipt)
        self.assertEqual(audit.request_sha256,hashlib.sha256(raw).digest())
        self.assertTrue(audit.independent_posterior_verified)
        self.assertNotIn(b'rain',audit.SerializeToString())

    def test_multiple_independent_roots_and_unsorted_parent_links(self):
        req=example()
        # Add a third node with two parents in reverse order of node indices.
        req.model.nodes.add(id='alarm',states=['off','on'],parents=[1,0],
                            cpt_ppm=[900000,100000,700000,300000,
                                     800000,200000,100000,900000])
        req.targets[:]=[2]
        result,raw,out=ask(req)
        self.assertEqual(result.status,p.EXACT_POSTERIOR)
        self.assertTrue(c.verify_receipt(raw,out).evidence_valid)

    def test_random_small_dags_match_independent_oracle(self):
        rng=random.Random(0xC130)
        for n in range(2,6):
            for _ in range(18):
                req=p.InferenceRequest(schema_version=1,trace_id='random',method=p.EXACT_VARIABLE_ELIMINATION,
                                       timeout_ms=5000, max_verifier_assignments=8192)
                for i in range(n):
                    parents=[j for j in range(i) if rng.randrange(2)]
                    rows=[]
                    for _ in range(2**len(parents)):
                        x=rng.randrange(0,1000001)
                        rows.extend([x,1000000-x])
                    req.model.nodes.add(id=f'n{i}',states=['false','true'],parents=parents,cpt_ppm=rows)
                req.targets[:]=rng.sample(range(n),k=2)
                if rng.randrange(2): req.hard_evidence.add(node=rng.randrange(n),state=rng.randrange(2))
                res,raw,out=ask(req)
                self.assertIn(res.status,(p.EXACT_POSTERIOR,p.IMPOSSIBLE_EVIDENCE))
                self.assertTrue(c.verify_receipt(raw,out).evidence_valid)

    def test_reverse_index_topology(self):
        req=example()
        # Move parent to node 1 and child to node 0. Parent before child not required.
        req.model.nodes[0].CopyFrom(p.DiscreteNode(id='wet',states=['no','yes'],parents=[1],
                                                   cpt_ppm=[900000,100000,200000,800000]))
        req.model.nodes[1].CopyFrom(p.DiscreteNode(id='rain',states=['no','yes'],cpt_ppm=[800000,200000]))
        req.targets[:]=[1]
        res,raw,out=ask(req)
        self.assertEqual(probs(res),{(0,):'4/5',(1,):'1/5'})
        self.assertTrue(c.verify_receipt(raw,out).evidence_valid)

    def test_request_binding(self):
        req=example();answer,raw,out=ask(req)
        req.trace_id='other'
        self.assertFalse(c.verify_receipt(req.SerializeToString(deterministic=True),out).evidence_valid)

    def test_output_bound(self):
        req=example();req.model.nodes[0].states.extend(['later'])
        self.assertEqual(ask(req)[0].status,p.REJECTED_INFERENCE)

if __name__=='__main__': unittest.main()
