"""C15 T2 P2P: read-only C07 integration, adversarial provenance and replay."""
import copy
import hashlib
import pytest
from cognitum.proto import spatial_structural_c07_bridge_pb2 as bridge_pb
from cognitum.proto import spatial_composition_pb2 as sg
from cognitum.proto import spatial_ontology_subset_pb2 as ont
from cognitum.proto import state_pb2 as sp
from cognitum import spatial_structural_c07_bridge as bridge
from cognitum.state_host_gate import SourceUnavailable


def req_fixture():
    outer = bridge_pb.T2C07BridgeRequest(schema_version=1, research_only=True)
    p = outer.structural_request
    p.schema_version = 1;p.conversation_id = 'c1';p.research_only = True
    template = p.ontology_template
    template.schema_version = 1;template.conversation_id = 'c1';template.research_only=True
    template.graph.schema_version=1;template.graph.graph_id='graph';template.graph.conversation_id='c1';template.graph.research_only=True
    template.graph.nodes.add(node_id='node',kind='component',evidence=sg.EVIDENCE_INFERRED,source_ref='node-source')
    for ident, parents in [('Entity',[]),('Solid',['Entity']),('Void',['Entity'])]:
        template.classes.add(class_id=ident,parent_class_ids=parents,source_ref='taxonomy')
    template.disjoints.add(first_class_id='Solid',second_class_id='Void',source_ref='disjoint')
    p.candidates.add(candidate_id='branchA',explanation='One structural interpretation')
    for index, label in enumerate(['Solid','Void']):
        e=p.events.add(event_id=f'ev{index+1}',candidate_id='branchA',sequence=index+1,
                       source_ref='untrustedP2OSource',rationale='A sourced, reviewable alternative')
        e.add_type.claim_id=f'claim{index+1}'
        e.add_type.claim.CopyFrom(ont.OntologyTypeClaim(node_id='node',class_id=label,
                  evidence=sg.EVIDENCE_INFERRED,source_ref='untrustedType'))
    e=p.events.add(event_id='ev3',candidate_id='branchA',sequence=3,
                   source_ref='untrustedP2OSource',rationale='Retire the disputed alternative')
    e.retract.claim_id='claim2'
    return outer


def state_events(req, *, disputed=False, uncertainty=False):
    events=[]
    def make(t2, action, value, rev=0, origin=sp.USER_VERIFIED, name=None, time=1):
        e=sp.StateEvent(schema_version=1,event_id=name or t2.event_id,scope_id='c1',
             claim_id=bridge._claim_id(t2),subject_id=t2.candidate_id,
             predicate=bridge.PREFIX+bridge._claim_id(t2),value_kind=sp.TEXT,value_text=value,
             origin=origin,action=action,expected_revision=rev,
             recorded_at_ms=time,effective_at_ms=time,
             source=sp.SourceEvidence(session_id='c1',root_entry_id='1',revision_entry_id='2',
                   content_sha256='a'*64,snapshot_id='snap'))
        return e
    a,b,c=req.structural_request.events[:3]
    ha=bridge._digest(a.add_type.claim).hex()
    hb=bridge._digest(b.add_type.claim).hex()
    e=make(a,sp.ASSERT,ha,time=1000,
           origin=sp.MODEL_HYPOTHESIS if uncertainty else sp.USER_VERIFIED)
    if uncertainty:
        e.uncertainty_kind=sp.EXPLICITLY_UNCERTAIN
        e.uncertainty_note='Classification uncertain; confirm by independent evidence'
    events.append(e)
    if disputed:
        events.append(make(a,sp.CHALLENGE,ha,1,sp.MODEL_HYPOTHESIS,'challengeA',1500))
    events.append(make(b,sp.ASSERT,hb,time=2000))
    events.append(make(c,sp.RETRACT,hb,1,time=3000))
    return events


class TrustedTestLease:
    def __init__(self):
        self.active=True;self.admitted=[];self.sources=[];self.bindings=[]
        self.deny_source=False;self.deny_binding=False;self.deny_admission=False
        self.reject_claimed_user=False
    def ensure_active(self):return self.active
    def admit_event(self,scope,e):
        self.admitted.append(e.event_id)
        return not self.deny_admission and not (self.reject_claimed_user and e.origin == sp.USER_VERIFIED)
    def verify_source(self,scope,source,current):
        self.sources.append((source.session_id,current))
        return not self.deny_source and source.session_id == scope
    def bind_structural_event(self,scope,t2,c07):
        self.bindings.append((t2.event_id,c07.event_id))
        return not self.deny_binding and scope=='c1' and t2.event_id==c07.event_id


def run(req,lease=None):
    lease=lease or TrustedTestLease()
    seen=[]
    response=bridge.publish_host_fenced(req,lease,lambda data: seen.append(data) or data)
    assert len(seen)==1
    return bridge_pb.T2C07BridgeResult.FromString(response),lease


def populated(disputed=False,uncertainty=False):
    q=req_fixture()
    q.c07_event_frames.extend(e.SerializeToString(deterministic=True) for e in
                              state_events(q,disputed=disputed,uncertainty=uncertainty))
    return q


def test_reconciliation_keeps_c07_provenance_and_p2o_conflict_history():
    q=populated()
    out,lease=run(q)
    assert out.structural_result.revisions[1].introduced_conflicts==['node|Solid|Void|disjoint']
    assert out.structural_result.revisions[2].resolved_conflicts==['node|Solid|Void|disjoint']
    assert [x.event_id for x in out.events]==['ev1','ev2','ev3']
    assert [(x.claim_id,x.structural_status,x.c07_status) for x in out.claims]==[
        ('claim1','ACTIVE',sp.ACTIVE),('claim2','RETRACTED',sp.RETRACTED)]
    assert not out.requires_review and not out.grants_authority and out.research_only
    assert len(lease.bindings)==3
    assert len([v for _,v in lease.sources if v])==1
    assert all(len(x.c07_source_sha256)==32 for x in out.claims)
    again,_=run(q)
    assert again.SerializeToString(deterministic=True)==out.SerializeToString(deterministic=True)


def test_dispute_requires_review_without_auto_retraction_or_promotion():
    q=populated(disputed=True)
    out,_=run(q)
    assert out.requires_review
    assert out.claims[0].c07_status == sp.DISPUTED
    assert out.claims[0].structural_status == 'ACTIVE'
    assert out.claims[0].c07_revision == 2
    assert out.structural_result.candidates[0].active_claim_ids==['claim1']
    assert len(out.events)==3


def test_uncertainty_survives_without_fabricated_numeric_confidence():
    out,_=run(populated(uncertainty=True))
    assert out.requires_review
    assert out.claims[0].c07_origin == sp.MODEL_HYPOTHESIS
    assert out.claims[0].c07_uncertainty == sp.EXPLICITLY_UNCERTAIN
    assert 'uncertain' in out.claims[0].c07_uncertainty_note.lower()
    assert not out.grants_authority


def test_host_denials_fail_closed_and_publish_nothing():
    for gate in ['deny_source','deny_binding','deny_admission']:
        l=TrustedTestLease();setattr(l,gate,True);out=[]
        with pytest.raises(SourceUnavailable):
            bridge.publish_host_fenced(populated(),l,out.append)
        assert not out
    l=TrustedTestLease();l.active=False
    with pytest.raises(SourceUnavailable):run(populated(),l)


def test_host_can_reject_forged_verified_origin():
    l=TrustedTestLease();l.reject_claimed_user=True
    with pytest.raises(SourceUnavailable):run(populated(),l)

@pytest.mark.parametrize('attack',[
    'foreign_scope','foreign_source','unknown_wire','missing_frame','tamper_hash',
    'duplicate_c07_id','wrong_identity','wrong_predicate','swap_frames','missing_retract',
    'injected_unmapped_retract','faked_authority','cross_candidate','invalid_version',
    'unknown_outer_field','wrong_claim_id','wrong_action','untrusted_state_field',
])
def test_adversarial_rejection(attack):
    q=populated()
    events=[sp.StateEvent.FromString(x) for x in q.c07_event_frames]
    if attack=='foreign_scope': events[0].scope_id='other'
    elif attack=='foreign_source':events[0].source.session_id='other'
    elif attack=='unknown_wire': q.c07_event_frames[0]+=b'\xf8\x07\x01'
    elif attack=='missing_frame':del q.c07_event_frames[1]
    elif attack=='tamper_hash':events[0].value_text='0'*64
    elif attack=='duplicate_c07_id':events[1].event_id=events[0].event_id
    elif attack=='wrong_identity':events[0].subject_id='different'
    elif attack=='wrong_predicate':events[0].predicate='other'
    elif attack=='swap_frames':events[0],events[1]=events[1],events[0]
    elif attack=='missing_retract':del q.c07_event_frames[-1]
    elif attack=='injected_unmapped_retract':events[0].event_id='extra';events[0].action=sp.RETRACT
    elif attack=='faked_authority':q.grants_authority=True
    elif attack=='cross_candidate':q.structural_request.events[0].candidate_id='foreign'
    elif attack=='invalid_version':q.schema_version=9
    elif attack=='unknown_outer_field':q=bridge_pb.T2C07BridgeRequest.FromString(q.SerializeToString()+b'\xf8\x07\x01')
    elif attack=='wrong_claim_id':events[0].claim_id='unknown'
    elif attack=='wrong_action':events[0].action=sp.CONFIRM
    elif attack=='untrusted_state_field':events[0].origin=999
    if attack not in ('faked_authority','cross_candidate','invalid_version','unknown_outer_field','missing_frame','missing_retract','unknown_wire'):
        q.c07_event_frames[:]=[e.SerializeToString(deterministic=True) for e in events]
    if attack=='swap_frames':
        # Keep C07 chronology in order of supplied frames, not sorting.
        pass
    with pytest.raises((bridge.T2C07Rejected,SourceUnavailable)):
        run(q)


def test_unmapped_expiry_does_not_retract_p2o_claim():
    q=req_fixture(); events=state_events(q)
    e=copy.deepcopy(events[0]);e.event_id='expiry';e.action=sp.EXPIRE;e.expected_revision=1
    e.recorded_at_ms=1750;e.effective_at_ms=1750
    frames=[events[0],e,*events[1:]]
    q.c07_event_frames.extend(x.SerializeToString(deterministic=True) for x in frames)
    out,_=run(q)
    assert out.requires_review and out.claims[0].c07_status==sp.EXPIRED
    assert out.claims[0].structural_status=='ACTIVE'


def test_late_host_revocation_fails_before_publication():
    class Revoking(TrustedTestLease):
        def verify_source(self,scope,source,current):
            if current:self.active=False
            return super().verify_source(scope,source,current)
    results=[]
    with pytest.raises(SourceUnavailable):
        bridge.publish_host_fenced(populated(),Revoking(),results.append)
    assert results==[]


def test_response_contains_no_raw_c07_source_record_and_not_a_grant():
    out,_=run(populated())
    assert not out.grants_authority
    assert b'aaaaaaaaaaaaaaaa' not in out.SerializeToString(deterministic=True)
    assert out.request_sha256==hashlib.sha256(populated().SerializeToString(deterministic=True)).digest()


def test_two_candidates_isolation_and_independent_provenance():
    q=req_fixture()
    q.structural_request.candidates.add(candidate_id='branchB',explanation='Different source hypothesis')
    e=q.structural_request.events.add(event_id='ev4',candidate_id='branchB',sequence=1,
                                     source_ref='otherResearchSource',rationale='Independent candidate')
    e.add_type.claim_id='branchBClaim'
    e.add_type.claim.CopyFrom(ont.OntologyTypeClaim(node_id='node',class_id='Void',
                                 evidence=sg.EVIDENCE_HYPOTHETICAL,source_ref='otherSource'))
    events=state_events(q)
    extra=sp.StateEvent(schema_version=1,event_id='ev4',scope_id='c1',claim_id='branchBClaim',
                        subject_id='branchB',predicate='spatial.branchBClaim',
                        value_kind=sp.TEXT,value_text=bridge._digest(e.add_type.claim).hex(),
                        action=sp.ASSERT,origin=sp.MODEL_HYPOTHESIS,
                        recorded_at_ms=4000,effective_at_ms=4000,
                        uncertainty_kind=sp.OPEN_QUESTION,uncertainty_note='Unverified second candidate',
                        source=sp.SourceEvidence(session_id='c1',root_entry_id='20',revision_entry_id='21',
                             content_sha256='b'*64,snapshot_id='otherSnap'))
    q.c07_event_frames.extend(x.SerializeToString(deterministic=True) for x in [*events,extra])
    result,lease=run(q)
    assert result.requires_review
    assert len(result.claims)==3
    by_id={c.claim_id:c for c in result.claims}
    assert by_id['branchBClaim'].candidate_id=='branchB'
    assert by_id['branchBClaim'].c07_origin==sp.MODEL_HYPOTHESIS
    assert 'branchBClaim' not in result.structural_result.candidates[0].active_claim_ids
    assert result.structural_result.candidates[1].active_claim_ids==['branchBClaim']
    assert len(lease.bindings)==4


def test_host_callback_mutation_detected_even_when_lease_returns_true():
    class Mutating(TrustedTestLease):
        def bind_structural_event(self,scope,t2,c07):
            t2.source_ref='forgedByHostCallback'
            return True
    callbacks=[]
    with pytest.raises(bridge.T2C07Rejected,match='MUTATED_BRIDGE_REQUEST'):
        bridge.publish_host_fenced(populated(),Mutating(),callbacks.append)
    assert not callbacks


def test_unknown_field_c07_fails_without_source_callback():
    q=populated();q.c07_event_frames[0]+=b'\xf8\x07\x01'
    lease=TrustedTestLease()
    with pytest.raises(bridge.T2C07Rejected):run(q,lease)
    assert not lease.admitted and not lease.sources and not lease.bindings


def test_global_claim_collision_across_candidates_is_explicitly_rejected():
    q=req_fixture()
    q.structural_request.candidates.add(candidate_id='branchB', explanation='Other')
    e=q.structural_request.events.add(event_id='ev4',candidate_id='branchB',sequence=1,
             source_ref='research',rationale='Duplicate ID across candidates')
    e.add_type.claim_id='claim1'
    e.add_type.claim.CopyFrom(q.structural_request.events[0].add_type.claim)
    q.c07_event_frames.extend(x.SerializeToString(deterministic=True) for x in state_events(q))
    with pytest.raises(bridge.T2C07Rejected,match='COLLISION'):
        run(q)


def test_c07_confirm_keeps_p2o_hypothesis_separate_from_host_verification():
    q=req_fixture();events=state_events(q,uncertainty=True)
    confirm=copy.deepcopy(events[0]);confirm.event_id='confirm1';confirm.action=sp.CONFIRM
    confirm.origin=sp.USER_VERIFIED;confirm.expected_revision=1
    confirm.uncertainty_kind=sp.UNCERTAINTY_UNSPECIFIED
    confirm.uncertainty_note='';confirm.recorded_at_ms=1500;confirm.effective_at_ms=1500
    q.c07_event_frames.extend(e.SerializeToString(deterministic=True) for e in
                              [events[0],confirm,*events[1:]])
    out,_=run(q)
    assert out.claims[0].c07_revision==2
    assert out.claims[0].c07_origin==sp.USER_VERIFIED
    assert out.claims[0].c07_uncertainty==sp.EXPLICITLY_UNCERTAIN
    assert out.requires_review
    assert out.structural_result.candidates[0].final_decision=='CLAIMS_CONSISTENT'
    assert not out.grants_authority


def test_c07_temporal_correction_links_history_but_cannot_change_structural_claim():
    q=req_fixture();events=state_events(q)
    correct=copy.deepcopy(events[0]);correct.event_id='correct1';correct.action=sp.TEMPORAL_CORRECT
    correct.expected_revision=1;correct.recorded_at_ms=1500;correct.effective_at_ms=800
    correct.corrects_event_id='ev1'
    q.c07_event_frames.extend(e.SerializeToString(deterministic=True) for e in
                              [events[0],correct,*events[1:]])
    out,_=run(q)
    assert out.claims[0].c07_revision==2
    assert out.claims[0].latest_c07_event_id=='correct1'
    assert out.claims[0].structural_status=='ACTIVE'
    assert not out.grants_authority
    correct.corrects_event_id='ev2'
    q.c07_event_frames[:]=[e.SerializeToString(deterministic=True) for e in
                           [events[0],correct,*events[1:]]]
    with pytest.raises(bridge.T2C07Rejected,match='STATE_TRANSITION'):
        run(q)
