import unittest
from cognitum.proto import spatial_composition_pb2 as p
from cognitum.spatial_composition import query,validate,StructureRejected

def fixture():
    g=p.StructureGraph(schema_version=1,graph_id='building',conversation_id='thread',research_only=True)
    for ident,kind,ev in [('building','structure',p.EVIDENCE_OBSERVED),('wall','wall',p.EVIDENCE_INFERRED),('pipe','pipe',p.EVIDENCE_HYPOTHETICAL),('room','space',p.EVIDENCE_INFERRED)]:
        g.nodes.add(node_id=ident,kind=kind,evidence=ev,source_ref='source_1')
    g.edges.add(from_id='wall',to_id='building',relation=p.STRUCTURE_PART_OF,evidence=p.EVIDENCE_INFERRED,source_ref='source_1')
    g.edges.add(from_id='pipe',to_id='wall',relation=p.STRUCTURE_PART_OF,evidence=p.EVIDENCE_HYPOTHETICAL,source_ref='source_1')
    g.edges.add(from_id='building',to_id='room',relation=p.STRUCTURE_CONTAINS,evidence=p.EVIDENCE_INFERRED,source_ref='source_1')
    return g

class CompositionTests(unittest.TestCase):
 def test_parts_and_ancestors(self):
    g=fixture();r=query(g,p.StructureQuery(schema_version=1,graph_id='building',conversation_id='thread',target_id='wall'))
    self.assertEqual(list(r.ancestors),['building']);self.assertEqual(list(r.descendants),[])
    self.assertTrue(r.research_only);self.assertFalse(r.grants_authority)
 def test_hypothetical_pipe_not_factual(self):
    g=fixture();q=p.StructureQuery(schema_version=1,graph_id='building',conversation_id='thread',target_id='building')
    r=query(g,q);self.assertNotIn('pipe',r.descendants)
    q.include_hypotheses=True;self.assertIn('pipe',query(g,q).descendants)
 def test_no_invented_internal_parts(self):
    g=fixture();g.nodes.pop();g.edges.pop();self.assertNotIn('pipe',query(g,p.StructureQuery(schema_version=1,graph_id='building',conversation_id='thread',target_id='building')).descendants)
 def test_cycle_rejected(self):
    g=fixture();g.edges.add(from_id='building',to_id='pipe',relation=p.STRUCTURE_PART_OF,evidence=p.EVIDENCE_INFERRED,source_ref='source_1')
    with self.assertRaisesRegex(StructureRejected,'CYCLE'):validate(g)
 def test_multiple_parents_rejected(self):
    g=fixture();g.edges.add(from_id='wall',to_id='room',relation=p.STRUCTURE_PART_OF,evidence=p.EVIDENCE_INFERRED,source_ref='source_1')
    with self.assertRaisesRegex(StructureRejected,'MULTIPLE'):validate(g)
 def test_no_fake_observed_hypothesis(self):
    g=fixture();g.edges[1].evidence=p.EVIDENCE_OBSERVED
    with self.assertRaisesRegex(StructureRejected,'CONFLATION'):validate(g)
 def test_scope_bound(self):
    with self.assertRaisesRegex(StructureRejected,'SCOPE'):query(fixture(),p.StructureQuery(schema_version=1,graph_id='building',conversation_id='other',target_id='building'))
 def test_prohibited_authority(self):
    g=fixture();g.grants_authority=True
    with self.assertRaises(StructureRejected):validate(g)
 def test_missing_source_rejected(self):
    g=fixture();g.nodes[1].source_ref=''
    with self.assertRaises(StructureRejected):validate(g)
 def test_hypothetical_connection_is_hidden_by_default(self):
    g=fixture();g.edges.add(from_id="room",to_id="wall",relation=p.STRUCTURE_CONNECTED_TO,evidence=p.EVIDENCE_HYPOTHETICAL,source_ref="source_1")
    q=p.StructureQuery(schema_version=1,graph_id="building",conversation_id="thread",target_id="wall")
    self.assertNotIn("room",query(g,q).connections)
    q.include_hypotheses=True;self.assertIn("room",query(g,q).connections)
 def test_no_automatic_semantics(self):
    g=fixture();g.nodes[0].kind='human'
    r=query(g,p.StructureQuery(schema_version=1,graph_id='building',conversation_id='thread',target_id='building'))
    self.assertEqual(set(r.descendants),{'wall','room'})

if __name__=='__main__':unittest.main()
