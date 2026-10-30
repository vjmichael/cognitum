"""C12 P2 bounded external planner adapter tests (shim drivers, not FD/UP)."""
from __future__ import annotations
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import threading
import time
import unittest

from cognitum.planning_engines import (ExternalPlannerRuntime, pinned_policy, _parse_plan,
    verify_external_result, make_external_audit, capability_manifest, verify_manifest)
from cognitum.proto import planning_engines_pb2 as e
from tests.test_c12_planning import example, frame


DRIVER='''import sys,time,pathlib
args=sys.argv[1:]
if '--plan-file' in args:
    target=pathlib.Path(args[args.index('--plan-file')+1])
else:
    target=pathlib.Path(args[2])
# Authored test fixture: not a real external planner.
MODE='__MODE__'
if MODE == 'sleep':
    time.sleep(10)
elif MODE == 'fail':
    sys.exit(1)
elif MODE == 'empty':
    target.write_text('\\n')
elif MODE == 'invalid':
    target.write_text('(act3)\\n(act0)\\n')
elif MODE == 'inject':
    target.write_text('(act0)\\n; comment\\n(quit)\\n')
elif MODE == 'non-ascii':
    target.write_bytes(b'\\xff')
elif MODE == 'suboptimal':
    target.write_text('(act3)\\n')
elif MODE == 'anytime':
    target.write_text('(act3)\\n')
    target.with_name(target.name+'.1').write_text('(act0)\\n(act1)\\n(act2)\\n')
else:
    target.write_text('; cost = 7\\n(act0)\\n(act1)\\n(act2)\\n')
'''

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='c12-p2-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.driver=self.root/'driver.py'
        self.driver.write_text(DRIVER.replace('__MODE__','valid'))

    def policy(self, backend='fast-downward', *, enabled=True, mode='valid'):
        self.driver.write_text(DRIVER.replace('__MODE__',mode))
        return pinned_policy(backend,self.driver,enabled=enabled)

    def request(self, backend='fast-downward', timeout=1500):
        req=e.EngineRequest(schema_version=1,classical_request=frame(example()),
                            backend_id=backend,deadline_ms=timeout)
        return req.SerializeToString(deterministic=True)

    def run_result(self, policy,request=None,**kwargs):
        request=request or self.request(policy.backend_id)
        return e.EngineResult.FromString(ExternalPlannerRuntime(policy).execute(request,host_authorized=True,**kwargs))

    def receipt(self, request, result):
        return e.EngineReceipt.FromString(verify_external_result(request,result.SerializeToString(deterministic=True)))

    def test_fast_downward_shim_checkable_plan(self):
        req=self.request();result=self.run_result(self.policy())
        self.assertEqual(result.status,e.VERIFIED_OPTIMAL)
        self.assertEqual(list(result.action_indices),[0,1,2])
        self.assertEqual(result.total_cost,7)
        self.assertTrue(self.receipt(req,result).optimality_verified)

    def test_up_shim_checkable_plan(self):
        req=self.request('unified-planning')
        result=self.run_result(self.policy('unified-planning'),req)
        self.assertEqual(result.status,e.VERIFIED_OPTIMAL)
        self.assertTrue(self.receipt(req,result).evidence_valid)

    def test_anytime_selects_cheapest_checked_plan(self):
        req=self.request();result=self.run_result(self.policy(mode='anytime'))
        self.assertEqual(result.total_cost,7)
        self.assertEqual(list(result.action_indices),[0,1,2])
        self.assertTrue(self.receipt(req,result).evidence_valid)

    def test_suboptimal_reported_as_feasible(self):
        req=self.request();result=self.run_result(self.policy(mode='suboptimal'))
        self.assertEqual(result.status,e.VERIFIED_PLAN)
        self.assertEqual(result.total_cost,20)
        self.assertFalse(result.optimality_verified)
        self.assertTrue(self.receipt(req,result).evidence_valid)

    def test_invalid_action_order_not_accepted(self):
        r=self.run_result(self.policy(mode='invalid'))
        self.assertNotIn(r.status,[e.VERIFIED_OPTIMAL,e.VERIFIED_PLAN])
        self.assertFalse(r.witness_verified)

    def test_text_command_injection_not_accepted(self):
        r=self.run_result(self.policy(mode='inject'))
        self.assertEqual(r.status,e.UNKNOWN)
        self.assertFalse(r.witness_verified)

    def test_non_ascii_not_accepted(self):
        r=self.run_result(self.policy(mode='non-ascii'))
        self.assertEqual(r.status,e.UNKNOWN)

    def test_no_plan_never_certifies_unreachable(self):
        r=self.run_result(self.policy(mode='empty'))
        self.assertEqual(r.status,e.UNKNOWN)
        self.assertFalse(r.optimality_verified)

    def test_nonzero_return_not_certified(self):
        r=self.run_result(self.policy(mode='fail'))
        self.assertEqual(r.status,e.UNKNOWN)

    def test_deadline_terminates_worker(self):
        req=self.request(timeout=60)
        r=self.run_result(self.policy(mode='sleep'),req)
        self.assertEqual(r.reason_code,'HOST_DEADLINE_EXCEEDED')
        self.assertEqual(r.status,e.UNKNOWN)

    def test_cancellation_event(self):
        event=threading.Event();event.set()
        r=self.run_result(self.policy(mode='sleep'),cancel_event=event)
        self.assertEqual(r.reason_code,'HOST_CANCELLED')

    def test_disable_active_worker(self):
        runtime=ExternalPlannerRuntime(self.policy(mode='sleep'))
        out=[]
        thread=threading.Thread(target=lambda: out.append(e.EngineResult.FromString(runtime.execute(self.request(),host_authorized=True))))
        thread.start();time.sleep(.12);runtime.disable();thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertIn(out[0].reason_code,('HOST_CANCELLED','BACKEND_EXECUTION_FAILED'))

    def test_disabled_by_default(self):
        r=self.run_result(self.policy(enabled=False))
        self.assertEqual(r.status,e.REJECTED)
        self.assertEqual(r.reason_code,'BACKEND_DISABLED')

    def test_host_authorization_required(self):
        r=e.EngineResult.FromString(ExternalPlannerRuntime(self.policy()).execute(self.request(),host_authorized=False))
        self.assertEqual(r.reason_code,'HOST_AUTHORIZATION_REQUIRED')

    def test_wrong_backend_denied(self):
        r=self.run_result(self.policy('unified-planning'),self.request('fast-downward'))
        self.assertEqual(r.reason_code,'BACKEND_NOT_HOST_ALLOWED')

    def test_digest_changes_denied(self):
        pol=self.policy();self.driver.write_text('print("changed")')
        r=self.run_result(pol)
        self.assertEqual(r.reason_code,'WORKER_ARTIFACT_MISMATCH')

    def test_up_rejects_incompatible_pyperplan(self):
        pol=self.policy('unified-planning')
        r=self.run_result(replace(pol,search_configuration='pyperplan'),self.request('unified-planning'))
        self.assertEqual(r.reason_code,'UNREVIEWED_SEARCH_CONFIGURATION')

    def test_search_config_not_model_controlled(self):
        p=self.policy()
        r=self.run_result(replace(p,search_configuration='; rm -rf /'))
        self.assertEqual(r.reason_code,'UNREVIEWED_SEARCH_CONFIGURATION')

    def test_invalid_backend_id_rejected(self):
        req=e.EngineRequest(schema_version=1,classical_request=frame(example()),backend_id='research-dream',deadline_ms=1000)
        r=e.EngineResult.FromString(ExternalPlannerRuntime(self.policy()).execute(req.SerializeToString(deterministic=True),host_authorized=True))
        self.assertEqual(r.status,e.REJECTED)

    def test_forged_plan_and_optimality_rejected(self):
        req=self.request();r=self.run_result(self.policy())
        r.action_indices[0]=3
        self.assertFalse(self.receipt(req,r).evidence_valid)
        r=self.run_result(self.policy(mode='suboptimal'))
        r.status=e.VERIFIED_OPTIMAL;r.optimality_verified=True;r.reason_code='INDEPENDENT_FINITE_OPTIMALITY'
        self.assertFalse(self.receipt(req,r).evidence_valid)

    def test_host_pinned_worker_provenance_rechecked(self):
        req=self.request();r=self.run_result(self.policy())
        serialized=r.SerializeToString(deterministic=True)
        check=e.EngineReceipt.FromString(verify_external_result(req,serialized,expected_worker_sha256=r.worker_sha256))
        self.assertTrue(check.evidence_valid)
        bad=e.EngineReceipt.FromString(verify_external_result(req,serialized,expected_worker_sha256=b'X'*32))
        self.assertFalse(bad.evidence_valid)

    def test_forged_worker_or_export_digest_rejected(self):
        req=self.request();r=self.run_result(self.policy())
        r.export_sha256=b'X'*32
        self.assertFalse(self.receipt(req,r).evidence_valid)
        r=self.run_result(self.policy());r.worker_sha256=b'X'*31
        self.assertFalse(self.receipt(req,r).evidence_valid)

    def test_request_rebinding_rejected(self):
        req=self.request();r=self.run_result(self.policy())
        alt=e.EngineRequest.FromString(req);alt.deadline_ms-=1
        self.assertFalse(self.receipt(alt.SerializeToString(deterministic=True),r).evidence_valid)

    def test_audit_data_minimized(self):
        req=self.request();r=self.run_result(self.policy())
        blob=r.SerializeToString(deterministic=True)
        audit=e.EngineAudit.FromString(make_external_audit(req,blob))
        self.assertTrue(audit.evidence_valid)
        self.assertEqual(audit.backend_id,'fast-downward')
        self.assertNotIn(b'at_start',audit.SerializeToString())
        self.assertEqual(audit.request_sha256,hashlib.sha256(req).digest())

    def test_unknown_never_provides_evidence_receipt(self):
        req=self.request();r=self.run_result(self.policy(mode='empty'))
        self.assertFalse(self.receipt(req,r).evidence_valid)

    def test_unverified_unknown_cannot_forge_witness(self):
        req=self.request();r=self.run_result(self.policy(mode='empty'))
        r.witness_verified=True
        self.assertFalse(self.receipt(req,r).evidence_valid)

    def test_manifest_not_runtime_tested(self):
        msg=e.EngineManifest.FromString(capability_manifest())
        self.assertTrue(verify_manifest(capability_manifest()))
        self.assertFalse(any(x.runtime_tested or x.available for x in msg.backends))
        self.assertEqual(len(msg.backends),2)

    def test_plan_text_parser(self):
        self.assertEqual(_parse_plan(b' ;comment\n(act0)\n(act12)\n',20),[0,12])
        for invalid in [b'(ACT0)',b'(act001)',b'(act0 extra)',b'(quit)',b'\xff']:
            with self.assertRaises(ValueError):_parse_plan(invalid,20)


if __name__=='__main__': unittest.main()
