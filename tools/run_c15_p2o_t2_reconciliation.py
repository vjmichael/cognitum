"""Reproduce the C15 T2 P2O claim-revision example without external inputs.

Usage: PYTHONPATH=. python tools/run_c15_p2o_t2_reconciliation.py [--out FILE]
Research-only illustrative fixture, not a real evidence benchmark or OWL run.
"""
import argparse
import json
from pathlib import Path
from google.protobuf.json_format import MessageToDict
from cognitum import spatial_structural_reconciliation as r2
from cognitum.proto import spatial_structural_reconciliation_pb2 as p
from cognitum.proto import spatial_composition_pb2 as sg


def fixture():
    req=p.T2ReconciliationRequest(schema_version=1,conversation_id='replayDemo',research_only=True)
    base=req.ontology_template
    base.schema_version=1;base.conversation_id='replayDemo';base.research_only=True
    g=base.graph
    g.schema_version=1;g.conversation_id='replayDemo';g.graph_id='sampleAssembly';g.research_only=True
    g.nodes.add(node_id='component',kind='part',evidence=sg.EVIDENCE_INFERRED,source_ref='callerNode')
    for class_id,parents in [('Entity',[]),('Solid',['Entity']),('MachinePart',['Solid']),('Void',['Entity'])]:
        base.classes.add(class_id=class_id,parent_class_ids=parents,source_ref='schemaClaim')
    base.disjoints.add(first_class_id='Solid',second_class_id='Void',source_ref='schemaDisjointClaim')
    req.candidates.add(candidate_id='candidateA',explanation='Mechanical part; conflicting void label later retired')
    req.candidates.add(candidate_id='candidateB',explanation='Void hypothesis; no contradiction with current claims')
    def add(c,eid,num,ctype,cid):
        e=req.events.add(event_id=eid,candidate_id=c,sequence=num,
                         source_ref='researchSource',rationale='caller supplied a classification')
        e.add_type.claim_id=cid
        e.add_type.claim.node_id='component';e.add_type.claim.class_id=ctype
        e.add_type.claim.evidence=sg.EVIDENCE_INFERRED;e.add_type.claim.source_ref=cid
    add('candidateA','revision1',1,'MachinePart','mechanicalClaim')
    add('candidateA','revision2',2,'Void','voidClaim')
    e=req.events.add(event_id='revision3',candidate_id='candidateA',sequence=3,
                     source_ref='revisionSource',rationale='caller retracted disputed void label')
    e.retract.claim_id='voidClaim'
    add('candidateB','revision4',1,'Void','voidOnlyClaim')
    return req


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    result=r2.reconcile(fixture())
    payload={
        'phase':'C15 T2 P2O',
        'origin':'synthetic caller-claim fixture (not source-authenticated)',
        'result':MessageToDict(result,preserving_proto_field_name=True),
        'acceptance':'No real hypothesis selection, 3D projection, scene mutation or Lu permission',
    }
    content=json.dumps(payload,sort_keys=True,indent=2)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(content,encoding='utf-8')
    else:print(content,end='')
    return 0


if __name__=='__main__':raise SystemExit(main())
