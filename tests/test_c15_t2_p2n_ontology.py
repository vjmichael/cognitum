"""C15/T2/P2N: tests for finite, provenance-constrained ontology subset."""
import copy
import io
import random
import unittest
from PIL import Image
import pytest
from cognitum import spatial_ontology_subset as t2
from cognitum.proto import spatial_ontology_subset_pb2 as p
from cognitum.proto import spatial_composition_pb2 as sg


def sample():
    r = p.OntologyAuditRequest(schema_version=1, conversation_id='chatA',research_only=True)
    g=r.graph
    g.schema_version=1;g.conversation_id='chatA';g.graph_id='assemblyA';g.research_only=True
    g.nodes.add(node_id='x',kind='component',evidence=sg.EVIDENCE_INFERRED,source_ref='modelA')
    g.nodes.add(node_id='y',kind='component',evidence=sg.EVIDENCE_HYPOTHETICAL,source_ref='modelA')
    r.classes.add(class_id='Entity',source_ref='ontologyA')
    r.classes.add(class_id='Material',parent_class_ids=['Entity'],source_ref='ontologyA')
    r.classes.add(class_id='Mechanical',parent_class_ids=['Material'],source_ref='ontologyA')
    r.classes.add(class_id='Void',parent_class_ids=['Entity'],source_ref='ontologyA')
    r.disjoints.add(first_class_id='Material',second_class_id='Void',source_ref='ontologyA')
    r.assertions.add(node_id='x',class_id='Mechanical',evidence=sg.EVIDENCE_INFERRED,source_ref='cameraA')
    r.assertions.add(node_id='y',class_id='Void',evidence=sg.EVIDENCE_HYPOTHETICAL,source_ref='cameraB')
    return r


def findings(result):
    return {x.node_id: x for x in result.findings}


class OntologySubsetTests(unittest.TestCase):
    def test_transitive_entailment_provenance_determinism(self):
        r=sample(); a,b=t2.audit(r),t2.audit(r)
        self.assertEqual(a.SerializeToString(deterministic=True),b.SerializeToString(deterministic=True))
        self.assertEqual(len(a.request_sha256),32)
        self.assertEqual(len(a.graph_sha256),32)
        self.assertEqual({x.class_id for x in findings(a)['x'].entailed_types}, {'Entity','Material','Mechanical'})
        self.assertEqual(set(findings(a)['x'].entailed_types[0].support_sources),{'cameraA'})
        self.assertEqual(list(findings(a)['y'].entailed_types),[])
        self.assertTrue(a.consistent_with_claimed_evidence)
        self.assertFalse(a.grants_authority)

    def test_disjoint_inferred_subclass_conflict(self):
        r=sample();r.assertions.add(node_id='x',class_id='Void',evidence=sg.EVIDENCE_INFERRED,source_ref='cameraC')
        out=t2.audit(r)
        self.assertFalse(out.consistent_with_claimed_evidence)
        self.assertEqual(list(findings(out)['x'].disjoint_conflicts),['Material|Void|ontologyA'])
        self.assertEqual(list(findings(out)['y'].disjoint_conflicts),[])
        self.assertEqual(out.findings[0].conflicted,True)

    def test_hypothetical_type_never_promoted_by_default(self):
        r=sample();r.assertions.add(node_id='x',class_id='Void',evidence=sg.EVIDENCE_HYPOTHETICAL,source_ref='guess')
        self.assertTrue(t2.audit(r).consistent_with_claimed_evidence)
        r.include_hypotheses=True
        out=t2.audit(r)
        self.assertFalse(out.consistent_with_claimed_evidence)
        self.assertEqual([x.class_id for x in findings(out)['y'].entailed_types],['Entity','Void'])
        self.assertTrue(all(x.hypothetical for x in findings(out)['y'].entailed_types))
        self.assertTrue(next(x for x in findings(out)['x'].entailed_types if x.class_id=='Void').hypothetical)
        self.assertIn('HYPOTHETICAL_RESULTS_INCLUDED_BY_EXPLICIT_REQUEST',out.warnings)

    def test_no_typing_from_kind_string_or_unobserved_absence(self):
        r=sample();r.assertions.clear()
        out=t2.audit(r)
        self.assertTrue(out.consistent_with_claimed_evidence)
        self.assertTrue(all(not x.entailed_types for x in out.findings))

    def test_reject_observed_type_of_hypothetical_node(self):
        r=sample();r.assertions[-1].evidence=sg.EVIDENCE_OBSERVED
        with self.assertRaisesRegex(t2.OntologyRejected,'CONFLATION'):t2.audit(r)

    def test_open_world_absence_is_not_negation(self):
        r=sample(); r.assertions.clear()
        r.assertions.add(node_id='x',class_id='Void',source_ref='claim',evidence=sg.EVIDENCE_INFERRED)
        out=t2.audit(r); self.assertTrue(out.consistent_with_claimed_evidence)
        self.assertNotIn('Material', {x.class_id for x in out.findings[0].entailed_types})
        self.assertIn('OPEN_WORLD_ABSENCE_IS_NOT_NEGATION',out.warnings)

    def test_reject_scope_mismatch_and_elevated_authority(self):
        for edit in ('scope','top_authority','graph_authority','unknown_field','graph_unknown_field'):
            r=sample()
            if edit=='scope':r.conversation_id='chatB'
            if edit=='top_authority':r.grants_authority=True
            if edit=='graph_authority':r.graph.grants_authority=True
            if edit=='unknown_field':
                raw=r.SerializeToString()+b'\xc0\x3e\x01';r=p.OntologyAuditRequest.FromString(raw)
            if edit=='graph_unknown_field':
                g=sg.StructureGraph.FromString(r.graph.SerializeToString()+b'\xc0\x3e\x01')
                r.graph.CopyFrom(g)
            with self.subTest(edit=edit), self.assertRaises(t2.OntologyRejected):t2.audit(r)

    def test_class_cycles_and_unknown_disjoint_class_rejected(self):
        r=sample(); r.classes[0].parent_class_ids.append('Mechanical')
        with self.assertRaisesRegex(t2.OntologyRejected,'TAXONOMY_CYCLE'):t2.audit(r)
        r=sample(); r.disjoints[0].second_class_id='Missing'
        with self.assertRaisesRegex(t2.OntologyRejected,'INVALID_DISJOINT'):t2.audit(r)

    def test_capacity_and_duplicate_axioms_rejected(self):
        r=sample();r.classes.add(class_id='Material',source_ref='foo')
        with self.assertRaisesRegex(t2.OntologyRejected,'INVALID_ONTOLOGY_CLASS'):t2.audit(r)
        r=sample();r.disjoints.add(first_class_id='Void',second_class_id='Material',source_ref='other')
        with self.assertRaisesRegex(t2.OntologyRejected,'DUPLICATE_DISJOINT'):t2.audit(r)
        r=sample()
        for i in range(128):r.classes.add(class_id='Extra'+str(i),source_ref='schema')
        with self.assertRaisesRegex(t2.OntologyRejected,'ONTOLOGY_CAPACITY_LIMIT'):t2.audit(r)

    def test_evidence_provenance_missing_or_duplicate(self):
        r=sample();r.assertions[0].source_ref=''
        with self.assertRaisesRegex(t2.OntologyRejected,'INVALID_TYPE'):t2.audit(r)
        r=sample();r.assertions.add().CopyFrom(r.assertions[0])
        with self.assertRaisesRegex(t2.OntologyRejected,'DUPLICATE_TYPE'):t2.audit(r)

    def test_mixed_support_not_hypothetical_when_independently_inferred(self):
        r=sample();r.include_hypotheses=True
        r.assertions.add(node_id='x',class_id='Mechanical',source_ref='unverifiedGuess',evidence=sg.EVIDENCE_HYPOTHETICAL)
        types=findings(t2.audit(r))['x'].entailed_types
        for typ in types:self.assertFalse(typ.hypothetical)
        self.assertEqual(sorted(types[0].support_sources),['cameraA','unverifiedGuess'])

    def test_p2m_safe_integration_and_mutation_rejection(self):
        from cognitum import spatial_p2m_pipeline as p2m
        from cognitum.proto import spatial_appearance_pipeline_pb2 as pp
        pic=Image.new('RGB',(48,48),(22,88,14));b=io.BytesIO();pic.save(b,'PNG')
        r=pp.P2MFeatureRequest(schema_version=1,conversation_id='chatA',sequence_id='sample',request_id='req',research_only=True)
        r.model.CopyFrom(p2m.histogram_model())
        f=r.frames.add(frame=1,source_ref='frame.1',encoded_image=b.getvalue())
        f.boxes.add(x=3,y=3,w=12,h=12)
        features=p2m.extract(r)
        h=p2m.integration_handoff(r,features,{(1,0):1})
        result=t2.audit_p2m_handoff(r,features,h)
        self.assertTrue(result.consistent_with_claimed_evidence)
        self.assertEqual([x.class_id for x in result.findings[0].entailed_types],['2d_evidence_candidate','2d_identity_hypothesis'])
        self.assertTrue(all(x.hypothetical for x in result.findings[0].entailed_types))
        self.assertFalse(result.grants_authority)
        modified=copy.deepcopy(h);modified.t3_projection_blocked_without_calibration=False
        with self.assertRaisesRegex(t2.OntologyRejected,'INVALID_P2M_HANDOFF'):
            t2.audit_p2m_handoff(r,features,modified)
        modified=copy.deepcopy(h);modified.t2_hypothetical_graph.nodes[0].evidence=sg.EVIDENCE_OBSERVED
        with self.assertRaisesRegex(t2.OntologyRejected,'P2M_HANDOFF_MISMATCH'):
            t2.audit_p2m_handoff(r,features,modified)


def test_independent_networkx_subclass_closure_and_rdflib_reachability():
    """168 randomized, bounded DAGs against independent NetworkX and RDFLib APIs."""
    nx=pytest.importorskip('networkx')
    rdf=pytest.importorskip('rdflib')
    from rdflib import Graph,URIRef,RDFS
    rnd=random.Random(152826)
    for case in range(168):
        req=p.OntologyAuditRequest(schema_version=1,conversation_id='chat',research_only=True)
        g=req.graph;g.schema_version=1;g.conversation_id='chat';g.graph_id='g';g.research_only=True
        g.nodes.add(node_id='object',kind='unknown',evidence=sg.EVIDENCE_INFERRED,source_ref='caller')
        graph=nx.DiGraph();rg=Graph()
        count=rnd.randint(3,14)
        names=[f'T{i}' for i in range(count)]
        for name in names:graph.add_node(name)
        for i,name in enumerate(names):
            parents=rnd.sample(names[:i], k=rnd.randint(0,min(3,i)))
            req.classes.add(class_id=name,parent_class_ids=parents,source_ref='ontology')
            for parent in parents:
                graph.add_edge(name,parent)
                rg.add((URIRef('urn:'+name),RDFS.subClassOf,URIRef('urn:'+parent)))
        selected=rnd.choice(names)
        req.assertions.add(node_id='object',class_id=selected,evidence=sg.EVIDENCE_INFERRED,source_ref='object_source')
        actual={a.class_id for a in t2.audit(req).findings[0].entailed_types}
        expected=nx.descendants(graph, selected) | {selected}
        rdf_expected={str(u).removeprefix('urn:') for u in rg.transitive_objects(URIRef('urn:'+selected),RDFS.subClassOf)}
        assert actual==expected==rdf_expected, f'case={case}'


def test_independent_disjoint_differential_72_seeded_cases():
    """Independent explicit set-intersection oracle, not the implementation helper."""
    rnd=random.Random(20261028)
    for case in range(72):
        r=sample()
        r.assertions.clear()
        choices=rnd.sample(['Material','Void','Mechanical'],k=rnd.randint(0,3))
        for cls in choices:
            r.assertions.add(node_id='x',class_id=cls,source_ref='source'+cls,evidence=sg.EVIDENCE_INFERRED)
        result=t2.audit(r)
        # Material includes Mechanical; Void is disjoint with either.
        expectation='Void' in choices and any(x in choices for x in ('Material','Mechanical'))
        assert bool(result.findings[0].disjoint_conflicts)==expectation,case
        assert result.consistent_with_claimed_evidence != expectation,case


def test_relation_type_rule_disjointness_and_provenance():
    r=sample()
    r.classes.add(class_id='Assembly',parent_class_ids=['Entity'],source_ref='ontologyA')
    r.graph.nodes.add(node_id='parent',kind='assembly',evidence=sg.EVIDENCE_INFERRED,source_ref='collector')
    r.graph.edges.add(from_id='x',to_id='parent',relation=sg.STRUCTURE_PART_OF,
                      evidence=sg.EVIDENCE_INFERRED,source_ref='partObserved')
    r.relation_rules.add(relation=sg.STRUCTURE_PART_OF,from_class_id='Void',
                         to_class_id='Assembly',source_ref='ruleSource')
    out=t2.audit(r)
    assert not out.consistent_with_claimed_evidence
    fx=findings(out)['x']
    assert fx.conflicted and fx.disjoint_conflicts[0]=='Material|Void|ontologyA'
    pclass={x.class_id:x for x in findings(out)['parent'].entailed_types}
    assert 'Assembly' in pclass and set(pclass['Assembly'].support_sources)=={'partObserved','ruleSource'}
    assert 'Void' in {x.class_id for x in fx.entailed_types}


def test_hypothetical_edge_and_no_undeclared_rule():
    r=sample();r.graph.nodes.add(node_id='parent',kind='assembly',evidence=sg.EVIDENCE_INFERRED,source_ref='collector')
    r.graph.edges.add(from_id='y',to_id='parent',relation=sg.STRUCTURE_PART_OF,
                      evidence=sg.EVIDENCE_HYPOTHETICAL,source_ref='guessedEdge')
    r.relation_rules.add(relation=sg.STRUCTURE_PART_OF,from_class_id='Mechanical',
                         to_class_id='Material',source_ref='ontologyA')
    assert not findings(t2.audit(r))['parent'].entailed_types
    r.include_hypotheses=True
    out=t2.audit(r)
    assert all(x.hypothetical for x in findings(out)['parent'].entailed_types)
    assert not out.findings[0].conflicted
    r.relation_rules.clear()
    assert not findings(t2.audit(r))['parent'].entailed_types


def test_invalid_relation_signature_rejected():
    r=sample()
    r.relation_rules.add(relation=sg.STRUCTURE_CONNECTED_TO,from_class_id='Material',
                         to_class_id='Void',source_ref='schema')
    with pytest.raises(t2.OntologyRejected,match='INVALID_RELATION_TYPE_RULE'):
        t2.audit(r)
    r.relation_rules.clear()
    r.relation_rules.add(relation=sg.STRUCTURE_PART_OF,from_class_id='Void',
                         to_class_id='Material',source_ref='schema')
    r.relation_rules.add(relation=sg.STRUCTURE_PART_OF,from_class_id='Void',
                         to_class_id='Material',source_ref='schema2')
    with pytest.raises(t2.OntologyRejected,match='DUPLICATE_RELATION_TYPE_RULE'):
        t2.audit(r)
