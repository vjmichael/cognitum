"""Research acceptance regression: verify frozen records and fail-closed promotion boundaries."""
import unittest,json,hashlib,sys
from pathlib import Path
R=Path(__file__).resolve().parent
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.a=json.loads((R/'CH40M3_ACCEPTANCE.json').read_text())
  cls.point=json.loads((R/'results/flint15_point_check.json').read_text())
  cls.region=json.loads((R/'results/flint15_region_hadamard.json').read_text())
  cls.scip=json.loads((R/'results/scip15_bounded.json').read_text())
  cls.candidates=json.loads((R/'results/scip_verified_candidates.json').read_text())
  cls.perf=json.loads((R/'results/flint_vs_rational_cpu.json').read_text())
 def test_immutable_15_case_hashes(self):
  pins=Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json')
  if not pins.is_file():self.skipTest('External original CH40-K frozen pins not present; no synthetic fixtures used')
  expected={x['case']:x['trace_sha256'] for x in json.loads(pins.read_text())['cases']}
  self.assertEqual(len(expected),15)
  self.assertEqual({x['case']:x['trace_sha256'] for x in self.point['cases']},expected)
  self.assertEqual({x['case']:x['source_sha256'] for x in self.region['cases']},expected)
 def test_flint_point_enclosure_acceptance(self):
  self.assertEqual(self.point['passing'],15)
  self.assertTrue(all(x['status']=='INDEPENDENT_POINT_OVERLAP_VERIFIED' and x['flint_contains_reference'] for x in self.point['cases']))
 def test_frozen_region_bounds_not_promoted(self):
  self.assertEqual(self.region['conservative_agreement'],15)
  self.assertFalse(any(x.get('improves_frozen_leaf_cap') for x in self.region['cases']))
  self.assertTrue(self.perf['all_conservative'])
 def test_scip_did_not_promote_dual_bounds(self):
  self.assertTrue(self.scip['complete'])
  self.assertEqual(self.scip['native_executed_cases'],15)
  self.assertEqual(self.scip['proven_global_bounds'],0)
  self.assertTrue(all('solver_bound_unverified' not in x for x in self.scip['cases']))
 def test_scip_candidates_independently_checked(self):
  self.assertEqual(self.scip['candidate_cases'],3)
  self.assertEqual(len(self.candidates['candidate_checks']),3)
  self.assertTrue(all(x.get('independent_point_overlap') for x in self.candidates['candidate_checks']))
  self.assertFalse(any(x.get('material_verified_gain_over_original') for x in self.candidates['candidate_checks']))
 def test_native_missing_dependencies_fail_closed(self):
  self.assertEqual(self.a['ibex']['native_build'],'BLOCKED_BEFORE_COMPILE')
  self.assertEqual(self.a['ipopt']['native_execution'],'BLOCKED_MISSING_SHARED_LIBRARIES')
  self.assertFalse(self.a['global_0_05_tolerance_proved'])
  self.assertEqual(self.a['scientific_release'],'NO_GO')
 def test_native_flint_and_scip_actual_import(self):
  if not (R/'site/flint').exists() or not (R/'site/pyscipopt').exists():self.skipTest('Optional native research wheels not installed beside extracted source')
  sys.path.insert(0,str(R/'site'))
  try:
   import flint,pyscipopt
   self.assertEqual(flint.__version__,'0.9.0')
   self.assertEqual(pyscipopt.Model().getMajorVersion(),10)
  finally:sys.path.pop(0)
 def test_kernel_timing_honest_scope(self):
  self.assertGreater(self.perf['total_rational_cpu_seconds'],self.perf['total_flint_cpu_seconds'])
  self.assertFalse(self.perf['any_frozen_cap_improved'])
if __name__=='__main__':unittest.main()

