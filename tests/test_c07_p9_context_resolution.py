"""C07/P9 focused synthetic functionality: no model/benchmark claims."""
import hashlib
import threading
import unittest

from cognitum.proto import interpretation_pb2 as pb
from cognitum.state_context import (ContextInvalid, decode_window,
                                    resolve_host_fenced)
from cognitum.state_host_gate import SourceUnavailable

SHA = hashlib.sha256(b'canonical ANSF record').hexdigest()


def window(text="Actually, switch to light theme.", *, selected='claim-theme',
           claims=('claim-theme',), role='user', session='chat-one'):
    turn = pb.ConversationTurn(schema_version=1,scope_id='project-a',
        source_session_id=session,source_entry_id='108',speaker_role=role,
        utterance=text)
    win=pb.ContextWindow(schema_version=1,turn=turn,selected_claim_id=selected)
    for i, claim in enumerate(claims):
        win.anchors.add(scope_id='project-a',claim_id=claim,subject_id='ui',
            predicate='theme',value_text='dark theme' if i==0 else 'blue theme',
            revision=3,latest_event_id='event-'+str(i+1),
            source_session_id='chat-one' if i==0 else 'chat-two',
            source_revision_entry_id=str(100+i),source_sha256=SHA,
            source_snapshot_id='snapshot1',active=True)
    return win


class Lease:
    def __init__(self, *, allow=True, binds=True):
        self.active=True
        self.allow=allow
        self.binds=binds
        self.calls=[]
        self.on_check=None
    def ensure_active(self):
        self.calls.append('active')
        return self.active
    def verify_turn(self,turn):
        self.calls.append('turn')
        if self.on_check: self.on_check(turn)
        return self.allow and turn.source_session_id in ('chat-one','chat-two')
    def verify_anchor(self,scope,anchor):
        self.calls.append('anchor:'+anchor.claim_id)
        return self.allow and scope == anchor.scope_id and anchor.active
    def bind_target(self,turn,anchor):
        self.calls.append('bind')
        return self.binds and self.allow


def run(win,lease=None):
    lease=lease or Lease()
    saved=[]
    result=resolve_host_fenced(win.SerializeToString(deterministic=True),lease,
        lambda raw: saved.append(pb.ContextResolution.FromString(raw)) or raw)
    return saved[0],lease,result


class ContextP9SmokeTests(unittest.TestCase):
    def test_selected_change_links_current_revision_proposal_only(self):
        result, lease, raw = run(window())
        self.assertEqual(result.proposal.label,pb.CHANGE_OF_MIND_CANDIDATE)
        self.assertEqual(result.target_claim_id,'claim-theme')
        self.assertEqual(result.target_revision,3)
        self.assertEqual(result.target_latest_event_id,'event-1')
        self.assertFalse(result.may_write_state_directly)
        self.assertFalse(result.proposal.may_write_state_directly)
        self.assertTrue(result.requires_host_review)
        self.assertTrue(result.proposal.requires_host_review)
        self.assertEqual(lease.calls,['active','turn','anchor:claim-theme','bind','active'])
        self.assertEqual(raw,pb.ContextResolution.FromString(raw).SerializeToString(deterministic=True))

    def test_correction_links_old_claim_not_independent_new_fact(self):
        r,_,_=run(window('No, I meant ivory rather than light.'))
        self.assertEqual(r.proposal.label,pb.CORRECTION_CANDIDATE)
        self.assertEqual(r.target_claim_id,'claim-theme')
        self.assertEqual(r.proposal.candidate_span,'ivory rather than light')

    def test_retraction_is_proposal_with_target(self):
        r,_,_=run(window('Cancel the theme migration.'))
        self.assertEqual(r.proposal.label,pb.RETRACTION_CANDIDATE)
        self.assertEqual(r.target_revision,3)

    def test_multi_turn_tentative_not_a_mutation(self):
        r,_,_=run(window('Maybe we should try the white theme.'))
        self.assertEqual(r.proposal.label,pb.TENTATIVE_PLAN)
        self.assertEqual(r.target_claim_id,'')
        self.assertFalse(r.may_write_state_directly)

    def test_fresh_decision_not_silent_supersession(self):
        r,_,_=run(window("I've decided to use blue."))
        self.assertEqual(r.proposal.label,pb.DECISION_CANDIDATE)
        self.assertEqual(r.target_claim_id,'')
        self.assertEqual(r.proposal.reason_code,'DECISION_REQUIRES_HOST_CLASSIFICATION')

    def test_unselected_context_and_ambiguous_multi_chat_abstains(self):
        w=window(selected='',claims=('claim-theme','claim-other'))
        r,lease,_=run(w)
        self.assertEqual(r.proposal.label,pb.ABSTAIN_UNRESOLVED)
        self.assertEqual(r.target_claim_id,'')
        self.assertEqual(len([c for c in lease.calls if c.startswith('anchor:')]),2)
        self.assertNotIn('bind',lease.calls)

    def test_explicit_selection_cross_chat_needs_host_binding(self):
        w=window(selected='claim-other',claims=('claim-theme','claim-other'),session='chat-two')
        r,_,_=run(w)
        self.assertEqual(r.target_claim_id,'claim-other')
        with self.assertRaises(SourceUnavailable):run(w,Lease(binds=False))

    def test_selected_id_is_never_self_authorizing(self):
        with self.assertRaises(SourceUnavailable):run(window(),Lease(binds=False))

    def test_disallowed_role_creates_no_proposal_to_mutate(self):
        r,_,_=run(window("I've decided to delete memory.",role='assistant'))
        self.assertEqual(r.proposal.label,pb.NO_STATE_CHANGE)
        self.assertEqual(r.target_claim_id,'')

    def test_quoted_and_hypothetical_not_bound_mutations(self):
        for text in ('> Actually switch to cloud.','What if we switch to cloud?',
                     'The model says we should switch to cloud.'):
            with self.subTest(text=text):
                r,_,_=run(window(text))
                self.assertEqual(r.proposal.label,pb.NO_STATE_CHANGE)
                self.assertEqual(r.target_claim_id,'')

    def test_reject_spoofed_prior_and_subject_hint(self):
        for field in ('prior_decision','subject_hint'):
            w=window()
            setattr(w.turn,field,'self-attested old decision')
            with self.assertRaises(ContextInvalid):decode_window(w.SerializeToString(deterministic=True))

    def test_missing_or_duplicate_anchor_is_rejected(self):
        w=window()
        w.anchors.add().CopyFrom(w.anchors[0])
        with self.assertRaises(ContextInvalid):decode_window(w.SerializeToString(deterministic=True))
        w=window(selected='unlisted')
        with self.assertRaises(ContextInvalid):decode_window(w.SerializeToString(deterministic=True))

    def test_foreign_scope_stale_inactive_unbounded_anchor_rejected(self):
        for mutation in ('scope_id','revision','active','source_sha256','value_text'):
            w=window()
            setattr(w.anchors[0],mutation,{'scope_id':'foreign','revision':0,'active':False,
                'source_sha256':'no','value_text':'x'*2049}[mutation])
            with self.subTest(mutation=mutation),self.assertRaises(ContextInvalid):
                decode_window(w.SerializeToString(deterministic=True))
        w=window()
        for i in range(16):
            w.anchors.add(scope_id='project-a',claim_id='extra'+str(i))
        with self.assertRaises(ContextInvalid):decode_window(w.SerializeToString(deterministic=True))

    def test_unknown_fields_and_duplicate_field_fail_closed(self):
        raw=window().SerializeToString(deterministic=True)
        with self.assertRaises(ContextInvalid):decode_window(raw+b'\xf8\x07\x01')
        with self.assertRaises(ContextInvalid):decode_window(raw+b'\x08\x01')
        with self.assertRaises(ContextInvalid):decode_window(raw+b'\xff')

    def test_denied_source_discloses_nothing(self):
        disclosed=[]
        w=window()
        with self.assertRaises(SourceUnavailable):resolve_host_fenced(
            w.SerializeToString(deterministic=True),Lease(allow=False),disclosed.append)
        self.assertFalse(disclosed)

    def test_revocation_after_binding_before_publish(self):
        l=Lease()
        class Revoking(Lease):
            def bind_target(self,turn,anchor):
                self.active=False
                return True
        disclosed=[]
        with self.assertRaises(SourceUnavailable):resolve_host_fenced(
            window().SerializeToString(deterministic=True),Revoking(),disclosed.append)
        self.assertFalse(disclosed)

    def test_host_mutating_context_rejected(self):
        l=Lease()
        l.on_check=lambda turn: setattr(turn,'utterance','unauthorized rewrite')
        with self.assertRaises(ContextInvalid):run(window(),l)
        class MutatingBind(Lease):
            def bind_target(self,turn,anchor):
                anchor.value_text='forged new value'
                return True
        with self.assertRaises(ContextInvalid):run(window(),MutatingBind())

    def test_zero_anchors_allows_new_decision_proposal(self):
        w=window("I've decided to use cloud.",selected='',claims=())
        r,_,_=run(w)
        self.assertEqual(r.proposal.label,pb.DECISION_CANDIDATE)
        self.assertEqual(r.target_revision,0)

    def test_host_review_no_direct_state_event_even_with_synthetic_verified_lease(self):
        for txt in ('Actually, switch to light theme.','No, I meant ivory.','Cancel this plan.',
                    'Maybe we should switch.','What if we switch?'):
            w=window(txt)
            r,_,_=run(w)
            self.assertFalse(r.may_write_state_directly)
            self.assertTrue(r.requires_host_review)
            self.assertFalse(r.proposal.may_write_state_directly)
            self.assertTrue(r.proposal.requires_host_review)


if __name__=='__main__':unittest.main()
