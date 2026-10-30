"""T2 P2C: bounded alternatives, nonpromotion and independent closed-graph comparison."""
import math,unittest
from cognitum.proto import structural_hypotheses_pb2 as pb
from cognitum.spatial_structural_hypotheses import analyze,StructuralHypothesesRejected

def fixture():
 q=pb.StructuralHypothesisRequest(schema_version=1,graph_id='building',conversation_id='chat',research_only=True)
 a=q.hypotheses.add(hypothesis_id='beam',prior_weight=1)
 a.assertions.add(assembly_id='room',part_id='support1',role='support',present=True)
 b=q.hypotheses.add(hypothesis_id='no_beam',prior_weight=1)
 b.assertions.add(assembly_id='room',part_id='support1',role='support',present=False)
 q.functions.add(function_id='structural',assembly_id='room',required_roles=['support'],excluded_roles=['unsafe'])
 return q

def evidence(q,lik_a=.9,lik_b=.1,ref='test',tick=1):
 o=q.observations.add(source_ref=ref,tick=tick)
 o.likelihoods.add(hypothesis_id='beam',likelihood=lik_a)
 o.likelihoods.add(hypothesis_id='no_beam',likelihood=lik_b)
 return o

class StructuralHypothesesTests(unittest.TestCase):
 def test_equal_priors_ambiguous(self):
  x=analyze(fixture());self.assertTrue(x.ambiguous);self.assertEqual([a.relative_weight for a in x.ranked],[.5,.5]);self.assertFalse(x.grants_authority)
 def test_competing_likelihoods(self):
  q=fixture();evidence(q);r=analyze(q);self.assertAlmostEqual(r.ranked[0].relative_weight,.9);self.assertFalse(r.ambiguous)
 def test_function_not_certified(self):
  q=fixture();x=analyze(q);self.assertEqual(x.ranked[0].functions[0].status,'STRUCTURAL_PRECONDITIONS_CLAIMED');self.assertIn('NO_FUNCTION_PERFORMANCE_CERTIFICATION',x.ranked[0].functions[0].reasons)
 def test_missing_role_not_absent(self):
  q=fixture();q.hypotheses[0].ClearField('assertions');x=analyze(q);self.assertEqual(next(a for a in x.ranked if a.hypothesis_id=='beam').functions[0].status,'UNDETERMINED')
 def test_explicit_absence_contradicted(self):
  x=analyze(fixture());self.assertEqual(next(a for a in x.ranked if a.hypothesis_id=='no_beam').functions[0].status,'CONTRADICTED')
 def test_excluded_role_contradicts(self):
  q=fixture();q.hypotheses[0].assertions.add(assembly_id='room',part_id='hazard',role='unsafe',present=True);x=analyze(q);self.assertEqual(next(a for a in x.ranked if a.hypothesis_id=='beam').functions[0].status,'CONTRADICTED')
 def test_inconsistent_hypothesis_weight_zero(self):
  q=fixture();q.hypotheses[0].assertions.add(assembly_id='room',part_id='support1',role='support',present=False)
  r=analyze(q);self.assertFalse(r.ranked[-1].internally_consistent);self.assertEqual(r.ranked[-1].relative_weight,0)
 def test_cycle_hypothesis_weight_zero(self):
  q=fixture();q.hypotheses[0].assertions.add(assembly_id='support1',part_id='room',role='parent',present=True)
  r=analyze(q);self.assertIn('PART_WHOLE_CYCLE',r.ranked[-1].contradictions)
 def test_all_hypotheses_invalid(self):
  q=fixture()
  for h in q.hypotheses:h.assertions.add(assembly_id='room',part_id='room',role='bogus',present=True)
  with self.assertRaises(StructuralHypothesesRejected):analyze(q)
 def test_replayed_source_tick(self):
  q=fixture();evidence(q);evidence(q,ref='test',tick=1)
  with self.assertRaisesRegex(StructuralHypothesesRejected,'REPLAY'):analyze(q)
 def test_incomplete_vector(self):
  q=fixture();evidence(q).likelihoods.pop()
  with self.assertRaises(StructuralHypothesesRejected):analyze(q)
 def test_zero_likelihood_rejected(self):
  q=fixture();evidence(q,lik_a=0)
  with self.assertRaises(StructuralHypothesesRejected):analyze(q)
 def test_nan_rejected(self):
  q=fixture();q.hypotheses[0].prior_weight=float('nan')
  with self.assertRaises(StructuralHypothesesRejected):analyze(q)
 def test_unauthorized(self):
  q=fixture();q.grants_authority=True
  with self.assertRaises(StructuralHypothesesRejected):analyze(q)
 def test_unrecognized_field_rejected(self):
  q=fixture();p=pb.StructuralHypothesisRequest.FromString(q.SerializeToString()+b'\xd8\x07\x01')
  with self.assertRaises(StructuralHypothesesRejected):analyze(p)
 def test_stable_normalization(self):
  q=fixture()
  for i in range(80):evidence(q,.01,.99,ref='r'+str(i),tick=i+1)
  r=analyze(q);self.assertAlmostEqual(sum(x.relative_weight for x in r.ranked),1)
 def test_independent_numpy_bayes(self):
  import numpy as np
  q=fixture();evidence(q,.7,.2);evidence(q,.6,.3,ref='other',tick=2)
  expected=np.array([.7*.6,.2*.3]);expected/=expected.sum()
  r=analyze(q);self.assertAlmostEqual(r.ranked[0].relative_weight,expected[0],places=12)

if __name__=='__main__':unittest.main()
