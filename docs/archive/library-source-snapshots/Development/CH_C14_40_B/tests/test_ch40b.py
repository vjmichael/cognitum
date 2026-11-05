"""Genuine independent CH40-B mathematical/adversarial regression on frozen CH23."""
from __future__ import annotations
import copy,json,pathlib,sys,unittest,zipfile
from decimal import Decimal as D
from fractions import Fraction as F
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256
from independent_checker40 import MathematicalModel,exact_partition,validate_duals
from independent_bounds40b import (dual_coupled_upper,objective_derivatives,taylor_upper)
from independent_newton40b import krawczyk,check_claim,interior
from batch40b import finite_fraction

ARCHIVE=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'

class CH40B(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ARCHIVE) as z:
            pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
            cls.cert=decode_case(z,'one_event_n80_i00',pins)
        cls.model=MathematicalModel(cls.cert['model'])
        cls.leaves=exact_partition(cls.cert)
        cls.inc=cls.cert['incumbent']
        cls.B=[(finite_fraction(F(str(x))-F(1,1000)),finite_fraction(F(str(x))+F(1,1000))) for x in cls.inc]
        cls.C=[['-0.01' if i==j else '0' for j in range(cls.model.d)] for i in range(cls.model.d)]
    def box(self,i):return [(finite_fraction(a),finite_fraction(b)) for a,b in self.leaves[i][1]]
    def test_01_exact_spd(self):
        self.assertGreater(validate_duals(self.cert),0)
    def test_02_coupled_recomputed_from_source(self):
        out=dual_coupled_upper(self.model,self.box(0),self.cert['dual_matrices'])
        self.assertEqual(len(out['by_dual']),len(self.cert['dual_matrices']))
    def test_03_original_leaf_coupled_tightens_direct(self):
        B=self.box(0)
        self.assertLess(dual_coupled_upper(self.model,B,self.cert['dual_matrices'])['upper'],self.model.objective_bound(B))
    def test_04_cryptographically_pinned_original(self):
        from hashlib import sha256
        self.assertEqual(sha256(ARCHIVE.read_bytes()).hexdigest(),ORIGINAL_ZIP_SHA256)
    def test_05_leaf_upper_vs_local_feasible(self):
        for leaf in (0,5,20,63):
            box=self.box(leaf)
            upper=min(dual_coupled_upper(self.model,box,self.cert['dual_matrices'])['upper'],self.model.objective_bound(box))
            center=[finite_fraction((a+b)/2) for a,b in self.leaves[leaf][1]]
            self.assertGreaterEqual(upper,self.model.incumbent_lower(center))
    def test_06_refuse_non_spd_dual(self):
        Q=copy.deepcopy(self.cert['dual_matrices']);Q[0][0][0]='-100'
        with self.assertRaises(ValueError):dual_coupled_upper(self.model,self.box(0),Q)
    def test_07_refuse_non_symmetric_dual(self):
        Q=copy.deepcopy(self.cert['dual_matrices']);Q[0][0][1]='0'
        with self.assertRaises(ValueError):dual_coupled_upper(self.model,self.box(0),Q)
    def test_08_taylor_encloses_center(self):
        bound=taylor_upper(self.model,self.B)
        centerbound=self.model.objective_bound([(v,v) for v in self.inc])
        self.assertGreaterEqual(bound,centerbound)
    def test_09_taylor_tighter_than_direct_near_center(self):
        self.assertLess(taylor_upper(self.model,self.B),self.model.objective_bound(self.B))
    def test_10_fisher_score_hessian_finite(self):
        G,H=objective_derivatives(self.model,self.B)
        self.assertEqual(len(G),3);self.assertEqual(len(H),3)
        for v in G+[x for row in H for x in row]:
            self.assertTrue(v.lo.is_finite());self.assertTrue(v.hi.is_finite());self.assertLessEqual(v.lo,v.hi)
    def test_11_hessian_symmetric_overlap(self):
        _,H=objective_derivatives(self.model,self.B)
        for i in range(3):
            for j in range(3):
                self.assertLessEqual(max(H[i][j].lo,H[j][i].lo),min(H[i][j].hi,H[j][i].hi))
    def test_12_gradient_matches_high_precision_numeric(self):
        try:import mpmath as mp
        except ImportError:self.skipTest('Optional high-precision mpmath crosscheck is not installed')
        mp.mp.dps=70
        rows=self.cert['model']['rows']
        def true_objective(a,b,c):
            beta=(a,b,c);ll=mp.mpf('0');I=mp.matrix(3)
            for r in rows:
                xx=[mp.mpf(str(k)) for k in r['x']]
                z=sum(t*u for t,u in zip(xx,beta));p=1/(1+mp.exp(-z));w=p*(1-p);n=r['n'];s=r['s']
                ll+=s*z-n*mp.log(1+mp.exp(z))
                for i in range(3):
                    for j in range(3):I[i,j]+=n*w*xx[i]*xx[j]
            return ll+mp.log(mp.det(I))/2
        x=[mp.mpf(str(v)) for v in self.inc]
        G,H=objective_derivatives(self.model,[(v,v) for v in self.inc])
        h=mp.mpf('0.000001')
        for j in range(3):
            lo=x.copy();hi=x.copy();lo[j]-=h;hi[j]+=h
            fd=(true_objective(*hi)-true_objective(*lo))/(2*h)
            midpoint=(G[j].lo+G[j].hi)/2
            self.assertLess(abs(float(fd)-float(midpoint)),2e-7)
        # Independent central second difference for full Firth Hessian diagonal.
        f0=true_objective(*x)
        h=mp.mpf('0.0001')
        for j in range(3):
            left=x.copy();right=x.copy();left[j]-=h;right[j]+=h
            fdh=(true_objective(*right)-2*f0+true_objective(*left))/(h*h)
            hmid=(H[j][j].lo+H[j][j].hi)/2
            self.assertLess(abs(float(fdh)-float(hmid)),2e-5)
    def test_13_krawczyk_original_interior(self):
        self.assertTrue(interior(self.B,self.cert['root_box']))
        r=krawczyk(self.model,self.B,self.cert['root_box'],self.C)
        self.assertIn(r['status'],('CONTRACTED','NO_GAIN','NO_STATIONARY'))
    def test_14_krawczyk_claim_contains_independent_enclosure(self):
        r=krawczyk(self.model,self.B,self.cert['root_box'],self.C)
        if r['status']=='CONTRACTED':self.assertEqual(check_claim(self.model,self.B,self.cert['root_box'],self.C,{'status':'CONTRACTED','box':r['box']})['status'],'CONTRACTED')
        else:self.skipTest('No contraction on selected original dataset')
    def test_15_forged_over_narrowed_contraction_refused(self):
        r=krawczyk(self.model,self.B,self.cert['root_box'],self.C)
        if r['status']!='CONTRACTED':self.skipTest('No contraction on selected original dataset')
        forged=copy.deepcopy(r);forged['box'][0][0]=str(D(forged['box'][0][0])+D('0.000001'))
        with self.assertRaises(ValueError):check_claim(self.model,self.B,self.cert['root_box'],self.C,forged)
    def test_16_refuse_root_boundary_krawczyk(self):
        with self.assertRaises(ValueError):krawczyk(self.model,self.cert['root_box'],self.cert['root_box'],self.C)
    def test_17_refuse_wrong_preconditioner_shape(self):
        with self.assertRaises(ValueError):krawczyk(self.model,self.B,self.cert['root_box'],[['1']])
    def test_18_refuse_forged_exclusion(self):
        with self.assertRaises(ValueError):check_claim(self.model,self.B,self.cert['root_box'],self.C,{'status':'NO_STATIONARY','reason':'GRADIENT_SIGN'})
    def test_19_old_proof_no_newton_events(self):
        self.assertEqual(self.cert['newton_exclusions'],0)
        self.assertEqual(self.cert['newton_contractions'],0)
    def test_20_frozen_claim_remains_unresolved(self):
        self.assertEqual(self.cert['status'],'UNRESOLVED_REFUSE_CERTIFICATION')
        self.assertEqual(self.cert['production_release'],'NO_GO')

if __name__=='__main__':unittest.main(verbosity=2)