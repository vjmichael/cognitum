"""C15 T2 P2O revision replay and adversarial epistemic boundaries."""
import copy
import hashlib
import random
import pytest
from cognitum import spatial_structural_reconciliation as r2
from cognitum import spatial_ontology_subset as ont
from cognitum.proto import spatial_structural_reconciliation_pb2 as pb
from cognitum.proto import spatial_composition_pb2 as sg
from cognitum.proto import spatial_ontology_subset_pb2 as op


def setup(*names, include_hypotheses=False):
    req = pb.T2ReconciliationRequest(schema_version=1,conversation_id='c1',research_only=True)
    base = req.ontology_template
    base.schema_version=1;base.conversation_id='c1';base.research_only=True
    base.include_hypotheses=include_hypotheses
    base.graph.schema_version=1;base.graph.graph_id='g1';base.graph.conversation_id='c1';base.graph.research_only=True
    for node, evidence in [('x',sg.EVIDENCE_INFERRED),('y',sg.EVIDENCE_INFERRED),('guess',sg.EVIDENCE_HYPOTHETICAL)]:
        base.graph.nodes.add(node_id=node,kind='component',evidence=evidence,source_ref='sourceNode')
    for name, parents in [('Entity',[]),('Solid',['Entity']),('Mechanical',['Solid']),('Void',['Entity']),('Assembly',['Entity'])]:
        base.classes.add(class_id=name,parent_class_ids=parents,source_ref='schema')
    base.disjoints.add(first_class_id='Solid',second_class_id='Void',source_ref='disjointRule')
    for name in names:
        req.candidates.add(candidate_id=name,explanation='An unadmitted research alternative '+name)
    return req


def add_type(req,candidate,cls,node='x',status=sg.EVIDENCE_INFERRED,claim=None):
    events=[e for e in req.events if e.candidate_id==candidate]
    e=req.events.add(event_id=f'{candidate}E{len(events)+1}',candidate_id=candidate,
                     sequence=len(events)+1,source_ref='researchLog',rationale='New caller claim, not an authenticated measurement')
    e.add_type.claim_id=claim or (candidate+cls+node)
    e.add_type.claim.CopyFrom(op.OntologyTypeClaim(node_id=node,class_id=cls,evidence=status,source_ref='source'+(claim or candidate+cls+node)))
    return e


def add_edge(req,candidate,from_id='x',to_id='y',relation=sg.STRUCTURE_PART_OF,
             status=sg.EVIDENCE_INFERRED,claim='edge1'):
    events=[e for e in req.events if e.candidate_id==candidate]
    e=req.events.add(event_id=f'{candidate}E{len(events)+1}',candidate_id=candidate,
                     sequence=len(events)+1,source_ref='researchLog',rationale='Edge added as an unadmitted structural claim')
    e.add_edge.claim_id=claim
    e.add_edge.edge.CopyFrom(sg.StructureEdge(from_id=from_id,to_id=to_id,relation=relation,evidence=status,source_ref='edgeSource'))
    return e


def retract(req,candidate,key,reason='A source has revised an earlier claim'):
    events=[e for e in req.events if e.candidate_id==candidate]
    e=req.events.add(event_id=f'{candidate}E{len(events)+1}',candidate_id=candidate,
                     sequence=len(events)+1,source_ref='revisionLog',rationale=reason)
    e.retract.claim_id=key
    return e


def by_candidate(out):return {c.candidate_id:c for c in out.candidates}


def test_revision_retracts_conflict_and_preserves_receipts():
    req=setup('alternativeA','alternativeB')
    add_type(req,'alternativeA','Mechanical')
    add_type(req,'alternativeA','Void')
    retract(req,'alternativeA','alternativeAVoidx')
    add_type(req,'alternativeB','Void')
    original=req.SerializeToString(deterministic=True)
    out=r2.reconcile(req)
    assert req.SerializeToString(deterministic=True)==original
    assert not out.any_conflicts
    rev=[x for x in out.revisions if x.candidate_id=='alternativeA']
    assert [x.decision for x in rev]==['CLAIMS_CONSISTENT','CLAIMS_CONFLICTED','CLAIMS_CONSISTENT']
    assert rev[1].introduced_conflicts==['x|Solid|Void|disjointRule']
    assert rev[2].resolved_conflicts==['x|Solid|Void|disjointRule']
    assert rev[2].active_claim_ids==['alternativeAMechanicalx']
    assert len({x.journal_receipt_sha256 for x in rev})==3
    assert all(len(x.journal_receipt_sha256)==32 and len(x.snapshot_sha256)==32 for x in rev)
    assert by_candidate(out)['alternativeA'].final_decision=='CLAIMS_CONSISTENT'
    assert by_candidate(out)['alternativeB'].final_decision=='CLAIMS_CONSISTENT'
    assert out.grants_authority is False and out.research_only
    assert r2.reconcile(req).SerializeToString(deterministic=True)==out.SerializeToString(deterministic=True)
    assert 'CONSISTENCY_IS_NOT_CORRECTNESS_OR_PROBABILISTIC_HYPOTHESIS_SELECTION' in out.warnings


def test_unresolved_conflict_is_never_automatically_selected():
    req=setup('conflicted','alternative')
    add_type(req,'conflicted','Mechanical')
    add_type(req,'conflicted','Void')
    add_type(req,'alternative','Void')
    out=r2.reconcile(req)
    assert out.any_conflicts
    assert by_candidate(out)['conflicted'].final_decision=='CLAIMS_CONFLICTED'
    assert by_candidate(out)['alternative'].final_decision=='CLAIMS_CONSISTENT'
    assert not hasattr(out,'selected_candidate')


def test_hypothetical_never_promoted_and_opt_in_is_labeled():
    req=setup('c1')
    add_type(req,'c1','Mechanical')
    add_type(req,'c1','Void',status=sg.EVIDENCE_HYPOTHETICAL)
    normal=r2.reconcile(req)
    assert not normal.any_conflicts
    assert not any('Void' in s for s in normal.candidates[0].final_supported_types)
    req.ontology_template.include_hypotheses=True
    included=r2.reconcile(req)
    assert included.any_conflicts
    assert 'x|Void|true' in included.candidates[0].final_supported_types
    assert 'x|Mechanical|false' in included.candidates[0].final_supported_types
    req2=setup('c2')
    add_type(req2,'c2','Mechanical',node='guess',status=sg.EVIDENCE_OBSERVED)
    with pytest.raises(r2.ReconciliationRejected,match='CONFLATION'):
        r2.reconcile(req2)


def test_edge_signatures_change_types_and_provenance_with_retraction():
    req=setup('structure')
    req.ontology_template.relation_rules.add(relation=sg.STRUCTURE_PART_OF,
                      from_class_id='Void',to_class_id='Assembly',source_ref='schemaSource')
    add_type(req,'structure','Mechanical')
    add_edge(req,'structure')
    retract(req,'structure','edge1')
    out=r2.reconcile(req)
    rev=out.revisions
    assert rev[1].introduced_conflicts==['x|Solid|Void|disjointRule']
    assert rev[2].resolved_conflicts==['x|Solid|Void|disjointRule']
    assert 'edgeSource' in rev[1].supporting_sources
    assert 'schemaSource' in rev[1].supporting_sources
    assert 'edgeSource' not in rev[2].supporting_sources
    assert all('y|Assembly' not in s for s in out.candidates[0].final_supported_types)


def test_retractions_cannot_target_other_candidate_or_reuse_ids():
    req=setup('a','b');add_type(req,'a','Mechanical');retract(req,'b','aMechanicalx')
    with pytest.raises(r2.ReconciliationRejected,match='UNKNOWN_CLAIM'):
        r2.reconcile(req)
    req=setup('a');add_type(req,'a','Mechanical');retract(req,'a','aMechanicalx')
    add_type(req,'a','Mechanical')
    with pytest.raises(r2.ReconciliationRejected,match='REUSED_CLAIM'):
        r2.reconcile(req)
    req=setup('a');add_type(req,'a','Mechanical');retract(req,'a','aMechanicalx')
    retract(req,'a','aMechanicalx')
    with pytest.raises(r2.ReconciliationRejected,match='UNKNOWN_CLAIM'):
        r2.reconcile(req)


@pytest.mark.parametrize('tamper',[
 'wrong_scope','authority','template_authority','template_assertion','template_edge',
 'duplicate_candidate','duplicate_event','sequence_gap','event_scope','bad_op',
 'bad_claim_id','no_reason','unknown_wire','invalid_node','unknown_class',
 'wrong_graph_scope','missing_research_flag', 'empty_events',
])
def test_adversarial_rejects_invalid_wire_and_logs(tamper):
    req=setup('a');add_type(req,'a','Mechanical')
    if tamper=='wrong_scope':req.conversation_id='c2'
    elif tamper=='authority':req.grants_authority=True
    elif tamper=='template_authority':req.ontology_template.grants_authority=True
    elif tamper=='template_assertion':req.ontology_template.assertions.add(node_id='x',class_id='Solid',evidence=sg.EVIDENCE_INFERRED,source_ref='src')
    elif tamper=='template_edge':req.ontology_template.graph.edges.add(from_id='x',to_id='y',relation=sg.STRUCTURE_PART_OF,evidence=sg.EVIDENCE_INFERRED,source_ref='src')
    elif tamper=='duplicate_candidate':req.candidates.add().CopyFrom(req.candidates[0])
    elif tamper=='duplicate_event':req.events.add().CopyFrom(req.events[0])
    elif tamper=='sequence_gap':req.events[0].sequence=2
    elif tamper=='event_scope':req.events[0].candidate_id='foreign'
    elif tamper=='bad_op':req.events[0].ClearField('add_type')
    elif tamper=='bad_claim_id':req.events[0].add_type.claim_id=''
    elif tamper=='no_reason':req.events[0].rationale=''
    elif tamper=='unknown_wire':req=pb.T2ReconciliationRequest.FromString(req.SerializeToString()+b'\xc0\x3e\x01')
    elif tamper=='invalid_node':req.events[0].add_type.claim.node_id='does_not_exist'
    elif tamper=='unknown_class':req.events[0].add_type.claim.class_id='Other'
    elif tamper=='wrong_graph_scope':req.ontology_template.graph.conversation_id='c2'
    elif tamper=='missing_research_flag':req.research_only=False
    elif tamper=='empty_events':req.events.clear()
    with pytest.raises(r2.ReconciliationRejected):r2.reconcile(req)


def test_invalid_structure_cycle_rejected_without_mutating_input():
    req=setup('a')
    add_edge(req,'a',from_id='x',to_id='y',claim='a')
    add_edge(req,'a',from_id='y',to_id='x',claim='b')
    initial=req.SerializeToString(deterministic=True)
    with pytest.raises(r2.ReconciliationRejected,match='INVALID_REVISED_ONTOLOGY'):
        r2.reconcile(req)
    assert req.SerializeToString(deterministic=True)==initial


def test_randomized_retraction_replay_matches_independent_ontology_snapshots():
    rnd=random.Random(20261028)
    # For every branch independently build the expected active-claim set, and
    # compare reconciler decision + conflicts to P2N on a freshly built request.
    for case in range(120):
        req=setup('a')
        additions=[];active={}
        for j in range(rnd.randint(1,12)):
            if active and rnd.random()<0.37:
                claim_id=rnd.choice(sorted(active))
                retract(req,'a',claim_id)
                del active[claim_id]
            else:
                cls=rnd.choice(['Mechanical','Void','Assembly','Solid'])
                node=rnd.choice(['x','y'])
                claim_id=f'id{j}'
                add_type(req,'a',cls,node=node,claim=claim_id)
                active[claim_id]=copy.deepcopy(req.events[-1].add_type.claim)
            additions.append(copy.deepcopy(active))
        out=r2.reconcile(req)
        assert len(out.revisions)==len(additions)
        for rev, expected_active in zip(out.revisions, additions):
            independent=op.OntologyAuditRequest()
            independent.CopyFrom(req.ontology_template)
            for key in sorted(expected_active):independent.assertions.add().CopyFrom(expected_active[key])
            checked=ont.audit(independent)
            expected={f'{f.node_id}|{c}' for f in checked.findings for c in f.disjoint_conflicts}
            # Separate class-set oracle: subclass expansion Mechanical=>Solid and
            # the only disjointness rule in the fixture is Solid vs Void.
            typed={node:set() for node in ('x','y','guess')}
            for item in expected_active.values():
                typed[item.node_id].add(item.class_id)
                if item.class_id=='Mechanical':typed[item.node_id].add('Solid')
            oracle={f'{node}|Solid|Void|disjointRule' for node,types in typed.items()
                    if 'Solid' in types and 'Void' in types}
            assert expected==oracle,case
            assert rev.decision == ('CLAIMS_CONFLICTED' if expected else 'CLAIMS_CONSISTENT'),case
            assert list(rev.active_claim_ids)==sorted(expected_active),case
            assert rev.ontology_result_sha256==hashlib.sha256(checked.SerializeToString(deterministic=True)).digest(),case


def test_reordered_event_changes_receipts_not_authenticated_provenance():
    first=setup('a');add_type(first,'a','Mechanical');add_type(first,'a','Void')
    second=setup('a');add_type(second,'a','Void');add_type(second,'a','Mechanical')
    x,y=r2.reconcile(first),r2.reconcile(second)
    assert x.candidates[0].final_ontology_result_sha256==y.candidates[0].final_ontology_result_sha256
    assert x.candidates[0].final_receipt_sha256!=y.candidates[0].final_receipt_sha256
    assert x.any_conflicts and y.any_conflicts


def test_capacity_preflight_fails_closed():
    req=setup('a')
    for j in range(r2.MAX_EVENTS+1):add_type(req,'a','Mechanical',claim=f'id{j}')
    with pytest.raises(r2.ReconciliationRejected,match='P2O_CAPACITY'):
        r2.reconcile(req)


def test_receipts_remain_stable_when_new_revision_is_appended():
    original=setup('a');add_type(original,'a','Mechanical')
    before=r2.reconcile(original)
    appended=copy.deepcopy(original);add_type(appended,'a','Void')
    after=r2.reconcile(appended)
    assert before.revisions[0].journal_receipt_sha256==after.revisions[0].journal_receipt_sha256
    assert before.revisions[0].snapshot_sha256==after.revisions[0].snapshot_sha256
    assert before.request_sha256!=after.request_sha256

def test_p2m_hypothetical_only_branch_is_not_admitted():
    req=setup('cameraHypothesis')
    add_type(req,'cameraHypothesis','Mechanical',node='guess',status=sg.EVIDENCE_HYPOTHETICAL)
    result=r2.reconcile(req)
    assert result.candidates[0].final_decision=='CLAIMS_CONSISTENT'
    assert not result.candidates[0].final_supported_types
    assert not result.any_conflicts
    assert not result.grants_authority
