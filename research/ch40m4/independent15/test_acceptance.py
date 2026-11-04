"""Integrity and claim-scope checks for CH40-M.4 research evidence (stdlib only)."""
from pathlib import Path
from fractions import Fraction
import copy,json,unittest
ROOT=Path(__file__).resolve().parent

def load(name):return json.loads((ROOT/name).read_text())

def validate(opt,aud):
    runs=opt.get('cases',{})
    cases=aud.get('cases',[])
    if len(runs)!=15 or len(cases)!=15:raise ValueError('exactly 15 original cases required')
    if len({c.get('case') for c in cases})!=15 or set(runs)!={c['case'] for c in cases}:raise ValueError('case ID mismatch')
    if aud.get('scientific_release')!='NO_GO':raise ValueError('cannot promote research evidence')
    for c in cases:
        name=c['case'];r=runs[name]
        if r['status']!='EXECUTED_UNVERIFIED' or r['exit']!=0 or r['terminal']!='TIME_LIMIT':raise ValueError('native run not original bounded acceptance')
        if r['model_sha256']!=c['model_sha256']:raise ValueError('model hash mismatch')
        if not (r['gap_reported']>0.05 and c['ibex_reported_gap']>0.05):raise ValueError('unexpected closed gap: require independent audit')
        if c['native_status']!='TIME_LIMIT' or c['independent_global_certificate'] is not False:raise ValueError('proof scope invalid')
        if c['point_status']!='INDEPENDENT_POINT_INTERVAL_OVERLAP' or c['arb_rational_point_overlap'] is not True:raise ValueError('point not independently overlapped')
        al,au=Fraction(c['arb_lower_exact']),Fraction(c['arb_upper_exact'])
        rl,ru=Fraction(c['rational_lower_exact']),Fraction(c['rational_upper_exact'])
        if max(al,rl)>min(au,ru):raise ValueError('disjoint independent point enclosures')
        oldl,oldu=map(Fraction,c['original_verified_firth_max_interval'])
        il,iu=map(Fraction,[str(v) for v in c['ibex_reported_min_interval']])
        if max(-iu,oldl)>min(-il,oldu):raise ValueError('native triage interval incompatible with frozen certificate')
        if max(al,rl)>oldl:raise ValueError('new stronger incumbent; requires independent promotion')
    return True

class Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.opt=load('IBEX15_SOPLEX_04S.json');cls.audit=load('IBEX15_INDEPENDENT_AUDIT.json')
    def test_fifteen_cases_accepted_as_research_only(self):self.assertTrue(validate(self.opt,self.audit))
    def test_nonzero_or_missing_native_case_rejected(self):
        x=copy.deepcopy(self.opt);next(iter(x['cases'].values()))['exit']=-11
        with self.assertRaises(ValueError):validate(x,self.audit)
    def test_fake_proof_promotion_rejected(self):
        x=copy.deepcopy(self.audit);x['scientific_release']='GO'
        with self.assertRaises(ValueError):validate(self.opt,x)
    def test_tampered_model_digest_rejected(self):
        x=copy.deepcopy(self.opt);next(iter(x['cases'].values()))['model_sha256']='00'*32
        with self.assertRaises(ValueError):validate(x,self.audit)
    def test_disjoint_point_enclosure_rejected(self):
        x=copy.deepcopy(self.audit);x['cases'][0]['arb_lower_exact']='10000';x['cases'][0]['arb_upper_exact']='10001'
        with self.assertRaises(ValueError):validate(self.opt,x)
    def test_case_omission_rejected(self):
        x=copy.deepcopy(self.audit);x['cases'].pop()
        with self.assertRaises(ValueError):validate(self.opt,x)
if __name__=='__main__':unittest.main()
