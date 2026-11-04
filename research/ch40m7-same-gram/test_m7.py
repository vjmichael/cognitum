"""CH40-M7 original-fixture and fail-closed research acceptance."""
from __future__ import annotations
import copy,hashlib,json,os,sys,tempfile,unittest
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('CH40M7_WORKSPACE','/mnt/data')).resolve()
sys.path.insert(0,str(HERE))
from audit_m7 import replay,Refusal
from launch_m7 import CASE_ORDER
from mpfr_gram import decimal_bracket,weight_ceiling

SUMMARY=HERE/'accepted/CH40M7_ALL15_MATCHED_GRAM.json'
class Acceptance(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not SUMMARY.exists() or not (ROOT/'CH40K/traces').exists():
   raise unittest.SkipTest('Original frozen external data/evidence missing')
  cls.s=json.loads(SUMMARY.read_text())
  cls.case='quasi_separated_n80_i00'
  cls.record=HERE/'accepted'/(cls.case+'_arb_gram.json')
 def test_all15_and_frozen_hash_pins(self):
  self.assertEqual(set(r['case'] for r in self.s['rows']),set(CASE_ORDER))
  pins=json.loads((ROOT/'CH40K/CH40K_ACCEPTANCE.json').read_text())
  for row in self.s['rows']:
   src=ROOT/'CH40K/traces'/(row['case']+'_127_original_mpfr_trace.json')
   self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),row['trace_sha256'])
 def test_equivalent_bound_formula(self):
  for row in self.s['rows']:
   for diff in row['first_split_bound_abs_diff_float']:
    self.assertLess(diff,1e-60)
  self.assertEqual(self.s['both_bound_formulas'],'PSD_GRAM_DOMINANCE')
 def test_accepted_results(self):
  self.assertEqual((self.s['cases'],self.s['accepted_arms']),(15,30))
  self.assertEqual(self.s['independent_replayed_children'],242)
  self.assertEqual(self.s['totals']['arb']['splits'],65)
  self.assertEqual(self.s['totals']['mpfr']['splits'],56)
  self.assertEqual(self.s['wins'],{'arb':5,'mpfr':0,'tie':10})
  self.assertEqual(self.s['scientific_release'],'NO_GO')
 def test_readonly_fresh_one_case(self):
  self.assertEqual(replay(self.record)['status'],'PASS_INDEPENDENT_RATIONAL_REPLAY')
 def test_tampered_original_sha_refused(self):
  r=json.loads(self.record.read_text());r['trace_sha256']='0'*64
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'fake.json';p.write_text(json.dumps(r))
   with self.assertRaisesRegex(Refusal,'SHA mismatch'):replay(p)
 def test_rehashed_unsafe_cap_refused(self):
  from analyze40l import canon,sha
  r=json.loads(self.record.read_text());e=r['events'][-1];c=e['children'][-1]
  c['local_hi']='-1000000';c['effective_cap']='-1000000'
  e['digest']=sha(canon({k:v for k,v in e.items() if k!='digest'}).encode())
  r['journal_tip']=e['digest']
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'fake.json';p.write_text(json.dumps(r))
   with self.assertRaisesRegex(Refusal,'undercuts'):replay(p)
 def test_forged_scientific_status_refused(self):
  r=json.loads(self.record.read_text());r['release_status']='GO'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'fake.json';p.write_text(json.dumps(r))
   with self.assertRaisesRegex(Refusal,'scientific status'):replay(p)
 def test_rational_endpoint_brackets(self):
  for q in (F(-1,7),F(1,7),F(0),F(13,25),F(-10**20,17)):
   lo,hi=map(F,decimal_bracket(q));self.assertLessEqual(lo,q);self.assertGreaterEqual(hi,q)
 def test_proof_verifier_cannot_import_native_engines(self):
  s=(HERE/'audit_m7.py').read_text()
  self.assertNotIn('from mpfr_gram import',s)
  self.assertNotIn('from gram_psd import',s)
  self.assertNotIn('import flint',s)
 def test_30_receipts_exist(self):
  for case in CASE_ORDER:
   for engine in ('arb_gram','mpfr_gram'):
    p=HERE/'accepted'/(case+'_'+engine+'.audit.json');self.assertTrue(p.is_file())
    x=json.loads(p.read_text());self.assertEqual(x['status'],'PASS_INDEPENDENT_RATIONAL_REPLAY')
if __name__=='__main__':unittest.main(verbosity=2)
