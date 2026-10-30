"""P3D synthetic graph/effect comparisons: do not assert causal identification."""
import hashlib
import random
import unittest

from cognitum.proto import causal_validation_pb2 as v
from cognitum.proto import causal_discovery_pb2 as d
from cognitum.proto import causal_heterogeneity_pb2 as h
from cognitum.proto import causal_mature_pb2 as m
from cognitum.causal_discovery import run_discovery_frame
from cognitum.causal_heterogeneity import run_heterogeneity_frame
from cognitum.causal_mature_backend import BACKEND_NAMES, ASSURANCE
from cognitum.causal_validation import (run_validation_frame,validation_receipt,
    run_conditional_comparison_frame,conditional_comparison_receipt)
from tests.test_c14_p3c_mature_adapter import fixtures


def encoded(x):return x.SerializeToString(deterministic=True)


def graph_case(*, truth=True, external=False):
    model=fixtures()[1]
    source=d.DiscoveryRequest();source.CopyFrom(model.candidate_graph)
    source.method=d.REFERENCE_PC_STABLE_SKELETON
    reply=run_discovery_frame(encoded(source),host_authorized=True,enabled=True)
    req=v.DiscoveryValidationRequest(schema_version=1,trace_id=source.trace_id,
        reference_request=source,reference_result=reply,
        has_declared_synthetic_truth=truth)
    if truth:
        req.declared_truth_skeleton.add(first=0,second=1)
        req.declared_truth_skeleton.add(first=1,second=2)
    if external:
        req.external_request.CopyFrom(model)
        out=m.MatureCausalResult(schema_version=1,
            request_sha256=hashlib.sha256(encoded(model)).digest(),
            trace_id=model.trace_id,backend=model.backend,backend_id=BACKEND_NAMES[model.backend],
            runtime_version='0.1.4.8',status=m.MATURE_RESULT_CANDIDATE,
            reason_code='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF',
            assurance=ASSURANCE,sample_count=len(source.observations))
        out.skeleton_edges.add(first=0,second=1)
        out.skeleton_edges.add(first=1,second=2)
        req.external_result=encoded(out)
    return req


def effects_case():
    ext=fixtures()[0]
    original=h.HeterogeneityRequest();original.CopyFrom(ext.conditional_effects)
    original.method=h.REFERENCE_CONDITIONAL_STANDARDIZATION
    original_reply=run_heterogeneity_frame(encoded(original),host_authorized=True,enabled=True)
    reference=h.HeterogeneityResult.FromString(original_reply)
    out=m.MatureCausalResult(schema_version=1,
        request_sha256=hashlib.sha256(encoded(ext)).digest(),
        trace_id=ext.trace_id,backend=ext.backend,backend_id=BACKEND_NAMES[ext.backend],
        runtime_version='0.17.0',status=m.MATURE_RESULT_CANDIDATE,
        reason_code='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF',
        assurance=ASSURANCE,
        sample_count=sum(row.count for row in original.estimation.observations))
    for idx,group in enumerate(reference.subgroups):
        val='0.75' if idx==0 else '0.2'
        out.effects.add(modifier_states=group.modifier_states,
            observations=group.observations,estimated_effect=val,
            reference_effect=group.estimated_effect,
            absolute_reference_difference='0.25' if idx==0 else '0.2')
    return v.ConditionalComparisonRequest(schema_version=1,trace_id=ext.trace_id,
        reference_request=original,reference_result=original_reply,
        external_request=ext,external_result=encoded(out))


class TestC14P3DDiscovery(unittest.TestCase):
    def run_it(self,req,**flags):
        raw=encoded(req);reply=run_validation_frame(raw,**flags)
        return raw,v.DiscoveryValidationResult.FromString(reply),reply

    def test_declared_synthetic_skeleton_metrics(self):
        raw,result,reply=self.run_it(graph_case(),host_authorized=True,enabled=True)
        self.assertEqual(result.status,v.CANDIDATE_COMPARISON_COMPUTED)
        self.assertTrue(result.reference_replay_checked)
        self.assertTrue(result.has_synthetic_scores)
        self.assertEqual((result.reference_scores.true_positive,result.reference_scores.false_positive,
            result.reference_scores.false_negative),(2,0,0))
        self.assertEqual(result.reference_scores.f1,'1')
        self.assertFalse(result.graph_orientations_identified)
        self.assertFalse(result.real_world_causation_proven)
        self.assertTrue(validation_receipt(raw,reply).deterministic_arithmetic_replay)
        self.assertFalse(validation_receipt(raw,reply).true_causal_graph_verified)

    def test_cross_backend_candidate_descriptive_only(self):
        raw,result,reply=self.run_it(graph_case(external=True),host_authorized=True,enabled=True)
        self.assertEqual(result.status,v.CANDIDATE_COMPARISON_COMPUTED)
        self.assertTrue(result.external_shape_checked)
        self.assertEqual(result.reference_external_jaccard,'1')
        self.assertEqual(result.external_scores.f1,'1')
        self.assertIn('NOT_PROVEN_LIBRARY_EXECUTION',result.evidence_limitations)
        self.assertFalse(result.real_world_causation_proven)
        self.assertTrue(validation_receipt(raw,reply).deterministic_arithmetic_replay)

    def test_mismatched_external_data_rejected(self):
        req=graph_case(external=True)
        req.external_request.candidate_graph.observations[0].values[0]+=0.1
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].reason_code,
                         'DATASET_OR_SETTINGS_MISMATCH')

    def test_reference_replay_tamper_rejected(self):
        req=graph_case()
        reply=d.DiscoveryResult.FromString(req.reference_result)
        reply.undirected_edges[0].second=2
        req.reference_result=encoded(reply)
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].status,
                         v.CAUSAL_VALIDATION_INCONCLUSIVE)

    def test_external_forged_orientation_not_promoted(self):
        req=graph_case(external=True)
        reply=m.MatureCausalResult.FromString(req.external_result)
        reply.orientations_published=True
        req.external_result=encoded(reply)
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].reason_code,
                         'UNVERIFIED_EXTERNAL_SHAPE')

    def test_external_digest_corruption(self):
        req=graph_case(external=True)
        reply=m.MatureCausalResult.FromString(req.external_result)
        reply.request_sha256=b'bad'
        req.external_result=encoded(reply)
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].status,
                         v.CAUSAL_VALIDATION_INCONCLUSIVE)

    def test_no_declared_truth_no_accuracy_claim(self):
        _,res,_=self.run_it(graph_case(truth=False),host_authorized=True,enabled=True)
        self.assertEqual(res.status,v.CANDIDATE_COMPARISON_COMPUTED)
        self.assertFalse(res.has_synthetic_scores)
        self.assertFalse(res.HasField('reference_scores'))

    def test_invalid_edge_canonical_order(self):
        req=graph_case();req.declared_truth_skeleton[1].first=2
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].reason_code,
                         'NONCANONICAL_OR_INVALID_EDGES')

    def test_no_truth_flag_rejects_truth_edges(self):
        req=graph_case();req.has_declared_synthetic_truth=False
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].reason_code,
                         'UNLABELED_SYNTHETIC_GRAPH')

    def test_missing_external_pair(self):
        req=graph_case(external=True);req.external_result=b''
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].reason_code,
                         'INCOMPLETE_EXTERNAL_PAIR')

    def test_host_and_disabled(self):
        req=graph_case()
        self.assertEqual(self.run_it(req,enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertEqual(self.run_it(req,host_authorized=True)[1].reason_code,'VALIDATION_DISABLED')

    def test_invalid_frame(self):
        for raw in (b'',b'bad'*100000):
            got=v.DiscoveryValidationResult.FromString(run_validation_frame(raw))
            self.assertEqual(got.status,v.CAUSAL_VALIDATION_REJECTED)

    def test_receipt_does_not_accept_modified_scores(self):
        raw,got,_=self.run_it(graph_case(),host_authorized=True,enabled=True)
        got.reference_scores.f1='0.5'
        self.assertFalse(validation_receipt(raw,encoded(got)).deterministic_arithmetic_replay)

    def test_markov_equivalence_ambiguity(self):
        # X->Y->Z and X<-Y->Z share a Markov equivalence class:
        # same skeleton, no unshielded collider, so this method cannot orient.
        req=graph_case(truth=True)
        _,result,_=self.run_it(req,host_authorized=True,enabled=True)
        orientation_a=[(0,1),(1,2)]
        orientation_b=[(1,0),(1,2)]
        self.assertNotEqual(orientation_a,orientation_b)
        self.assertFalse(result.graph_orientations_identified)
        self.assertEqual(result.reference_scores.f1,'1')

    def test_gaussian_markov_equivalent_chain_fork_same_covariance(self):
        # Explicitly construct two distinct linear-Gaussian SCMs with the
        # same observational covariance matrix. Statistical CI cannot
        # distinguish these orientations without extra assumptions.
        from fractions import Fraction as Q
        # Chain: X~N(0,1), Y=(7/10)X+N(0,49/100), Z=(3/5)Y+N(0,1/4)
        covariance_chain={(0,0):Q(1),(1,1):Q(49,50),
            (2,2):Q(3,5)**2*Q(49,50)+Q(1,4),
            (0,1):Q(7,10),(0,2):Q(7,10)*Q(3,5),
            (1,2):Q(49,50)*Q(3,5)}
        # Fork: Y~N(0,49/50), X=(5/7)Y+N(0,1/2),
        # Z=(3/5)Y+N(0,1/4). Their observed joint is identical.
        var_y=Q(49,50)
        coef_x=Q(5,7)
        covariance_fork={(0,0):coef_x**2*var_y+Q(1,2),
            (1,1):var_y,(2,2):Q(3,5)**2*var_y+Q(1,4),
            (0,1):coef_x*var_y,(0,2):coef_x*Q(3,5)*var_y,
            (1,2):Q(3,5)*var_y}
        self.assertEqual(covariance_chain,covariance_fork)
        self.assertFalse(self.run_it(graph_case(),host_authorized=True,enabled=True)[1].graph_orientations_identified)

    def test_skeleton_stability_on_multiple_synthetic_seeds(self):
        # A small deterministic regression fixture, not a statistically
        # powered graph-recovery benchmark or confidence interval.
        from tests.test_c14_p3_discovery import fixture as gaussian_fixture
        recovered=[]
        for seed in (7,19,42,81,131):
            source=gaussian_fixture(seed=seed)
            captured=d.DiscoveryResult.FromString(run_discovery_frame(
                encoded(source),host_authorized=True,enabled=True))
            self.assertEqual(captured.status,d.CANDIDATE_SKELETON_COMPUTED)
            recovered.append(tuple((e.first,e.second) for e in captured.undirected_edges))
            self.assertFalse(captured.orientations_inferred)
        self.assertEqual(recovered,[((0,1),(1,2))]*5)

    def test_negative_control_independent_gaussians(self):
        rng=random.Random(131)
        req=d.DiscoveryRequest(schema_version=1,trace_id='p3d-negative',
            method=d.REFERENCE_PC_STABLE_SKELETON,variable_ids=['A','B','C'],
            alpha=0.001,max_conditioning=2,max_tests=250,timeout_ms=5000)
        for _ in range(200):
            req.observations.add(values=[rng.gauss(0,1),rng.gauss(0,1),rng.gauss(0,1)])
        captured=run_discovery_frame(encoded(req),host_authorized=True,enabled=True)
        check=v.DiscoveryValidationRequest(schema_version=1,trace_id=req.trace_id,
            reference_request=req,reference_result=captured,has_declared_synthetic_truth=True)
        _,out,_=self.run_it(check,host_authorized=True,enabled=True)
        self.assertEqual(out.status,v.CANDIDATE_COMPARISON_COMPUTED)
        self.assertEqual(out.reference_scores.f1,'1')
        self.assertFalse(d.DiscoveryResult.FromString(captured).undirected_edges)

class TestC14P3DEffectComparison(unittest.TestCase):
    def run_it(self,req,**flags):
        raw=encoded(req);reply=run_conditional_comparison_frame(raw,**flags)
        return raw,v.ConditionalComparisonResult.FromString(reply),reply

    def test_descriptive_numeric_difference(self):
        raw,out,reply=self.run_it(effects_case(),host_authorized=True,enabled=True)
        self.assertEqual(out.status,v.CANDIDATE_COMPARISON_COMPUTED)
        self.assertTrue(out.empirical_reference_replay_checked)
        self.assertTrue(out.external_shape_checked)
        self.assertEqual([g.absolute_difference for g in out.differences],['0.25','0.2'])
        self.assertEqual(out.mean_absolute_difference,'0.225')
        self.assertEqual(out.max_absolute_difference,'0.25')
        self.assertFalse(out.same_estimand_proven)
        self.assertFalse(out.causal_assumptions_proven)
        self.assertTrue(conditional_comparison_receipt(raw,reply).deterministic_arithmetic_replay)

    def test_model_and_empirical_may_disagree(self):
        req=effects_case()
        observed=v.ConditionalComparisonResult.FromString(run_conditional_comparison_frame(
            encoded(req),host_authorized=True,enabled=True))
        self.assertEqual(observed.status,v.CANDIDATE_COMPARISON_COMPUTED)
        self.assertNotEqual(observed.mean_absolute_difference,'0')
        self.assertFalse(observed.same_estimand_proven)

    def test_different_dataset_rejected(self):
        req=effects_case()
        req.external_request.conditional_effects.modifier_indices[0]=1
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].status,
                         v.CAUSAL_VALIDATION_REJECTED)

    def test_tampered_reference_rejected(self):
        req=effects_case()
        source=h.HeterogeneityResult.FromString(req.reference_result)
        source.subgroups[0].estimated_effect='1000'
        req.reference_result=encoded(source)
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].status,
                         v.CAUSAL_VALIDATION_INCONCLUSIVE)

    def test_tampered_mature_candidate_rejected(self):
        req=effects_case()
        source=m.MatureCausalResult.FromString(req.external_result)
        source.effects[0].estimated_effect='1000'
        req.external_result=encoded(source)
        self.assertEqual(self.run_it(req,host_authorized=True,enabled=True)[1].status,
                         v.CAUSAL_VALIDATION_INCONCLUSIVE)

    def test_host_denied_and_disabled(self):
        req=effects_case()
        self.assertEqual(self.run_it(req,enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertEqual(self.run_it(req,host_authorized=True)[1].reason_code,'VALIDATION_DISABLED')

    def test_receipt_rejects_modified_error(self):
        raw,out,_=self.run_it(effects_case(),host_authorized=True,enabled=True)
        out.mean_absolute_difference='99'
        self.assertFalse(conditional_comparison_receipt(raw,encoded(out)).deterministic_arithmetic_replay)

    def test_failed_not_promoted(self):
        req=effects_case();raw=encoded(req)
        reply=run_conditional_comparison_frame(raw)
        self.assertFalse(conditional_comparison_receipt(raw,reply).deterministic_arithmetic_replay)

if __name__=='__main__':unittest.main()
