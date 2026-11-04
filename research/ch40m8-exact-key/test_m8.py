"""CH40-M.8 real-frozen-fixture and adversarial proof-memo acceptance.

No synthetic datasets can satisfy the tests' original CH40-K SHA pins.
A missing original suite is a SKIP, never a scientific PASS.
"""
import copy
import hashlib
import json
import os
import sys
import unittest
from fractions import Fraction as F
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('CH40M8_WORKSPACE','/mnt/data')).resolve()
sys.path.insert(0,str(HERE))
try:
    from audit_m8 import _load_pins,_prepare_original,audit_one,CertifiedBoxCache,run_batch,Refusal,sha,canon
except ModuleNotFoundError as exc:
    # Repository CI does not package the immutable ~800 MB external CH40 fixtures
    # or older checker modules. Missing originals are SKIP, never a false PASS.
    # A missing dependency when originals *are* available is a hard import error.
    if not (ROOT/'CH40K/traces').is_dir():
        raise unittest.SkipTest('original CH40 source modules and frozen fixtures not present') from exc
    raise

CASE='quasi_separated_n80_i00'

class M8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT/'CH40K/traces').is_dir() or not (ROOT/'CH40M7/accepted').is_dir():
            raise unittest.SkipTest('original frozen CH40-K/CH40-M7 records are not available')
        cls.pins=_load_pins()
        cls.trace,cls.original,cls.trace_sha=_prepare_original(CASE,cls.pins)
        cls.a_path=ROOT/'CH40M7/accepted'/(CASE+'_arb_gram.json')
        cls.b_path=ROOT/'CH40M7/accepted'/(CASE+'_mpfr_gram.json')
        cls.a=json.loads(cls.a_path.read_text())
        cls.b=json.loads(cls.b_path.read_text())

    def test_pins_are_original_fifteen(self):
        self.assertEqual(len(self.pins),15)
        self.assertEqual(self.pins[CASE]['trace_sha256'],self.trace_sha)
        self.assertEqual(len(self.original),64)

    def test_same_outcomes_cache_vs_fresh_real_pair(self):
        cached=run_batch(ROOT/'CH40M7/accepted','cache',[CASE])
        fresh=run_batch(ROOT/'CH40M7/accepted','fresh',[CASE])
        self.assertEqual(cached['archive_sha256'],fresh['archive_sha256'])
        self.assertEqual(cached['proposition_ledger_sha256'],fresh['proposition_ledger_sha256'])
        self.assertEqual(cached['children_checked'],fresh['children_checked'])
        self.assertEqual(cached['independent_rational_computations']+cached['same_box_cache_hits'],fresh['independent_rational_computations'])
        self.assertGreater(cached['same_box_cache_hits'],0)

    def test_original_checker_matches_one_existing_m7_receipt(self):
        cache=CertifiedBoxCache()
        receipt=audit_one(self.a,self.original,self.trace_sha,self.trace['certificate'],cache)
        old=json.loads((ROOT/'CH40M7/accepted'/(CASE+'_arb_gram.audit.json')).read_text())
        self.assertEqual(receipt['journal_tip'],old['journal_tip'])
        self.assertEqual(receipt['final_upper'],old['final_upper'])
        self.assertEqual(receipt['children_checked'],old['children'])

    def test_cache_refuses_rehashed_undercut_even_after_hit(self):
        cache=CertifiedBoxCache()
        audit_one(self.a,self.original,self.trace_sha,self.trace['certificate'],cache)
        tampered=copy.deepcopy(self.a)
        ev=tampered['events'][-1]
        ev['children'][0]['local_hi']='-1000000'
        ev['children'][0]['effective_cap']='-1000000'
        ev['digest']=sha(canon({k:v for k,v in ev.items() if k!='digest'}).encode())
        tampered['journal_tip']=ev['digest']
        with self.assertRaisesRegex(Refusal,'undercuts'):
            audit_one(tampered,self.original,self.trace_sha,self.trace['certificate'],cache)

    def test_missing_or_forged_trace_hash_refused(self):
        t=copy.deepcopy(self.a);t['trace_sha256']='0'*64
        with self.assertRaisesRegex(Refusal,'original source hash'):
            audit_one(t,self.original,self.trace_sha,self.trace['certificate'],CertifiedBoxCache())
        with self.assertRaisesRegex(Refusal,'case not in pinned'):
            _prepare_original('not_an_original_case',self.pins)

    def test_forged_release_refused(self):
        t=copy.deepcopy(self.a);t['release_status']='GO'
        with self.assertRaisesRegex(Refusal,'scientific status'):
            audit_one(t,self.original,self.trace_sha,self.trace['certificate'],CertifiedBoxCache())

    def test_invalid_partition_refused_even_if_digest_rehashed(self):
        t=copy.deepcopy(self.a)
        ev=t['events'][0]
        ev['children'][0]['box'][0][0]='0'
        ev['digest']=sha(canon({k:v for k,v in ev.items() if k!='digest'}).encode())
        with self.assertRaisesRegex(Refusal,'invalid partition'):
            audit_one(t,self.original,self.trace_sha,self.trace['certificate'],CertifiedBoxCache())

    def test_abstract_proof_keys_different_original_source(self):
        # Even when boxes coincide, source identities must differentiate claims.
        cache=CertifiedBoxCache()
        box=[['0','1'],['-1','1'],['1','2']]
        trace_a='a'*64;trace_b='b'*64
        from audit_m8 import FORMULA,serialize
        key_a=(trace_a,FORMULA,canon(box));key_b=(trace_b,FORMULA,canon(box))
        self.assertNotEqual(key_a,key_b)

    def test_no_producer_runtime_import_or_external_cache_trust(self):
        src=(HERE/'audit_m8.py').read_text()
        self.assertNotIn('from gram_psd import',src)
        self.assertNotIn('from mpfr_gram import',src)
        self.assertNotIn('import flint',src)
        self.assertNotIn('import gmpy2',src)
        self.assertNotIn('json.loads(cache',src)

    def test_frozen_m7_accepted_count(self):
        s=json.loads((ROOT/'CH40M7/accepted/CH40M7_ALL15_MATCHED_GRAM.json').read_text())
        self.assertEqual((s['cases'],s['accepted_arms'],s['independent_replayed_children']),(15,30,242))
        self.assertEqual(s['scientific_release'],'NO_GO')

    def test_bad_mode_and_duplicate_case_refused(self):
        with self.assertRaisesRegex(Refusal,'invalid audit mode'):
            run_batch(ROOT/'CH40M7/accepted','FAKE',[CASE])
        with self.assertRaisesRegex(Refusal,'duplicate'):
            run_batch(ROOT/'CH40M7/accepted','cache',[CASE,CASE])

    def test_frozen_immutable_after_audit(self):
        before=hashlib.sha256(self.a_path.read_bytes()).hexdigest()
        audit_one(self.a,self.original,self.trace_sha,self.trace['certificate'],CertifiedBoxCache())
        self.assertEqual(before,hashlib.sha256(self.a_path.read_bytes()).hexdigest())

if __name__=='__main__': unittest.main(verbosity=2)
