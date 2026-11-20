"""C13 real-engine compatibility and fail-closed diagnostics (no numerical mocks for positive cases)."""
import random
import subprocess
import sys
import unittest
import warnings
from unittest.mock import patch

from cognitum import probability_diagnostics as d
from cognitum.proto import probability_diagnostics_pb2 as p


def request():
    rng=random.Random(3)
    req=p.DiagnosticsRequest(schema_version=1,trace_id='c13.compat',timeout_ms=20000)
    for name in ('mu','sigma'):
        var=req.parameters.add(parameter=name)
        for _ in range(4):
            var.chains.add().values.extend(rng.gauss(0,1) for _ in range(80))
    return req


def execute(req):
    raw=req.SerializeToString(deterministic=True)
    out=d.run_diagnostics_frame(raw,host_authorized=True,enabled=True)
    return raw,out,p.DiagnosticsResult.FromString(out)


class DiagnosticsCompatibilityTests(unittest.TestCase):
    def assert_unavailable(self, raw, out, res):
        self.assertEqual(res.status,p.DIAGNOSTICS_UNKNOWN)
        self.assertEqual(res.reason_code,'DIAGNOSTICS_UNAVAILABLE')
        self.assertFalse(res.parameters)
        self.assertFalse(res.backend_version)
        self.assertFalse(d.verify_diagnostics_receipt(raw,out).evidence_valid)

    def test_constant_later_parameter_never_publishes_partial_results(self):
        req=request()
        for c in req.parameters[1].chains:
            for i in range(len(c.values)):c.values[i]=2
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            self.assert_unavailable(*execute(req))

    def test_warning_from_actual_backend_boundary_fails_closed(self):
        az,_=d._diagnostics_backend()
        def warn(*args,**kwargs):
            warnings.warn('synthetic numerical failure',RuntimeWarning)
        with patch.object(az,'rhat',warn):
            self.assert_unavailable(*execute(request()))

    def test_missing_backend_fails_closed(self):
        with patch.object(d,'_diagnostics_backend',side_effect=ImportError('missing')):
            self.assert_unavailable(*execute(request()))

    def test_receipt_engine_identity_is_version_bound(self):
        raw,out,res=execute(request())
        self.assertEqual(res.status,p.DIAGNOSTICS_SUCCESS)
        self.assertTrue(d.verify_diagnostics_receipt(raw,out).evidence_valid)
        _,version=d._diagnostics_backend()
        self.assertEqual(res.backend_version,'arviz-'+version)
        res.backend_version='arviz-forged-other-engine'
        self.assertFalse(d.verify_diagnostics_receipt(raw,res.SerializeToString()).evidence_valid)

    def test_fresh_process_real_diagnostics_without_modern_plotting(self):
        program = """
import builtins, random, sys
from cognitum import probability_diagnostics as d
from cognitum.proto import probability_diagnostics_pb2 as p
if sys.version_info >= (3, 12):
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.split('.')[0] in {'arviz','arviz_plots','matplotlib'}:
            raise AssertionError('unexpected plotting import: '+name)
        return original(name,*args,**kwargs)
    builtins.__import__=guarded
rng=random.Random(3)
req=p.DiagnosticsRequest(schema_version=1,trace_id='c13.fresh',timeout_ms=20000)
v=req.parameters.add(parameter='mu')
for _ in range(4):
    v.chains.add().values.extend(rng.gauss(0,1) for _ in range(80))
raw=req.SerializeToString(deterministic=True)
out=d.run_diagnostics_frame(raw,host_authorized=True,enabled=True)
result=p.DiagnosticsResult.FromString(out)
assert result.status==p.DIAGNOSTICS_SUCCESS, result
assert d.verify_diagnostics_receipt(raw,out).evidence_valid
if sys.version_info >= (3, 12):
    assert result.backend_version.startswith('arviz-stats-')
    assert not {'arviz','arviz_plots','matplotlib'}.intersection(sys.modules)
else:
    assert result.backend_version.startswith('arviz-0.23.')
"""
        result=subprocess.run([sys.executable,'-W','error','-c',program],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
