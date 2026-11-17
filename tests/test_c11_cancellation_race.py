"""Real subprocess regression: disable must not own worker pipe I/O."""
import subprocess
import threading
import unittest
from unittest.mock import patch

from cognitum.optimization_runtime import OptimizationWorkerRuntime, verify_execution_shape
from cognitum.proto import optimization_runtime_pb2 as rt
from tests import test_c11_p3_runtime as fixtures


class CancellationRaceTests(unittest.TestCase):
    def test_disable_during_communicate_has_one_pipe_owner(self):
        case = fixtures.RuntimeTests()
        case.setUp()
        directory, policy = case._fixture_policy('import time\ntime.sleep(10)\n')
        self.addCleanup(directory.cleanup)
        runner = OptimizationWorkerRuntime(policy)
        entered, release, overlap = threading.Event(), threading.Event(), threading.Event()
        owner, holder, children = [], {}, []
        original = subprocess.Popen.communicate

        def tracked(child, *args, **kwargs):
            tid = threading.get_ident()
            if not owner:
                owner.append(tid)
                children.append(child)
                entered.set()
                if not release.wait(3):
                    raise AssertionError('test failed to release communication barrier')
            elif tid != owner[0]:
                overlap.set()
                release.set()
            return original(child, *args, **kwargs)

        def run():
            holder['frame'] = runner.execute(case.frame, host_authorized=True)

        with patch.object(subprocess.Popen, 'communicate', tracked):
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                runner.disable()
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(overlap.is_set(), 'disable called communicate on the execute-owned child')
        self.assertIsNotNone(children[0].poll(), 'worker was not reaped')
        frame = holder['frame']
        reply = rt.ExecutionEnvelope.FromString(frame)
        self.assertEqual(reply.record.outcome, rt.CANCELLED)
        self.assertEqual(reply.record.reason_code, 'HOST_CANCELLED')
        self.assertFalse(reply.result_frame or reply.receipt_frame)
        self.assertTrue(verify_execution_shape(case.frame, frame))
        denied = rt.ExecutionEnvelope.FromString(runner.execute(case.frame, host_authorized=True))
        self.assertEqual(denied.record.reason_code, 'WORKER_DISABLED')

    def test_disable_during_validation_prevents_spawn(self):
        from cognitum import optimization_runtime as runtime
        case = fixtures.RuntimeTests()
        case.setUp()
        runner = OptimizationWorkerRuntime(runtime.fixed_worker_policy(enabled=True))
        entered, release = threading.Event(), threading.Event()
        holder = {}
        original = runtime._validate

        def blocked(req):
            entered.set()
            if not release.wait(10):
                raise AssertionError('validation barrier not released')
            return original(req)

        def run():
            holder['frame'] = runner.execute(case.frame, host_authorized=True)

        with patch.object(runtime, '_validate', blocked), patch.object(subprocess, 'Popen', wraps=subprocess.Popen) as spawn:
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            try:
                self.assertTrue(entered.wait(10))
                runner.disable()
            finally:
                release.set()
                thread.join(10)
            self.assertFalse(thread.is_alive())
            spawn.assert_not_called()
        reply = rt.ExecutionEnvelope.FromString(holder['frame'])
        self.assertEqual((reply.record.outcome, reply.record.reason_code), (rt.DENIED, 'WORKER_DISABLED'))
        self.assertTrue(verify_execution_shape(case.frame, holder['frame']))

    def test_cancellation_during_verification_discards_valid_result(self):
        from cognitum import optimization_runtime as runtime
        req = fixtures.assignment()
        req.timeout_ms = 5000
        frame = fixtures.wire(req)
        original = runtime.verify_workflow_frame
        for disable in (True, False):
            with self.subTest(disable=disable):
                runner = OptimizationWorkerRuntime(runtime.fixed_worker_policy(enabled=True))
                entered, release, cancel = threading.Event(), threading.Event(), threading.Event()
                holder = {}

                def blocked(request, output):
                    receipt = original(request, output)
                    entered.set()
                    if not release.wait(10):
                        raise AssertionError('verification barrier not released')
                    return receipt

                def run():
                    holder['frame'] = runner.execute(frame, host_authorized=True, cancel_event=cancel)

                with patch.object(runtime, 'verify_workflow_frame', blocked):
                    thread = threading.Thread(target=run, daemon=True)
                    thread.start()
                    try:
                        self.assertTrue(entered.wait(10))
                        if disable:
                            runner.disable()
                        else:
                            cancel.set()
                    finally:
                        release.set()
                        thread.join(10)
                self.assertFalse(thread.is_alive())
                packet = holder['frame']
                reply = rt.ExecutionEnvelope.FromString(packet)
                self.assertEqual((reply.record.outcome, reply.record.reason_code), (rt.CANCELLED, 'HOST_CANCELLED'))
                self.assertFalse(reply.result_frame or reply.receipt_frame or reply.record.result_sha256 or reply.record.receipt_sha256)
                self.assertTrue(verify_execution_shape(frame, packet))
