"""Real-source acceptance tests, enabled only in an interpreter with Tigramite 5.2.10.1.

The host attestation parameter in the subprocess test is a TEST FIXTURE ONLY.
It does not certify a native Windows Job Object or Lu's authorization.
"""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys
import unittest
from cognitum import causal_tigramite_backend as engine
from cognitum.proto import causal_temporal_discovery_pb2 as td
from tests.test_c14_p4e_tigramite import request

try:
    LIB_PRESENT = version('tigramite') == engine.VERSION
except PackageNotFoundError:
    LIB_PRESENT = False

@unittest.skipUnless(LIB_PRESENT, 'real Tigramite 5.2.10.1 not installed in this interpreter')
class TestUploadedTigramite(unittest.TestCase):
    def _run(self, mode, direct):
        raw = request(mode).SerializeToString(deterministic=True)
        if direct:
            reply = engine._compute_worker(raw)
        else:
            py = Path(sys.executable)
            policy = engine.TigramiteWorkerPolicy(
                str(py), engine.sha256_file(py),
                engine.sha256_file(engine.worker_source()),
                engine.sha256_file(Path(engine.__file__)),
                enabled=True,
                host_isolation_attested=True,  # synthetic contract test, not OS attestation
            )
            reply = engine.run_temporal_discovery_frame(
                raw, host_authorized=True, enabled=True, policy=policy)
        out = td.TemporalDiscoveryResult.FromString(reply)
        self.assertEqual(out.status, td.TD_CANDIDATE, out.reason_code)
        self.assertEqual(out.backend_version, engine.VERSION)
        self.assertEqual(out.reason_code, 'PARTIAL_CAUSAL_GRAPH_CANDIDATE_NOT_PROOF')
        self.assertTrue(engine.verify_temporal_discovery_receipt(raw, reply).request_bound_structure_checked)
        self.assertFalse(out.causal_directions_proven)
        self.assertFalse(out.causal_assumptions_verified)
        self.assertIn((0, 1, 1, '-->'),
                      [(x.source, x.target, x.lag, x.marks) for x in out.links])
        return out

    def _negative_controls(self, mode):
        from tests.test_c14_p4a_temporal import case as temporal_case
        for seed in (43, 66, 99):
            req = request(mode)
            null = temporal_case(seed=seed, related=False)
            for row, generated in zip(req.samples.observations, null.observations):
                row.values[:] = generated.values
            raw = req.SerializeToString(deterministic=True)
            reply = engine._compute_worker(raw)
            out = td.TemporalDiscoveryResult.FromString(reply)
            self.assertEqual(out.status, td.TD_CANDIDATE, out.reason_code)
            self.assertTrue(engine.verify_temporal_discovery_receipt(raw, reply).request_bound_structure_checked)
            self.assertFalse([(x.source,x.target,x.lag) for x in out.links
                              if x.source != x.target], f'seed={seed}')

    def test_independent_negative_controls_pcmci(self):
        self._negative_controls(td.TD_PCMCI_LAGGED)

    def test_independent_negative_controls_pcmciplus(self):
        self._negative_controls(td.TD_PCMCI_PLUS)

    def test_real_pcmci_direct(self): self._run(td.TD_PCMCI_LAGGED, True)
    def test_real_pcmciplus_direct(self): self._run(td.TD_PCMCI_PLUS, True)
    def test_real_pcmci_subprocess(self): self._run(td.TD_PCMCI_LAGGED, False)
    def test_real_pcmciplus_subprocess(self): self._run(td.TD_PCMCI_PLUS, False)
    def test_subprocess_still_denied_by_default(self):
        raw=request().SerializeToString(deterministic=True)
        out=td.TemporalDiscoveryResult.FromString(engine.run_temporal_discovery_frame(raw))
        self.assertEqual(out.status,td.TD_REJECTED)
        self.assertEqual(out.reason_code,'HOST_AUTHORIZATION_REQUIRED')
    def test_host_approved_but_no_containment_denied(self):
        raw=request().SerializeToString(deterministic=True)
        py=Path(sys.executable)
        policy=engine.TigramiteWorkerPolicy(
            str(py),engine.sha256_file(py),engine.sha256_file(engine.worker_source()),
            engine.sha256_file(Path(engine.__file__)),enabled=True,host_isolation_attested=False)
        out=td.TemporalDiscoveryResult.FromString(engine.run_temporal_discovery_frame(
            raw,host_authorized=True,enabled=True,policy=policy))
        self.assertEqual(out.status,td.TD_REJECTED)
        self.assertEqual(out.reason_code,'HOST_OS_ISOLATION_NOT_ATTESTED')

if __name__=='__main__': unittest.main()
