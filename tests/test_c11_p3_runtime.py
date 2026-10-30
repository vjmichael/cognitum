"""C11 P3 focused execution-boundary, audit and lifecycle smoke tests."""
import hashlib
from pathlib import Path
import tempfile
import threading
import time
import unittest

from cognitum.optimization_runtime import (
    OptimizationWorkerRuntime, WorkerPolicy, capability_manifest,
    fixed_worker_policy, verify_execution_shape, verify_manifest,
)
from cognitum.proto import optimization_runtime_pb2 as rt, workflows_pb2 as wf
from tests.test_c11_workflows import assignment, packing, flow, routing, scheduling, wire


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.frame = wire(assignment())

    def run_host(self, frame=None, policy=None, authorized=True):
        runner=OptimizationWorkerRuntime(policy or fixed_worker_policy(enabled=True))
        data=frame if frame is not None else self.frame
        output=runner.execute(data,host_authorized=authorized)
        return rt.ExecutionEnvelope.FromString(output), output

    def test_manifest_fixed_and_digest_checked(self):
        data=capability_manifest()
        self.assertTrue(verify_manifest(data))
        m=rt.CapabilityManifest.FromString(data)
        self.assertEqual(len(m.backends),8)
        self.assertEqual(sum(x.maturity==rt.RESEARCH_CANDIDATE for x in m.backends),2)
        self.assertTrue(all(x.opt_in_required and not x.available_in_p2 for x in m.backends if x.maturity==rt.RESEARCH_CANDIDATE))
        m.backends[0].implementation='forged'
        self.assertFalse(verify_manifest(wire(m)))
        self.assertFalse(verify_manifest(data+b'\x08\x01'))

    def test_denied_by_default_without_spawn(self):
        rec,packet=self.run_host(authorized=False)
        self.assertEqual(rec.record.outcome,rt.DENIED)
        self.assertEqual(rec.record.reason_code,'HOST_AUTHORIZATION_REQUIRED')
        self.assertTrue(verify_execution_shape(self.frame,packet))
        self.assertFalse(rec.result_frame)

    def test_host_disabled_without_spawn(self):
        rec,packet=self.run_host(policy=fixed_worker_policy())
        self.assertEqual(rec.record.reason_code,'WORKER_DISABLED')
        self.assertTrue(verify_execution_shape(self.frame,packet))

    def test_corrupt_worker_digest_denied(self):
        policy=fixed_worker_policy(enabled=True)
        policy=WorkerPolicy(policy.worker_script,'0'*64,enabled=True)
        rec,_=self.run_host(policy=policy)
        self.assertEqual(rec.record.reason_code,'WORKER_ARTIFACT_MISMATCH')

    def test_request_cannot_select_experimental_backend(self):
        req=packing();req.backend_id='research-neighborhood-search'
        frame=wire(req)
        rec,packet=self.run_host(frame)
        self.assertEqual(rec.record.outcome,rt.DENIED)
        self.assertTrue(verify_execution_shape(frame,packet))

    def test_host_allowlist_rejects_even_supported_backend(self):
        policy=fixed_worker_policy(enabled=True)
        policy=WorkerPolicy(policy.worker_script,policy.expected_sha256,enabled=True,allowed_backends=())
        rec,_=self.run_host(policy=policy)
        self.assertEqual(rec.record.reason_code,'BACKEND_NOT_HOST_ALLOWED')

    def test_request_cannot_pass_arbitrary_paths(self):
        req=assignment();req.backend_id='../../tmp/evil.py'
        rec,_=self.run_host(wire(req))
        self.assertEqual(rec.record.outcome,rt.DENIED)

    def test_live_assignment_rechecked(self):
        rec,packet=self.run_host()
        self.assertEqual(rec.record.outcome,rt.COMPLETED)
        self.assertTrue(rec.record.witness_verified)
        self.assertTrue(rec.record.optimality_verified)
        self.assertTrue(verify_execution_shape(self.frame,packet))
        self.assertFalse(rec.record.host_approved)
        self.assertEqual(rec.record.request_sha256,hashlib.sha256(self.frame).digest())
        self.assertEqual(wf.WorkflowResult.FromString(rec.result_frame).objective_value,15)

    def test_all_mature_families_in_worker(self):
        for req in (packing(),flow(),scheduling(),routing()):
            frame=wire(req)
            with self.subTest(req=req.WhichOneof('problem')):
                env,packet=self.run_host(frame)
                self.assertEqual(env.record.outcome,rt.COMPLETED,env.record.reason_code)
                self.assertTrue(verify_execution_shape(frame,packet))
                self.assertTrue(env.record.witness_verified)

    def test_tampered_record_and_receipt_rejected(self):
        env,_=self.run_host()
        env.record.optimality_verified=False
        self.assertFalse(verify_execution_shape(self.frame,wire(env)))
        env,_=self.run_host()
        env.record.host_approved=True
        self.assertFalse(verify_execution_shape(self.frame,wire(env)))
        env,_=self.run_host()
        env.receipt_frame=b'forged'
        self.assertFalse(verify_execution_shape(self.frame,wire(env)))

    def test_request_swap_rejected(self):
        env,packet=self.run_host()
        self.assertFalse(verify_execution_shape(wire(packing()),packet))

    def test_oversized_request_denied(self):
        env,_=self.run_host(b'a'*70000)
        self.assertEqual(env.record.outcome,rt.DENIED)

    def test_denial_forged_witness_rejected(self):
        env,_=self.run_host(authorized=False)
        env.record.witness_verified=True
        self.assertFalse(verify_execution_shape(self.frame,wire(env)))

    @staticmethod
    def _fixture_policy(contents):
        directory=tempfile.TemporaryDirectory()
        path=Path(directory.name)/'worker.py'
        path.write_text(contents)
        return directory, WorkerPolicy(path,hashlib.sha256(path.read_bytes()).hexdigest(),enabled=True)

    def test_deadline_kills_slow_worker(self):
        directory,policy=self._fixture_policy('import time\ntime.sleep(10)\n')
        try:
            req=assignment();req.timeout_ms=100
            env,packet=self.run_host(wire(req),policy)
            self.assertEqual(env.record.outcome,rt.TIMED_OUT)
            self.assertTrue(verify_execution_shape(wire(req),packet))
        finally:
            directory.cleanup()

    def test_host_cancellation_kills_process(self):
        directory,policy=self._fixture_policy('import time\ntime.sleep(10)\n')
        event=threading.Event()
        try:
            runner=OptimizationWorkerRuntime(policy)
            def cancel():
                time.sleep(.09)
                event.set()
            thread=threading.Thread(target=cancel,daemon=True);thread.start()
            env=rt.ExecutionEnvelope.FromString(runner.execute(self.frame,host_authorized=True,cancel_event=event))
            thread.join(timeout=1)
            self.assertEqual(env.record.outcome,rt.CANCELLED)
        finally:
            directory.cleanup()

    def test_host_disable_inflight_kills_process(self):
        directory,policy=self._fixture_policy('import time\ntime.sleep(10)\n')
        try:
            runner=OptimizationWorkerRuntime(policy)
            holder={}
            def run():holder['env']=rt.ExecutionEnvelope.FromString(runner.execute(self.frame,host_authorized=True))
            th=threading.Thread(target=run,daemon=True);th.start()
            time.sleep(.1);runner.disable();th.join(timeout=3)
            self.assertFalse(th.is_alive())
            self.assertEqual(holder['env'].record.outcome,rt.CANCELLED)
            next_result=rt.ExecutionEnvelope.FromString(runner.execute(self.frame,host_authorized=True))
            self.assertEqual(next_result.record.reason_code,'WORKER_DISABLED')
        finally:
            directory.cleanup()

    def test_failing_worker_returns_process_failed(self):
        directory,policy=self._fixture_policy('raise SystemExit(9)\n')
        try:
            env,_=self.run_host(policy=policy)
            self.assertEqual(env.record.outcome,rt.PROCESS_FAILED)
            self.assertFalse(env.result_frame)
        finally:
            directory.cleanup()

    def test_wrong_output_rejected(self):
        directory,policy=self._fixture_policy('import sys\nsys.stdout.buffer.write(b"not-protobuf")\n')
        try:
            env,_=self.run_host(policy=policy)
            self.assertEqual(env.record.outcome,rt.RESULT_REJECTED)
        finally:
            directory.cleanup()


if __name__=='__main__':unittest.main()
