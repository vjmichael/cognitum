"""C07/P2 security regression: offline mock host, never a Lu authenticator."""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from cognitum.proto import state_pb2 as p
from cognitum.state_revision import StateLedger, StateConflict, StateInvalid
from cognitum.state_host_gate import SourceUnavailable
from tests.test_c07_state_revision import evt


class FakeHostLease:
    """TEST-ONLY policy source. Production must use Lu host-owned records."""
    def __init__(self, allowed=('chat1',), origins=(p.USER_VERIFIED,p.HOST_OBSERVED), active=True):
        self.allowed = set(allowed)
        self.origins = set(origins)
        self.active = active
        self.live = {'chat1': ('2','a'*64)}
        self.retained = {('chat1','2','a'*64)}
        self.snapshots = {'chat1':'snap1'}
        self.admit_calls = []
        self.verify_calls = []
        self.mutate = False

    def ensure_active(self):
        return self.active

    def admit_event(self, scope_id, event):
        self.admit_calls.append(event.event_id)
        if self.mutate:
            event.origin = p.USER_VERIFIED if event.origin == p.MODEL_HYPOTHESIS else p.MODEL_HYPOTHESIS
        return (self.active and scope_id == 'proj1' and event.origin in self.origins
                and event.source.session_id in self.allowed)

    def verify_source(self, scope_id, source, require_current):
        self.verify_calls.append((source.session_id, source.revision_entry_id, require_current))
        retained = (source.session_id,source.revision_entry_id,source.content_sha256) in self.retained
        current = self.live.get(source.session_id) == (
            source.revision_entry_id,source.content_sha256)
        return (self.active and scope_id == 'proj1'
                and source.session_id in self.allowed and retained
                and self.snapshots.get(source.session_id) == source.snapshot_id
                and (not require_current or current))


def with_source(event, session='chat1', revision='2', digest='a'*64):
    event.source.session_id = session
    event.source.revision_entry_id = revision
    event.source.content_sha256 = digest
    return event


class C07HostP2Tests(unittest.TestCase):
    def setUp(self):
        self.ledger = StateLedger('proj1', require_host=True)
        self.host = FakeHostLease()

    def show(self):
        result = []
        self.ledger.publish_host_fenced(self.host, result.append)
        self.assertEqual(len(result), 1)
        return p.StateProjection.FromString(result[0])

    def test_no_unfenced_read_or_write_in_production_mode(self):
        with self.assertRaises(StateInvalid): self.ledger.apply(evt())
        with self.assertRaises(StateInvalid): self.ledger.apply_batch([evt()])
        with self.assertRaises(StateInvalid): self.ledger.projection()
        self.assertFalse(self.ledger.history())

    def test_host_verified_cas_and_publish(self):
        self.assertEqual(self.ledger.apply_host_batch([evt()], self.host), 1)
        self.assertEqual(self.show().claims[0].value_text, 'draft')
        self.assertEqual(self.ledger.apply_host_batch([evt()], self.host), 0)
        self.assertEqual(len(self.ledger.history()),1)

    def test_rejects_cross_conversation_source_without_consent(self):
        source = with_source(evt(),session='chat2')
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([source],self.host)
        self.assertFalse(self.ledger.history())
        self.host.allowed.add('chat2')
        self.host.live['chat2']=('2','a'*64)
        self.host.snapshots['chat2']='snap1'
        self.host.retained.add(('chat2','2','a'*64))
        self.assertEqual(self.ledger.apply_host_batch([source],self.host),1)

    def test_source_deleted_after_admission_cannot_publish(self):
        self.ledger.apply_host_batch([evt()],self.host)
        self.host.retained.remove(('chat1','2','a'*64))
        disclosed=[]
        with self.assertRaises(SourceUnavailable):
            self.ledger.publish_host_fenced(self.host,disclosed.append)
        self.assertFalse(disclosed)
        self.assertEqual(len(self.ledger.history()),1) # immutable audit retained

    def test_source_revision_changed_after_admission(self):
        self.ledger.apply_host_batch([evt()],self.host)
        self.host.live['chat1']=('3','a'*64)
        self.host.retained.add(('chat1','3','a'*64))
        with self.assertRaises(SourceUnavailable): self.show()

    def test_stale_source_snapshot_cannot_admit_or_publish(self):
        stale = evt()
        stale.source.snapshot_id='bad_snapshot'
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([stale], self.host)
        self.ledger.apply_host_batch([evt()],self.host)
        self.host.snapshots['chat1']='snap-new'
        with self.assertRaises(SourceUnavailable): self.show()

    def test_deleted_secondary_challenge_source_blocks_publication(self):
        self.ledger.apply_host_batch([evt()],self.host)
        second = with_source(evt('e2',action=p.CHALLENGE,rev=1,time=2000),revision='3',digest='b'*64)
        self.host.live['chat1']=('3','b'*64)
        self.host.retained.add(('chat1','3','b'*64))
        self.ledger.apply_host_batch([second],self.host)
        # The disputed claim still carries original source 2. Both the
        # original and the challenge source must be live for publication.
        self.host.retained.remove(('chat1','3','b'*64))
        with self.assertRaises(SourceUnavailable): self.show()

    def test_source_content_changed_without_revision_change(self):
        self.ledger.apply_host_batch([evt()],self.host)
        self.host.live['chat1']=('2','b'*64)
        self.host.retained.add(('chat1','2','b'*64))
        with self.assertRaises(SourceUnavailable): self.show()

    def test_revocation_blocks_retrieval_and_new_events(self):
        self.ledger.apply_host_batch([evt()],self.host)
        self.host.active = False
        with self.assertRaises(SourceUnavailable): self.show()
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([evt('e2',action=p.CONFIRM,rev=1,time=2000)], self.host)
        self.assertEqual(len(self.ledger.history()),1)

    def test_legitimate_revision_head_change_keeps_verified_history(self):
        self.ledger.apply_host_batch([evt()],self.host)
        changed=with_source(evt('e2',action=p.SUPERSEDE,rev=1,value='final',time=2000),revision='3',digest='b'*64)
        self.host.live['chat1']=('3','b'*64)
        self.host.retained.add(('chat1','3','b'*64))
        self.ledger.apply_host_batch([changed],self.host)
        self.assertEqual(self.show().claims[0].value_text,'final')
        self.assertIn(('chat1','2',False), self.host.verify_calls)
        self.assertIn(('chat1','3',True), self.host.verify_calls)

    def test_deleted_ancestor_blocks_derived_current_even_if_latest_live(self):
        self.ledger.apply_host_batch([evt()],self.host)
        changed=with_source(evt('e2',action=p.SUPERSEDE,rev=1,value='final',time=2000),revision='3',digest='b'*64)
        self.host.live['chat1']=('3','b'*64)
        self.host.retained.add(('chat1','3','b'*64))
        self.ledger.apply_host_batch([changed], self.host)
        self.host.retained.remove(('chat1','2','a'*64))
        with self.assertRaises(SourceUnavailable): self.show()

    def test_atomic_batch_with_foreign_source(self):
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([evt(),with_source(evt('e2',claim_id='c2'),session='foreign')],self.host)
        self.assertFalse(self.ledger.history())
        self.assertEqual(self.ledger._claims,{})

    def test_fake_host_cannot_admit_hypothesis_as_user(self):
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([evt(origin=p.MODEL_HYPOTHESIS)],self.host)
        self.assertFalse(self.ledger.history())

    def test_untrusted_callback_mutation_cannot_swap_origin(self):
        self.host.mutate=True
        with self.assertRaises((SourceUnavailable,StateInvalid)):
            self.ledger.apply_host_batch([evt()],self.host)
        self.assertFalse(self.ledger.history())

    def test_void_verdict_and_broken_host_fail_closed(self):
        class BadHost(FakeHostLease):
            def ensure_active(self): return None
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([evt()], BadHost())
        self.ledger.apply_host_batch([evt()],self.host)
        class LeakyHost(FakeHostLease):
            def verify_source(self,*args): raise RuntimeError('secret user content!')
        with self.assertRaises(SourceUnavailable) as raised:
            self.ledger.publish_host_fenced(LeakyHost(),lambda b: self.fail('published'))
        self.assertNotIn('secret',str(raised.exception))

    def test_failed_publication_does_not_emit_partial_projection(self):
        self.ledger.apply_host_batch([evt()], self.host)
        self.host.verify_source=lambda scope,source: False
        published=[]
        with self.assertRaises(SourceUnavailable):
            self.ledger.publish_host_fenced(self.host,published.append)
        self.assertEqual(published,[])

    def test_reentrant_publication_callback_cannot_mutate(self):
        self.ledger.apply_host_batch([evt()], self.host)
        def deliver(_data):
            self.ledger.apply_host_batch([evt('e2','c2')], self.host)
        with self.assertRaises(StateInvalid):
            self.ledger.publish_host_fenced(self.host,deliver)
        self.assertEqual(len(self.ledger.history()),1)
        self.show()  # callback-guard released after exception

    def test_reentrant_host_verifier_cannot_mutate(self):
        self.ledger.apply_host_batch([evt()], self.host)
        def verify(_scope,_src):
            self.ledger.apply(evt('e2','c2'))
            return True
        self.host.verify_source=verify
        with self.assertRaises(SourceUnavailable): self.show()
        self.assertEqual(len(self.ledger.history()),1)

    def test_cas_race_only_one_mutation_commits(self):
        self.ledger.apply_host_batch([evt()], self.host)
        gate = threading.Barrier(3)
        def race(n):
            attempt=evt(f'e{n}',action=p.SUPERSEDE,rev=1,value=f'v{n}',time=2000)
            gate.wait(timeout=5)
            try:
                self.ledger.apply_host_batch([attempt],self.host)
                return 'ok'
            except StateConflict:
                return 'stale'
        with ThreadPoolExecutor(2) as ex:
            a=ex.submit(race,2); b=ex.submit(race,3)
            gate.wait(timeout=5)
            self.assertCountEqual([a.result(timeout=5),b.result(timeout=5)],['ok','stale'])
        self.assertEqual(len(self.ledger.history()),2)
        self.assertEqual(self.show().claims[0].revision,2)

    def test_host_held_lease_serializes_publication_with_revocation(self):
        self.ledger.apply_host_batch([evt()],self.host)
        lock=threading.Lock()  # test stand-in for Lu's host synchronization
        entered=threading.Event()
        release=threading.Event()
        revoked=threading.Event()
        emitted=[]
        def publishing():
            with lock:
                def deliver(frame):
                    entered.set()
                    self.assertTrue(release.wait(timeout=5))
                    emitted.append(frame)
                self.ledger.publish_host_fenced(self.host, deliver)
        def revocation():
            with lock:
                self.host.active=False
                revoked.set()
        with ThreadPoolExecutor(2) as executor:
            reader=executor.submit(publishing)
            self.assertTrue(entered.wait(timeout=5))
            revoker=executor.submit(revocation)
            self.assertFalse(revoked.wait(timeout=0.1))
            release.set()
            reader.result(timeout=5)
            revoker.result(timeout=5)
        self.assertEqual(len(emitted),1)
        with self.assertRaises(SourceUnavailable): self.show()

    def test_reentrant_host_admission_cannot_force_partial_mutation(self):
        def admit(_scope,_event):
            self.ledger.apply_batch([evt('e99','c99')])
            return True
        self.host.admit_event=admit
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([evt()],self.host)
        self.assertFalse(self.ledger.history())

    def test_live_event_verification_done_before_exact_idempotent_replay(self):
        event=evt()
        self.ledger.apply_host_batch([event],self.host)
        self.host.active=False
        with self.assertRaises(SourceUnavailable):
            self.ledger.apply_host_batch([event],self.host)

    def test_corrupt_snapshot_no_evidence(self):
        self.ledger.apply_host_batch([evt()],self.host)
        self.ledger._history[0]=self.ledger._history[0]+b'\xf8\x07\x01'
        with self.assertRaises(StateInvalid): self.show()


class C07TemporalAndConflictTests(unittest.TestCase):
    def test_user_goal_change_retains_audit_and_upgrades_current(self):
        state=StateLedger('proj1')
        state.apply(evt(value='ship in June',predicate='goal'))
        state.apply(evt('e2',rev=1,action=p.SUPERSEDE,value='ship in July',time=2500,predicate='goal'))
        self.assertEqual(state.projection().claims[0].value_text,'ship in July')
        self.assertEqual(len(state.history()),2)
        self.assertEqual(StateLedger.replay('proj1',state.history()).projection(),state.projection())

    def test_retroactive_effective_time_rejected(self):
        state=StateLedger('proj1')
        state.apply(evt(time=3000))
        e=evt('e2',action=p.SUPERSEDE,rev=1,value='new',time=4000)
        e.effective_at_ms=1000
        with self.assertRaises(StateConflict):state.apply(e)

    def test_cross_conversation_contradiction_remains_visible(self):
        state=StateLedger('proj1')
        state.apply(evt())
        later=with_source(evt('e2',claim_id='c2',value='other',time=2000),session='chat2')
        state.apply(later)
        self.assertEqual(len(state.projection().conflicts),1)
        state.apply(with_source(evt('e3',claim_id='c2',value='other',action=p.RETRACT,rev=1,time=3000),session='chat2'))
        self.assertEqual(len(state.projection().conflicts),0)

    def test_host_observation_cannot_demote_user_confirmation(self):
        state=StateLedger('proj1')
        state.apply(evt())
        changed=with_source(evt('e2',action=p.CONFIRM,rev=1,origin=p.HOST_OBSERVED,time=2000),session='chat2',digest='b'*64)
        state.apply(changed)
        v=state.projection().claims[0]
        self.assertEqual(v.origin,p.USER_VERIFIED)
        self.assertEqual(v.source.session_id,'chat1')
        self.assertEqual(v.source.content_sha256,'a'*64)

    def test_user_confirmation_upgrades_model_hypothesis(self):
        state=StateLedger('proj1')
        state.apply(evt(origin=p.MODEL_HYPOTHESIS))
        e=with_source(evt('e2',action=p.CONFIRM,rev=1,time=2000),session='chat2')
        state.apply(e)
        v=state.projection().claims[0]
        self.assertEqual(v.origin,p.USER_VERIFIED)
        self.assertEqual(v.source.session_id,'chat2')

    def test_concurrent_disjoint_claims_both_preserved(self):
        state=StateLedger('proj1')
        with ThreadPoolExecutor(4) as pool:
            futures=[pool.submit(state.apply,evt(f'e{n}',claim_id=f'c{n}',value=f'v{n}',time=1000+n)) for n in range(1,5)]
            self.assertEqual([f.result(timeout=5) for f in futures],[True]*4)
        self.assertEqual(len(state.projection().claims),4)
        self.assertEqual(len(state.projection().conflicts),6)

if __name__=='__main__': unittest.main()
