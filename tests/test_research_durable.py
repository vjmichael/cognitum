"""C08/C09 persistent-revision and signer-key revocation negative tests."""
import tempfile
import threading
import time
from pathlib import Path
import unittest
from cognitum.research.durable_integrity import ResearchIntegrityLedger
from cognitum.research.hdc_index_lifecycle import EphemeralDerivedIndex
from cognitum.proto.research_optional_pb2 import HdcCandidates, KanPrediction
from tests.test_c09_signed_approval import SignedKanGate

ROWS=(('candidate1','owns','ship'),('candidate2','owns','station'))
D='a'*64

class HdcDurability(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'integrity.sqlite'
        self.ledger=ResearchIntegrityLedger(self.file)
        self.index=EphemeralDerivedIndex()
        self.ledger.activate_source('source1','rev1',D,expected_epoch=0)
        self.index.install('rev1',ROWS)
    def deliver(self, epoch=0, revision='rev1', digest=D, sink=None):
        return self.ledger.deliver_hdc('source1',epoch,revision,digest,self.index,'owns','ship',2,sink or (lambda _:None))
    def test_valid_and_restart(self):
        seen=[]
        self.deliver(sink=seen.append)
        self.assertEqual(HdcCandidates.FromString(seen[0]).candidate_ids[0],'candidate1')
        self.ledger=ResearchIntegrityLedger(self.file)
        self.deliver()
    def test_tampered_revision_digest_epoch(self):
        for kw in ({'revision':'rev2'},{'digest':'b'*64},{'epoch':1}):
            with self.assertRaises(PermissionError):self.deliver(**kw)
    def test_revision_update_requires_invalidate_and_exact_epoch(self):
        with self.assertRaises(PermissionError):self.ledger.activate_source('source1','rev2','b'*64,expected_epoch=0)
        ep=self.ledger.invalidate_source('source1',reason='EDIT')
        with self.assertRaises(PermissionError):self.deliver()
        with self.assertRaises(PermissionError):self.ledger.activate_source('source1','rev2','b'*64,expected_epoch=ep+1)
        self.ledger.activate_source('source1','rev2','b'*64,expected_epoch=ep)
        self.index.invalidate(reason='EDIT');self.index.install('rev2',ROWS)
        self.deliver(epoch=ep,revision='rev2',digest='b'*64)
        with self.assertRaises(PermissionError):self.deliver()
    def test_scope_revocation_terminal_across_restart(self):
        ep=self.ledger.invalidate_source('source1',reason='SCOPE_REVOKED')
        self.ledger=ResearchIntegrityLedger(self.file)
        with self.assertRaises(PermissionError):self.ledger.activate_source('source1','rev2',D,expected_epoch=ep)
        with self.assertRaises(PermissionError):self.deliver()
    def test_concurrent_invalidation_waits_for_callback(self):
        entered=threading.Event();release=threading.Event();done=threading.Event()
        def sink(_):entered.set();self.assertTrue(release.wait(3))
        t=threading.Thread(target=lambda:self.deliver(sink=sink));t.start();self.assertTrue(entered.wait(3))
        q=threading.Thread(target=lambda:(self.ledger.invalidate_source('source1',reason='DELETE'),done.set()))
        q.start();time.sleep(.08);self.assertFalse(done.is_set());release.set();t.join(3);q.join(3)
        self.assertTrue(done.is_set())
        with self.assertRaises(PermissionError):self.deliver()

class KanDurability(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ledger=ResearchIntegrityLedger(Path(self.tmp.name)/'keys.sqlite')
        self.f=SignedKanGate();self.f.setUp()
    def enroll(self):self.ledger.enroll_signer(self.f.trust,local_host_enrollment=True)
    def test_explicit_enrollment_and_restart_revoke(self):
        with self.assertRaises(PermissionError):self.ledger.enroll_signer(self.f.trust)
        self.enroll()
        actual=self.ledger.predict_kan('research-signer',self.f.req,self.f.data,self.f.policy,self.f.sign())
        self.assertFalse(KanPrediction.FromString(actual).grants_authority)
        self.ledger.revoke_signer('research-signer')
        self.ledger=ResearchIntegrityLedger(self.ledger.file)
        with self.assertRaises(PermissionError):self.ledger.predict_kan('research-signer',self.f.req,self.f.data,self.f.policy,self.f.sign())
        with self.assertRaises(PermissionError):self.enroll()
    def test_unknown_signer_and_key_replacement_rejected(self):
        self.enroll()
        with self.assertRaises(PermissionError):self.ledger.predict_kan('other',self.f.req,self.f.data,self.f.policy,self.f.sign())
        with self.assertRaises(PermissionError):self.enroll()
    def test_invalid_signature_and_optin_preserved(self):
        self.enroll()
        with self.assertRaises(ValueError):self.ledger.predict_kan('research-signer',self.f.req,self.f.data,self.f.policy,b'bad')
        from cognitum.research.kan_optional import ResearchPolicy
        with self.assertRaises(PermissionError):self.ledger.predict_kan('research-signer',self.f.req,self.f.data,ResearchPolicy(),self.f.sign())

if __name__=='__main__':unittest.main()
