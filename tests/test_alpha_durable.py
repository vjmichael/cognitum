"""P3 SQLite durable-alpha lifecycle and fail-closed experiments."""
import tempfile
import threading
import time
from pathlib import Path
import unittest
from cognitum.alpha_durable import DurableRequestLedger

class DurableTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'host.sqlite'
        self.host=DurableRequestLedger(self.path)

    def test_default_deny(self):
        with self.assertRaises(PermissionError):self.host.issue('a','r')
        with self.assertRaises(PermissionError):self.host.start('a','r',0)
        with self.assertRaises(ValueError):DurableRequestLedger(Path(':memory:'))

    def test_deliver_once_and_replay_denied_after_restart(self):
        e=self.host.issue('a','r',local_host_approval=True)
        self.host.start('a','r',e)
        seen=[]
        self.host.publish_once('a','r',e,b'ok',seen.append)
        self.assertEqual(seen,[b'ok'])
        self.assertEqual(DurableRequestLedger(self.path).status('a','r'),'DELIVERED')
        with self.assertRaises(PermissionError):self.host.publish_once('a','r',e,b'ok',seen.append)
        with self.assertRaises(ValueError):self.host.issue('a','r',local_host_approval=True)

    def test_crash_recovery_aborts_running(self):
        e=self.host.issue('a','r',local_host_approval=True)
        self.host.start('a','r',e)
        recovered=DurableRequestLedger(self.path)
        self.assertEqual(recovered.status('a','r'),'ABORTED')
        with self.assertRaises(PermissionError):recovered.publish_once('a','r',e,b'ok',lambda _:self.fail('published'))

    def test_revocation_terminal_after_restart(self):
        e=self.host.issue('a','r',local_host_approval=True)
        self.host.start('a','r',e)
        self.host.revoke('a')
        restarted=DurableRequestLedger(self.path)
        self.assertEqual(restarted.status('a','r'),'ABORTED')
        with self.assertRaises(PermissionError):restarted.issue('a','r2',local_host_approval=True)
        with self.assertRaises(PermissionError):restarted.publish_once('a','r',e,b'ok',lambda _:None)

    def test_bad_epoch_and_unstarted_rejected(self):
        e=self.host.issue('a','r',local_host_approval=True)
        with self.assertRaises(PermissionError):self.host.start('a','r',e+1)
        with self.assertRaises(PermissionError):self.host.publish_once('a','r',e,b'ok',lambda _:None)
        self.host.start('a','r',e)
        with self.assertRaises(PermissionError):self.host.start('a','r',e)

    def test_sink_failure_consumes_request(self):
        e=self.host.issue('a','r',local_host_approval=True)
        self.host.start('a','r',e)
        def bad(_):raise RuntimeError('partial')
        with self.assertRaises(RuntimeError):self.host.publish_once('a','r',e,b'ok',bad)
        self.assertEqual(self.host.status('a','r'),'FAILED')
        with self.assertRaises(PermissionError):self.host.publish_once('a','r',e,b'ok',lambda _:None)

    def test_revocation_serialized_behind_delivery(self):
        e=self.host.issue('a','r',local_host_approval=True)
        self.host.start('a','r',e)
        inside=threading.Event(); release=threading.Event(); seen=[]
        def sink(v): inside.set(); self.assertTrue(release.wait(3)); seen.append(v)
        t=threading.Thread(target=lambda:self.host.publish_once('a','r',e,b'ok',sink))
        t.start();self.assertTrue(inside.wait(3))
        revoked=threading.Event()
        q=threading.Thread(target=lambda:(self.host.revoke('a'),revoked.set()))
        q.start();time.sleep(.08);self.assertFalse(revoked.is_set())
        release.set();t.join(3);q.join(3)
        self.assertEqual(seen,[b'ok']);self.assertTrue(revoked.is_set())
        self.assertEqual(self.host.status('a','r'),'DELIVERED')
        with self.assertRaises(PermissionError):self.host.issue('a','r2',local_host_approval=True)

    def test_invalid_paths_result_and_sink(self):
        e=self.host.issue('a','r',local_host_approval=True)
        self.host.start('a','r',e)
        for bad in [b'',b'x'*16385,'string']:
            with self.assertRaises(ValueError):self.host.publish_once('a','r',e,bad,lambda _:None)
        with self.assertRaises(ValueError):self.host.publish_once('a','r',e,b'ok',None)
        self.assertEqual(self.host.status('a','r'),'RUNNING')

if __name__=='__main__':unittest.main()

class DurableSubprocessIntegration(unittest.TestCase):
    def test_real_worker_journalled_once(self):
        from cognitum.alpha_durable import run_journalled
        from cognitum.alpha_lifecycle import LocalLeaseBoard
        from cognitum.alpha_native import make_call
        from cognitum.proto.alpha_native_pb2 import Reply
        with tempfile.TemporaryDirectory() as root:
            ledger=DurableRequestLedger(Path(root)/'state.sqlite')
            board=LocalLeaseBoard();ticket=board.grant('conv1','req1',timeout_ms=5000)
            epoch=ledger.issue('conv1','req1',local_host_approval=True)
            captured=[]
            run_journalled(make_call('req1','1/3+1/6'),board,ticket,ledger,epoch,captured.append)
            self.assertEqual(len(captured),1)
            self.assertEqual(Reply.FromString(captured[0]).status,Reply.COMPLETED)
            self.assertEqual(DurableRequestLedger(ledger.path).status('conv1','req1'),'DELIVERED')
            with self.assertRaises(PermissionError):
                run_journalled(make_call('req1','1'),board,ticket,ledger,epoch,captured.append)

    def test_durable_revoke_prevents_real_worker_launch(self):
        from cognitum.alpha_durable import run_journalled
        from cognitum.alpha_lifecycle import LocalLeaseBoard
        from cognitum.alpha_native import make_call
        with tempfile.TemporaryDirectory() as root:
            ledger=DurableRequestLedger(Path(root)/'state.sqlite')
            board=LocalLeaseBoard();ticket=board.grant('conv1','req1',timeout_ms=5000)
            epoch=ledger.issue('conv1','req1',local_host_approval=True)
            ledger.revoke('conv1')
            with self.assertRaises(PermissionError):
                run_journalled(make_call('req1','1'),board,ticket,ledger,epoch,lambda _:self.fail('published'))
