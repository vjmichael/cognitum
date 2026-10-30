"""Actual process gate and deterministic cancellation/revocation race probes."""
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from cognitum.alpha_native import make_call, _parse
from cognitum.alpha_lifecycle import LocalLeaseBoard, LocalTicket, run_guarded
from cognitum.proto import alpha_native_pb2 as pb
from cognitum.proto.capability_pb2 import CalculateRationalResult


class LocalLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.board = LocalLeaseBoard()
        self.ticket = self.board.grant('conv1', 'req1', timeout_ms=5000)
        self.call = make_call('req1', '1/3 + 1/6')

    def test_real_subprocess_delivered_once(self):
        delivered = []
        run_guarded(self.call, self.board, self.ticket, delivered.append)
        self.assertEqual(len(delivered), 1)
        r = _parse(pb.Reply, delivered[0], 16384)
        self.assertEqual(CalculateRationalResult.FromString(r.result_payload).value, '1/2')
        self.assertFalse(r.lu_integrated or r.os_isolation_verified)
        with self.assertRaisesRegex(PermissionError, 'REVOKED_OR_COMPLETED'):
            run_guarded(self.call, self.board, self.ticket, delivered.append)

    def test_no_default_grant_or_forged_ticket(self):
        fake = LocalTicket('fake', 'conv1', 'req1', 0)
        with self.assertRaises(PermissionError):
            run_guarded(self.call, self.board, fake, lambda x: None)
        with self.assertRaisesRegex(PermissionError, 'REQUEST_NOT_ADMITTED'):
            run_guarded(make_call('not-req1', '1'), self.board, self.ticket, lambda x: None)

    def test_cancel_prevents_publish(self):
        self.board.cancel(self.ticket)
        with self.assertRaises(PermissionError):
            run_guarded(self.call, self.board, self.ticket, lambda x: None)

    def test_revoke_terminal_and_generation(self):
        self.board.revoke('conv1')
        with self.assertRaises(PermissionError):
            self.board.grant('conv1','req2')
        with self.assertRaises(PermissionError):
            run_guarded(self.call, self.board, self.ticket, lambda _: None)

    def test_no_duplicate_request(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            self.board.grant('conv1', 'req1')

    def test_sink_held_under_lock_and_recheck(self):
        calls = []
        def sink(wire):
            calls.append(wire)
            self.board.revoke('conv1')  # RLock: revocation runs after this delivery begins
        run_guarded(self.call, self.board, self.ticket, sink)
        self.assertEqual(len(calls), 1)
        with self.assertRaises(PermissionError):
            self.board.grant('conv1', 'req2')

    def test_no_delivery_on_subprocess_crash(self):
        p = []
        with patch('cognitum.alpha_lifecycle.subprocess.Popen') as mocked:
            instance = mocked.return_value
            instance.communicate.return_value = (b'', b'')
            instance.returncode = 1
            instance.poll.return_value = 1
            with self.assertRaisesRegex(ValueError,'FAILED_OR_TOO_LARGE'):
                run_guarded(self.call,self.board,self.ticket,p.append)
        self.assertFalse(p)

    def test_midflight_revoke_cancels_and_kills_worker(self):
        # Only the test intercepts the trusted worker launcher and substitutes
        # a sleeping Python process. The production function never accepts a command.
        real_popen = subprocess.Popen
        started = threading.Event()
        def slow(*args,**kwargs):
            proc = real_popen([sys.executable,'-c','import time;time.sleep(8)'], **kwargs)
            started.set()
            return proc
        errors=[]; published=[]
        with patch('cognitum.alpha_lifecycle.subprocess.Popen',side_effect=slow):
            thread = threading.Thread(target=lambda: self._runner(errors,published))
            thread.start()
            self.assertTrue(started.wait(2))
            self.board.revoke('conv1')
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(published,[])
        self.assertTrue(errors and isinstance(errors[0],PermissionError),errors)

    def _runner(self, errors, published):
        try: run_guarded(self.call,self.board,self.ticket,published.append)
        except Exception as e: errors.append(e)

    def test_short_timeout_kills_slow_child(self):
        ticket=self.board.grant('conv2','req2',timeout_ms=250)
        real_popen = subprocess.Popen
        with patch('cognitum.alpha_lifecycle.subprocess.Popen',
                   side_effect=lambda *a,**kw:real_popen([sys.executable,'-c','import time;time.sleep(8)'],**kw)):
            start=time.monotonic()
            with self.assertRaisesRegex(TimeoutError,'DEADLINE'):
                run_guarded(make_call('req2','1'),self.board,ticket,lambda x:self.fail('published'))
            self.assertLess(time.monotonic()-start,3)

if __name__=='__main__':unittest.main()
