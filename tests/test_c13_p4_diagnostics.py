"""C13 P4 ArviZ diagnostic checks, not a convergence or sampling benchmark."""
import hashlib
import random
import unittest
import math
from cognitum import probability_diagnostics as d
from cognitum.proto import probability_diagnostics_pb2 as p


def request(seed=3):
    rng=random.Random(seed)
    r=p.DiagnosticsRequest(schema_version=1,trace_id='c13.p4.diag',timeout_ms=20000)
    for name in ('population_mu','group_sd'):
        v=r.parameters.add(parameter=name)
        for _ in range(4):v.chains.add().values.extend(rng.gauss(0,1) for _ in range(80))
    return r


def execute(req=None,authorized=True,enabled=True):
    req=req or request();raw=req.SerializeToString(deterministic=True)
    out=d.run_diagnostics_frame(raw,host_authorized=authorized,enabled=enabled)
    return raw,out,p.DiagnosticsResult.FromString(out)

class DiagnosticsTests(unittest.TestCase):
    def test_real_arviz_rank_ess_mcse(self):
        raw,out,res=execute()
        self.assertEqual(res.status,p.DIAGNOSTICS_SUCCESS)
        self.assertEqual(len(res.parameters),2)
        self.assertTrue(res.backend_version.startswith('arviz-'))
        for row in res.parameters:
            self.assertEqual(row.chains,4)
            self.assertEqual(row.draws_per_chain,80)
            self.assertGreater(row.rhat_rank,0)
            self.assertGreater(row.ess_bulk,0)
            self.assertGreater(row.ess_tail,0)
            self.assertGreater(row.mcse_mean,0)
        self.assertTrue(d.verify_diagnostics_receipt(raw,out).evidence_valid)
    def test_sample_diagnostics_not_proof(self):
        receipt=d.verify_diagnostics_receipt(*execute()[:2])
        self.assertEqual(receipt.assurance,'ARVIZ_RECOMPUTED_NOT_CONVERGENCE_PROOF')
    def test_different_chains_detect_difference(self):
        req=request()
        for c in req.parameters[0].chains[2:]:
            for i in range(len(c.values)):c.values[i]+=10
        res=execute(req)[2]
        self.assertEqual(res.status,p.DIAGNOSTICS_SUCCESS)
        self.assertGreater(res.parameters[0].rhat_rank,1.1)
    def test_no_constant_diagnostic_proof(self):
        req=request()
        for v in req.parameters:
            for c in v.chains:
                for i in range(len(c.values)):c.values[i]=2
        raw,out,r=execute(req)
        self.assertNotEqual(r.status,p.DIAGNOSTICS_SUCCESS)
        self.assertFalse(d.verify_diagnostics_receipt(raw,out).evidence_valid)
    def test_bad_trace(self):
        req=request();req.trace_id=' ';
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_unequal_chains(self):
        req=request();del req.parameters[0].chains[0].values[-1]
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_one_chain(self):
        req=request();del req.parameters[0].chains[1:]
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_too_few_draws(self):
        req=request()
        for c in req.parameters[0].chains:del c.values[19:]
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_nonfinite(self):
        req=request();req.parameters[0].chains[0].values[0]=float('nan')
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_duplicate_parameter(self):
        req=request();req.parameters[1].parameter=req.parameters[0].parameter
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_no_parameter(self):
        req=request();req.ClearField('parameters')
        self.assertEqual(execute(req)[2].status,p.DIAGNOSTICS_REJECTED)
    def test_unauthorized(self):
        self.assertEqual(execute(authorized=False)[2].reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_disabled(self):
        self.assertEqual(execute(enabled=False)[2].reason_code,'DIAGNOSTICS_DISABLED')
    def test_corrupt_frame(self):
        r=p.DiagnosticsResult.FromString(d.run_diagnostics_frame(b'\xff',host_authorized=True,enabled=True))
        self.assertEqual(r.status,p.DIAGNOSTICS_REJECTED)
    def test_modified_rhat(self):
        raw,out,r=execute();r.parameters[0].rhat_rank+=.05
        self.assertFalse(d.verify_diagnostics_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_modified_ess(self):
        raw,out,r=execute();r.parameters[0].ess_bulk+=100
        self.assertFalse(d.verify_diagnostics_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_modified_backend_version(self):
        raw,out,r=execute();r.backend_version='arviz-forged'
        self.assertFalse(d.verify_diagnostics_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_modified_names(self):
        raw,out,r=execute();r.parameters[0].parameter='forged'
        self.assertFalse(d.verify_diagnostics_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_modified_request_digest(self):
        raw,out,r=execute();r.request_sha256=b'wrong'
        self.assertFalse(d.verify_diagnostics_receipt(raw,r.SerializeToString()).evidence_valid)
    def test_audit_no_raw_samples(self):
        raw,out,r=execute();a=d.make_diagnostics_audit(raw,out)
        self.assertTrue(a.verified)
        self.assertEqual(a.request_sha256,hashlib.sha256(raw).digest())
        self.assertEqual(a.parameter_count,2)
        self.assertNotIn(b'population_mu',a.SerializeToString())
    def test_reject_forged_receipt(self):
        raw,out,r=execute();receipt=d.verify_diagnostics_receipt(raw,out)
        receipt.evidence_valid=False
        with self.assertRaises(ValueError):d.make_diagnostics_audit(raw,out,receipt)
    def test_no_executable_from_prompt(self):
        self.assertNotIn('executable',[f.name for f in p.DiagnosticsRequest.DESCRIPTOR.fields])
    def test_meta_only_on_denial(self):
        raw,out,r=execute(authorized=False)
        self.assertFalse(d.make_diagnostics_audit(raw,out).verified)

if __name__=='__main__':unittest.main()
