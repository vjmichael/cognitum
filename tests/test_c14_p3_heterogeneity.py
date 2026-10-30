"""C14 P3A: conditional empirical effects, no assumed-graph promotion."""
import unittest
from fractions import Fraction
from tests.test_c14_estimation import request
from cognitum.proto import causal_estimation_pb2 as q, causal_heterogeneity_pb2 as h
from cognitum.causal_heterogeneity import (run_heterogeneity_frame,verify_heterogeneity_result,
                                             heterogeneity_receipt,heterogeneity_audit)


def fixture():
    return h.HeterogeneityRequest(schema_version=1,estimation=request(),
        modifier_indices=[0],max_subgroups=8,timeout_ms=1500,
        method=h.REFERENCE_CONDITIONAL_STANDARDIZATION)


def run(r,**kwargs):
    raw=r.SerializeToString(deterministic=True)
    reply=run_heterogeneity_frame(raw,**kwargs)
    return raw,h.HeterogeneityResult.FromString(reply),reply

class TestC14P3Heterogeneity(unittest.TestCase):
    def test_exact_subgroup_effects_and_overall_reconciliation(self):
        raw,got,reply=run(fixture(),host_authorized=True,enabled=True)
        self.assertEqual(got.status,h.CONDITIONAL_EFFECTS_COMPUTED)
        self.assertEqual([x.estimated_effect for x in got.subgroups],['1','0'])
        self.assertEqual([x.observed_weight for x in got.subgroups],['3/5','2/5'])
        self.assertEqual(got.overall_effect,'3/5')
        self.assertEqual(Fraction(got.subgroup_weighted_effect),Fraction(3,5))
        self.assertTrue(verify_heterogeneity_result(raw,reply))
        receipt=heterogeneity_receipt(raw,reply)
        self.assertTrue(receipt.arithmetic_verified)
        self.assertFalse(receipt.causal_assumptions_proven)
        audit=heterogeneity_audit(raw,reply)
        self.assertEqual(audit.trace_id,'c14-p2a')
        self.assertNotIn(b'no',audit.SerializeToString())

    def test_missing_permission(self):
        self.assertEqual(run(fixture(),enabled=True)[1].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_default_disabled(self):
        self.assertEqual(run(fixture(),host_authorized=True)[1].reason_code,'HETEROGENEITY_DISABLED')
    def test_unadjusted_variable_rejected(self):
        r=fixture();r.modifier_indices[:]=[2]
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_REJECTED)
    def test_duplicate_modifier_rejected(self):
        r=fixture();r.modifier_indices[:]=[0,0]
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_REJECTED)
    def test_no_modifiers_rejected(self):
        r=fixture();r.modifier_indices.clear()
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_REJECTED)
    def test_subgroup_budget(self):
        r=fixture();r.max_subgroups=1
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_INCONCLUSIVE)
    def test_optional_econml_unavailable(self):
        r=fixture();r.method=h.ECONML_CATE_OPTIONAL
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_BACKEND_UNAVAILABLE)
    def test_method_required(self):
        r=fixture();r.method=h.HETEROGENEITY_METHOD_UNSPECIFIED
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_REJECTED)
    def test_reference_backend_required(self):
        r=fixture();r.estimation.backend=q.DOWHY_OPTIONAL_WORKER
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].reason_code,'REFERENCE_BACKEND_REQUIRED')
    def test_missing_arm_not_fabricated(self):
        r=fixture();del r.estimation.observations[2]
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_OVERLAP_FAILED)
    def test_graph_not_certified(self):
        r=fixture();r.estimation.identification.adjustment.clear()
        # Modifier outside adjusted set must fail before unsupported identification claims.
        self.assertEqual(run(r,host_authorized=True,enabled=True)[1].status,h.HETEROGENEITY_REJECTED)
    def test_forged_group_effect_rejected(self):
        raw,got,_=run(fixture(),host_authorized=True,enabled=True)
        got.subgroups[0].estimated_effect='1000'
        self.assertFalse(verify_heterogeneity_result(raw,got.SerializeToString(deterministic=True)))
    def test_forged_overall_effect_rejected(self):
        raw,got,_=run(fixture(),host_authorized=True,enabled=True)
        got.overall_effect='0'
        self.assertFalse(verify_heterogeneity_result(raw,got.SerializeToString(deterministic=True)))
    def test_wrong_request_digest_rejected(self):
        raw,got,_=run(fixture(),host_authorized=True,enabled=True)
        got.request_sha256=b'x'*32
        self.assertFalse(verify_heterogeneity_result(raw,got.SerializeToString(deterministic=True)))
    def test_failed_result_no_receipt(self):
        raw,got,reply=run(fixture())
        self.assertFalse(heterogeneity_receipt(raw,reply).arithmetic_verified)
    def test_invalid_frame_rejected(self):
        self.assertEqual(h.HeterogeneityResult.FromString(run_heterogeneity_frame(b'garbage')).status,h.HETEROGENEITY_REJECTED)

if __name__=='__main__':unittest.main()
