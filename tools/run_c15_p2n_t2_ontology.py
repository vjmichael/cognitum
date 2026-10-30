"""Reproducible, offline C15/T2/P2N bounded taxonomy/structure smoke.

Usage: PYTHONPATH=. python tools/run_c15_p2n_t2_ontology.py
A deterministic example, NOT an external OWL 2 benchmark or sensor reading.
"""
import json
from cognitum.proto import spatial_composition_pb2 as sg
from cognitum.proto import spatial_ontology_subset_pb2 as pb
from cognitum.spatial_ontology_subset import audit


def run():
    r = pb.OntologyAuditRequest(schema_version=1,conversation_id='demo.chat',research_only=True)
    g=r.graph; g.schema_version=1;g.conversation_id='demo.chat';g.graph_id='demo.graph';g.research_only=True
    g.nodes.add(node_id='part',kind='unknown',evidence=sg.EVIDENCE_INFERRED,source_ref='caller.claim')
    g.nodes.add(node_id='whole',kind='unknown',evidence=sg.EVIDENCE_INFERRED,source_ref='caller.claim')
    g.edges.add(from_id='part',to_id='whole',relation=sg.STRUCTURE_PART_OF,
                evidence=sg.EVIDENCE_INFERRED,source_ref='caller.edge')
    for name,parents in [('Thing',[]),('Solid',['Thing']),('Void',['Thing']),('Assembly',['Thing'])]:
        r.classes.add(class_id=name,parent_class_ids=parents,source_ref='caller.taxonomy')
    r.disjoints.add(first_class_id='Solid',second_class_id='Void',source_ref='caller.disjoint')
    r.relation_rules.add(relation=sg.STRUCTURE_PART_OF,from_class_id='Solid',
                         to_class_id='Assembly',source_ref='caller.signature')
    r.assertions.add(node_id='part',class_id='Void',evidence=sg.EVIDENCE_INFERRED,source_ref='caller.type')
    result=audit(r)
    return dict(status='claimed_type_contradiction_detected' if not result.consistent_with_claimed_evidence else 'unexpected',
        research_only=result.research_only, grants_authority=result.grants_authority,
        request_sha256=result.request_sha256.hex(),graph_sha256=result.graph_sha256.hex(),
        findings=[dict(node_id=f.node_id,types=[t.class_id for t in f.entailed_types],
            conflicts=list(f.disjoint_conflicts)) for f in result.findings],
        full_owl2_reasoner_evaluation=None, real_world_structure_accuracy=None)

if __name__ == '__main__':
    print(json.dumps(run(),sort_keys=True,indent=2))
