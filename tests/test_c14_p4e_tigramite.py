"""P4E contract, synthetic graph adapter, boundary, and negative checks.

All fake Tigramite tests are interface tests, NOT genuine-library execution.
"""
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
import hashlib
import math
import sys
import unittest
import numpy as np

from cognitum import causal_tigramite_backend as engine
from cognitum.proto import causal_temporal_discovery_pb2 as td
from tests.test_c14_p4c_temporal_diagnostics import case


def request(mode=td.TD_PCMCI_LAGGED,lag=1):
    samples=case(lag=lag)
    return td.TemporalDiscoveryRequest(schema_version=1,samples=samples,mode=mode,
        tau_max=lag,pc_alpha=0.05,timeout_ms=5000,seed=127,
        stationarity_assumption_acknowledged=True)


def run(req,**kw):
    raw=req.SerializeToString(deterministic=True)
    reply=engine.run_temporal_discovery_frame(raw,**kw)
    return raw,td.TemporalDiscoveryResult.FromString(reply),reply


def raw_result(req,*,marks=None):
    raw=req.SerializeToString(deterministic=True)
    mode=req.mode
    out=td.TemporalDiscoveryResult(schema_version=1,
        request_sha256=hashlib.sha256(raw).digest(),trace_id=req.samples.trace_id,
        mode=mode,status=td.TD_CANDIDATE,
        reason_code='PARTIAL_CAUSAL_GRAPH_CANDIDATE_NOT_PROOF',
        backend_id=engine.BACKEND_ID,backend_version=engine.VERSION,
        observed_samples=len(req.samples.observations),
        significance_policy='PCMCI_BH_CORRECTED_P_MATRIX' if mode==td.TD_PCMCI_LAGGED
            else 'PCMCI_PLUS_UNCORRECTED_P_MATRIX',
        assumptions_and_limits=engine.LIMITS)
    for src,dst,lag,mark,p in (marks if marks is not None else [(0,1,1,'-->', '0.001')]):
        out.links.add(source=src,target=dst,lag=lag,marks=mark,significance=p)
    return raw,out


class FakeTigramite:
    def __init__(self,method):
        self.method=method
        self.calls=[]
    def __enter__(self):
        fixture=self
        pp=ModuleType('tigramite.data_processing')
        class DataFrame:
            def __init__(self,data,var_names):
                assert data.shape==(300,2)
                assert len(var_names)==2
                self.data=data
        pp.DataFrame=DataFrame
        parcorr=ModuleType('tigramite.independence_tests.parcorr')
        class ParCorr:pass
        parcorr.ParCorr=ParCorr
        pcmci=ModuleType('tigramite.pcmci')
        class PCMCI:
            def __init__(self,dataframe,cond_ind_test,verbosity):
                assert isinstance(cond_ind_test,ParCorr)
            def run_pcmci(self,**kwargs):
                fixture.calls.append(('pcmci',kwargs))
                graph=np.full((2,2,2),'',dtype='<U3')
                p=np.ones((2,2,2));graph[0,1,1]='-->';p[0,1,1]=0.005
                # Version 5.2.10.1 expected output can have graph or only p_matrix.
                return {'graph':graph,'p_matrix':p}
            def run_pcmciplus(self,**kwargs):
                fixture.calls.append(('pcmciplus',kwargs))
                graph=np.full((2,2,2),'',dtype='<U3')
                p=np.ones((2,2,2));graph[0,1,1]='-->';p[0,1,1]=0.003
                graph[0,1,0]='o-o';graph[1,0,0]='o-o';p[0,1,0]=0.04
                return {'graph':graph,'p_matrix':p}
        pcmci.PCMCI=PCMCI
        root=ModuleType('tigramite');root.__path__=[]
        root.data_processing=pp
        indep=ModuleType('tigramite.independence_tests');indep.__path__=[]
        indep.parcorr=parcorr;root.independence_tests=indep
        root.pcmci=pcmci
        self.mock=patch.dict(sys.modules,{
            'tigramite':root,'tigramite.data_processing':pp,
            'tigramite.independence_tests':indep,
            'tigramite.independence_tests.parcorr':parcorr,'tigramite.pcmci':pcmci})
        self.metadata=patch.object(engine,'version',return_value=engine.VERSION)
        self.mock.start();self.metadata.start()
        return self
    def __exit__(self,*a):self.metadata.stop();self.mock.stop()


class TestP4E(unittest.TestCase):
    def test_baseline_closed(self):
        _,out,_=run(request());self.assertEqual(out.reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertEqual(out.status,td.TD_REJECTED)
    def test_enabled_but_host_denied(self):
        _,out,_=run(request(),enabled=True);self.assertEqual(out.status,td.TD_REJECTED)
    def test_host_authorized_but_disabled(self):
        _,out,_=run(request(),host_authorized=True);self.assertEqual(out.reason_code,'TEMPORAL_DISCOVERY_DISABLED')
    def test_host_and_enabled_without_worker_policy(self):
        _,out,_=run(request(),host_authorized=True,enabled=True);self.assertEqual(out.status,td.TD_UNAVAILABLE)
    def test_policy_attestation_missing(self):
        pol=engine.TigramiteWorkerPolicy('','','','',enabled=True)
        _,out,_=run(request(),host_authorized=True,enabled=True,policy=pol)
        self.assertEqual(out.reason_code,'HOST_OS_ISOLATION_NOT_ATTESTED')
    def test_bad_backend_pin_denied(self):
        pol=engine.TigramiteWorkerPolicy('','','','',pinned_version='0',enabled=True,host_isolation_attested=True)
        _,out,_=run(request(),host_authorized=True,enabled=True,policy=pol)
        self.assertEqual(out.reason_code,'WORKER_LIBRARY_PIN_MISMATCH')
    def test_bad_source_hash_inconclusive(self):
        pol=engine.TigramiteWorkerPolicy(sys.executable,'bad','bad','bad',enabled=True,host_isolation_attested=True)
        _,out,_=run(request(),host_authorized=True,enabled=True,policy=pol)
        self.assertEqual(out.reason_code,'WORKER_INTEGRITY_MISMATCH')
    def test_real_missing_library_fails_closed(self):
        raw=request().SerializeToString(deterministic=True)
        from importlib.metadata import PackageNotFoundError
        with patch.object(engine,'version',side_effect=PackageNotFoundError('tigramite')):
            reply=td.TemporalDiscoveryResult.FromString(engine._compute_worker(raw))
        # This is real *unavailability*, not a skipped candidate graph.
        self.assertEqual(reply.status,td.TD_UNAVAILABLE)
        self.assertEqual(reply.reason_code,'TIGRAMITE_NOT_INSTALLED')
        self.assertFalse(reply.links)
    @unittest.skipIf(__import__('importlib').util.find_spec('tigramite'),
                     'unavailable subprocess check requires a Tigramite-free interpreter')
    def test_pinned_process_unavailable_result(self):
        py=Path(sys.executable);worker=engine.worker_source();dispatch=Path(engine.__file__)
        pol=engine.TigramiteWorkerPolicy(str(py),engine.sha256_file(py),
            engine.sha256_file(worker),engine.sha256_file(dispatch),
            enabled=True,host_isolation_attested=True)
        # Mock attestation exercises process plumbing; does NOT attest OS.
        _,out,_=run(request(),host_authorized=True,enabled=True,policy=pol)
        self.assertEqual(out.status,td.TD_UNAVAILABLE,out.reason_code)
        self.assertEqual(out.reason_code,'TIGRAMITE_NOT_INSTALLED')
    def test_mode_pcmci_fake_api_contract(self):
        req=request()
        with FakeTigramite('pcmci') as fixture:
            raw=req.SerializeToString(deterministic=True)
            reply=engine._compute_worker(raw)
        out=td.TemporalDiscoveryResult.FromString(reply)
        self.assertEqual(out.status,td.TD_CANDIDATE,out.reason_code)
        self.assertEqual([(x.source,x.target,x.lag,x.marks) for x in out.links],[(0,1,1,'-->')])
        self.assertTrue(engine.verify_temporal_discovery_receipt(raw,reply).request_bound_structure_checked)
        self.assertFalse(out.causal_directions_proven)
        self.assertEqual(fixture.calls[0][1]['fdr_method'],'fdr_bh')
        self.assertEqual(fixture.calls[0][1]['tau_min'],1)
    def test_mode_pcmciplus_fake_api_contract(self):
        req=request(td.TD_PCMCI_PLUS)
        with FakeTigramite('pcmciplus') as fixture:
            raw=req.SerializeToString(deterministic=True);reply=engine._compute_worker(raw)
        out=td.TemporalDiscoveryResult.FromString(reply)
        self.assertEqual(out.status,td.TD_CANDIDATE,out.reason_code)
        self.assertEqual([(x.source,x.target,x.lag,x.marks) for x in out.links],
                         [(0,1,0,'o-o'),(0,1,1,'-->')])
        self.assertTrue(engine.verify_temporal_discovery_receipt(raw,reply).request_bound_structure_checked)
        self.assertEqual(fixture.calls[0][1]['fdr_method'],'none')
    def test_lag_projection_drops_contemporaneous_pcmci(self):
        req=request();g=np.full((2,2,2),'',dtype='<U3');p=np.ones((2,2,2))
        g[0,1,0]='-->';g[1,0,0]='<--';g[0,1,1]='-->'
        self.assertEqual(len(engine._canonical_links(g,p,req)),1)
    def test_contemporaneous_reverse_required(self):
        req=request(td.TD_PCMCI_PLUS);g=np.full((2,2,2),'',dtype='<U3');p=np.ones((2,2,2))
        g[0,1,0]='-->';g[1,0,0]='-->'
        with self.assertRaisesRegex(ValueError,'INCONSISTENT'):
            engine._canonical_links(g,p,req)
    def test_unrecognized_partial_marks_fails(self):
        req=request(td.TD_PCMCI_PLUS);g=np.full((2,2,2),'',dtype='<U3');p=np.ones((2,2,2))
        g[0,1,0]='o->';g[1,0,0]='<-o'
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):
            engine._canonical_links(g,p,req)
    def test_invalid_p_array_rejected(self):
        req=request();g=np.full((2,2,2),'',dtype='<U3');p=np.ones((2,2,2));p[0,1,1]=np.nan;g[0,1,1]='-->'
        with self.assertRaisesRegex(ValueError,'INVALID_SIGNIFICANCE'):
            engine._canonical_links(g,p,req)
    def test_undefined_untested_zero_lag_is_allowed_for_pcmci(self):
        req=request();g=np.full((2,2,2),'',dtype='<U3');p=np.ones((2,2,2))
        p[:,:,0]=np.nan;g[0,1,1]='-->'
        self.assertEqual(len(engine._canonical_links(g,p,req)),1)
    def test_lagged_link_order_is_canonical(self):
        req=request(lag=2);g=np.full((2,2,3),'',dtype='<U3');p=np.ones((2,2,3))
        g[0,1,2]='-->';g[1,0,1]='-->'
        self.assertEqual([(a,b,lag) for a,b,lag,*_ in engine._canonical_links(g,p,req)],
                         [(1,0,1),(0,1,2)])
    def test_wrong_shape_rejected(self):
        req=request();g=np.full((2,2,3),'',dtype='<U3');p=np.ones((2,2,2))
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_ARRAY'):
            engine._canonical_links(g,p,req)
    def test_timestamps_missing_blocked(self):
        req=request();del req.samples.observations[80]
        self.assertRaisesRegex(ValueError,'NONREGULAR_TIMESTAMPS',engine._parse,req.SerializeToString(deterministic=True))
    def test_jitter_blocked(self):
        req=request();req.samples.observations[80].timestamp_ms+=2
        self.assertRaisesRegex(ValueError,'NONREGULAR_TIMESTAMPS',engine._parse,req.SerializeToString(deterministic=True))
    def test_stationarity_acknowledgement_required_not_verification(self):
        req=request();req.stationarity_assumption_acknowledged=False
        self.assertRaisesRegex(ValueError,'INVALID_TEMP_DISCOVERY_REQUEST',engine._parse,req.SerializeToString())
    def test_no_hidden_confounds_proof_in_result(self):
        raw,out=raw_result(request())
        out.causal_assumptions_verified=True
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_no_causal_proof_claim_in_result(self):
        raw,out=raw_result(request());out.causal_directions_proven=True
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_forged_trace_rejected(self):
        raw,out=raw_result(request());out.trace_id='forged'
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_forged_model_version_rejected(self):
        raw,out=raw_result(request());out.backend_version='different'
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_cross_request_digest_rejected(self):
        raw,out=raw_result(request());r2=request();r2.seed=12
        self.assertFalse(engine.verify_temporal_discovery_receipt(r2.SerializeToString(),out.SerializeToString()).request_bound_structure_checked)
    def test_duplicate_link_rejected(self):
        raw,out=raw_result(request());out.links.add().CopyFrom(out.links[0])
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_out_of_bounds_edge_rejected(self):
        raw,out=raw_result(request());out.links[0].source=99
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_invalid_p_value_rejected(self):
        raw,out=raw_result(request());out.links[0].significance='nan'
        self.assertFalse(engine.verify_temporal_discovery_receipt(raw,out.SerializeToString()).request_bound_structure_checked)
    def test_empty_candidate_is_not_a_proof(self):
        raw,out=raw_result(request(),marks=[])
        receipt=engine.verify_temporal_discovery_receipt(raw,out.SerializeToString())
        self.assertTrue(receipt.request_bound_structure_checked)
        self.assertFalse(receipt.independent_causal_proof)
    def test_unserialized_unknown_fields_rejected(self):
        raw=request().SerializeToString(deterministic=True)+b'\xc0\x0c\x01'
        self.assertRaises(ValueError,engine._parse,raw)
    def test_input_size_limit(self):
        self.assertRaises(ValueError,engine._parse,b'z'*(engine.MAX_FRAME+1))
    def test_invalid_tau(self):
        req=request();req.tau_max=3
        self.assertRaises(ValueError,engine._parse,req.SerializeToString())
    def test_bad_alpha(self):
        req=request();req.pc_alpha=math.nan
        self.assertRaises(ValueError,engine._parse,req.SerializeToString())
    def test_existing_p4d_still_denied(self):
        from cognitum.causal_temporal_advanced import run_temporal_advanced_frame
        from cognitum.proto import causal_temporal_advanced_pb2 as adv
        req=adv.TemporalAdvancedRequest(schema_version=1,samples=case(),timeout_ms=5000)
        result=adv.TemporalAdvancedResult.FromString(run_temporal_advanced_frame(req.SerializeToString()))
        self.assertEqual(result.status,adv.ADV_REJECTED)


@unittest.skipUnless(__import__('importlib').util.find_spec('tigramite'),
                     'genuine pinned Tigramite runtime absent; no mature-library claim')
class TestGenuineTigramite(unittest.TestCase):
    def test_real_pcmci_on_synthetic_lagged_process(self):
        from importlib.metadata import version
        self.assertEqual(version('tigramite'),engine.VERSION)
        raw=request().SerializeToString(deterministic=True)
        out=td.TemporalDiscoveryResult.FromString(engine._compute_worker(raw))
        self.assertEqual(out.status,td.TD_CANDIDATE,out.reason_code)
        self.assertFalse(out.causal_directions_proven)
    def test_real_pcmciplus_on_synthetic_process(self):
        from importlib.metadata import version
        self.assertEqual(version('tigramite'),engine.VERSION)
        raw=request(td.TD_PCMCI_PLUS).SerializeToString(deterministic=True)
        out=td.TemporalDiscoveryResult.FromString(engine._compute_worker(raw))
        self.assertEqual(out.status,td.TD_CANDIDATE,out.reason_code)
        self.assertFalse(out.causal_directions_proven)

if __name__=='__main__': unittest.main()
