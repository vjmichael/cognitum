"""CH40-M.6 frozen-data acceptance and malformed research journal refusal tests."""
from __future__ import annotations
import copy,hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
try:
 from audit_m6 import audit_file,validate,Refusal,DEFAULT_TRACES,DEFAULT_PIN
 from compare_m6 import validate_original
 from analyze40l import canon,sha
 IMPORT_ERROR=None
except (ImportError,ModuleNotFoundError) as exc:
 IMPORT_ERROR=str(exc)
DATA=ROOT/'accepted'

class M6Acceptance(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if IMPORT_ERROR:raise unittest.SkipTest('Native libraries or independent original checker absent: '+IMPORT_ERROR)
  if not (DATA/'CH40M6_ALL15_SEARCH_COMPARISON.json').exists() or not DEFAULT_TRACES.is_dir():
   raise unittest.SkipTest('Original pinned research fixtures/acceptance absent')
  cls.case='quasi_separated_n80_i00'
  cls.record=json.loads((DATA/(cls.case+'.json')).read_text())
  cls.trace,cls.orig,cls.trace_sha=validate_original(cls.case)
 def test_original_source_hash_pinned(self):
  self.assertEqual(self.trace_sha,self.record['trace_sha256'])
 def test_all15_aggregate(self):
  r=json.loads((DATA/'CH40M6_ALL15_SEARCH_COMPARISON.json').read_text())
  self.assertEqual(r['input_case_count'],15)
  self.assertEqual(len({q['case'] for q in r['rows']}),15)
  self.assertEqual(r['total_reverified_children'],348)
  self.assertEqual((r['total_flint_splits'],r['total_mpfr_splits']),(153,21))
  self.assertEqual((r['strict_flint_progress_wins'],r['ties_at_1e_minus10']),(12,3))
  self.assertTrue(all(x['flint_remaining_gap']>.05 and x['mpfr_remaining_gap']>.05 for x in r['rows']))
 def test_independent_rational_audit_of_real_input(self):
  rows=validate(self.record,self.orig,self.trace['certificate'])
  self.assertEqual(len(rows),2)
  self.assertEqual(sum(a['verified_children'] for a in rows),28)
 def test_tampered_hash_chain_refused(self):
  r=copy.deepcopy(self.record)
  r['flint']['events'][0]['children'][0]['local_hi']='0'
  with self.assertRaisesRegex(Refusal,'chain corrupted'):validate(r,self.orig,self.trace['certificate'])
 def test_changed_branch_selection_refused_even_with_rehashed_event(self):
  r=copy.deepcopy(self.record)
  event=r['legacy']['events'][0];event['parent_id']='not-the-worst-leaf'
  body={k:v for k,v in event.items() if k!='digest'};event['digest']=sha(canon(body).encode())
  with self.assertRaisesRegex(Refusal,'branch-selection'):validate(r,self.orig,self.trace['certificate'])
 def test_forged_underbound_refused_even_with_valid_event_hash(self):
  # Use last event (no downstream hash update needed) and set its *second*
  # child's native local ceiling to a grossly unsafe value.
  r=copy.deepcopy(self.record)
  e=r['flint']['events'][-1];child=e['children'][1]
  child['local_hi']='-1000000';child['effective_cap']='-1000000'
  e['digest']=sha(canon({k:v for k,v in e.items() if k!='digest'}).encode())
  r['flint']['journal_tip']=e['digest']
  with self.assertRaisesRegex(Refusal,'candidate upper below'):validate(r,self.orig,self.trace['certificate'])
 def test_sci_release_cannot_be_promoted(self):
  r=copy.deepcopy(self.record);r['legacy']['scientific_release']='GO'
  with self.assertRaisesRegex(Refusal,'backend/status confusion'):validate(r,self.orig,self.trace['certificate'])
 def test_source_pin_tamper_refused(self):
  r=copy.deepcopy(self.record);r['trace_sha256']='0'*64
  import tempfile
  with tempfile.TemporaryDirectory() as t:
   file=Path(t)/'fake.json';file.write_text(json.dumps(r))
   with self.assertRaisesRegex(Refusal,'trace SHA pin'):audit_file(file)
 def test_auditor_source_has_no_native_imports(self):
  s=(ROOT/'audit_m6.py').read_text()
  self.assertNotIn('from gram_psd import',s)
  self.assertNotIn('from native_mpfr40l3 import',s)
  self.assertNotIn('import flint',s)

if __name__=='__main__': unittest.main(verbosity=2)
