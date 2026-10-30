"""C15 T2 P2B independent negative and positive assembly reference tests."""
import unittest
from cognitum.proto import assembly_pb2 as p
from cognitum.spatial_assembly import analyze,AssemblyRejected

def fixture():
    q=p.AssemblyResearchRequest(schema_version=1,graph_id='building',conversation_id='chat',research_only=True)
    for name,kind in [('building','building'),('roomA','room'),('roomB','room'),('beam','beam'),('door','door')]:
        q.objects.add(id=name,kind=kind,source_ref='caller',evidence=p.ASSEMBLY_OBSERVED)
    return q

def membership(q,child='beam',assembly='roomA',role='support',ev=p.ASSEMBLY_OBSERVED):
    return q.memberships.add(part_id=child,assembly_id=assembly,role=role,evidence=ev,source_ref='caller')

class AssemblyTests(unittest.TestCase):
    def test_shared_beam_multiple_parents(self):
        q=fixture();membership(q);membership(q,assembly='roomB')
        ans=analyze(q)
        self.assertEqual(len(ans.roles),2)
        self.assertTrue(all(x.status==p.ASSEMBLY_PRESENT_CLAIM for x in ans.roles))
        self.assertFalse(ans.grants_authority)
    def test_multilevel_composition(self):
        q=fixture();membership(q,'beam','roomA');membership(q,'roomA','building','chamber')
        self.assertEqual(len(analyze(q).roles),2)
    def test_cycles_rejected(self):
        q=fixture();membership(q,'beam','roomA');membership(q,'roomA','beam','reverse')
        with self.assertRaisesRegex(AssemblyRejected,'CYCLE'):analyze(q)
    def test_duplicate_membership(self):
        q=fixture();membership(q);membership(q)
        with self.assertRaisesRegex(AssemblyRejected,'DUPLICATE_MEMBERSHIP'):analyze(q)
    def test_mismatched_part(self):
        q=fixture();membership(q,'ghost')
        with self.assertRaises(AssemblyRejected):analyze(q)
    def test_missing_part_is_unknown_not_absent(self):
        q=fixture();q.requirements.add(assembly_id='roomA',role='support',minimum_count=1,source_ref='schema')
        a=analyze(q).roles[0]
        self.assertEqual(a.status,p.ASSEMBLY_NOT_ESTABLISHED)
    def test_explicit_absence_remains_assertion(self):
        q=fixture();q.absences.add(assembly_id='roomA',role='support',evidence=p.ASSEMBLY_OBSERVED,source_ref='observer')
        self.assertEqual(analyze(q).roles[0].status,p.ASSEMBLY_EXPLICIT_ABSENCE)
    def test_presence_absence_conflict(self):
        q=fixture();membership(q);q.absences.add(assembly_id='roomA',role='support',evidence=p.ASSEMBLY_OBSERVED,source_ref='observer')
        self.assertEqual(analyze(q).roles[0].status,p.ASSEMBLY_CONTRADICTION)
    def test_hypothetical_absence_is_not_factual(self):
        q=fixture();q.absences.add(assembly_id='roomA',role='support',evidence=p.ASSEMBLY_HYPOTHETICAL,source_ref='guess')
        self.assertEqual(analyze(q).roles[0].status,p.ASSEMBLY_NOT_ESTABLISHED)
    def test_hypothetical_membership_not_promoted(self):
        q=fixture();membership(q,ev=p.ASSEMBLY_HYPOTHETICAL)
        self.assertEqual(analyze(q).roles[0].status,p.ASSEMBLY_NOT_ESTABLISHED)
    def test_minimum_required_count(self):
        q=fixture();membership(q);q.requirements.add(assembly_id='roomA',role='support',minimum_count=2,source_ref='schema')
        self.assertEqual(analyze(q).roles[0].status,p.ASSEMBLY_NOT_ESTABLISHED)
        membership(q,'door','roomA','support')
        self.assertEqual(analyze(q).roles[0].status,p.ASSEMBLY_PRESENT_CLAIM)
    def test_function_roles_and_unverified_performance(self):
        q=fixture();membership(q);q.functions.add(assembly_id='roomA',function_id='structural_support',required_roles=['support'],evidence=p.ASSEMBLY_INFERRED,source_ref='claim')
        ans=analyze(q)
        self.assertTrue(ans.functions[0].required_roles_claimed)
        self.assertIn('ROLE_PRESENCE_DOES_NOT_PROVE_FUNCTIONAL_PERFORMANCE',ans.functions[0].reasons)
    def test_function_does_not_promote_absent_role(self):
        q=fixture();q.functions.add(assembly_id='roomA',function_id='accessibility',required_roles=['door'],evidence=p.ASSEMBLY_INFERRED,source_ref='claim')
        self.assertFalse(analyze(q).functions[0].required_roles_claimed)
    def test_scope_authority(self):
        q=fixture();q.grants_authority=True
        with self.assertRaises(AssemblyRejected):analyze(q)
    def test_source_reference_required(self):
        q=fixture();membership(q).source_ref=''
        with self.assertRaises(AssemblyRejected):analyze(q)
    def test_observed_edge_with_hypothetical_object(self):
        q=fixture();q.objects[3].evidence=p.ASSEMBLY_HYPOTHETICAL;membership(q)
        with self.assertRaisesRegex(AssemblyRejected,'CONFLATION'):analyze(q)
    def test_unknown_fields_rejected(self):
        q=fixture();membership(q)
        changed=p.AssemblyResearchRequest()
        changed.ParseFromString(q.SerializeToString()+b"\x80\x06\x01")
        with self.assertRaisesRegex(AssemblyRejected,'UNKNOWN_PROTO_FIELDS'):analyze(changed)
    def test_purity(self):
        q=fixture();membership(q);wire=q.SerializeToString();analyze(q)
        self.assertEqual(q.SerializeToString(),wire)

if __name__=='__main__':unittest.main()
