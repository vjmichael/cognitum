import copy
import math
import unittest
from mpmath import mp
from mpfr_interval import Interval as I, MP
from verified_bnb import FirthObjective, bound_node, logistic_model, midpoint_bounds, solve
from verify_certificate import verify


def rows_intercept(n, successes):
    return [{'x':['1'], 'y':int(i<successes)} for i in range(n)]


def rows_two(n=12):
    return [{'x':['1',str((i%3)-1)], 'y':int(i%5==0)} for i in range(n)]


class TestVerifiedBnB(unittest.TestCase):
    def test_mpfr_enclosures(self):
        x=I('0.1','0.2')
        for z in ['0.1','0.15','0.2']:
            with mp.workdps(90):
                ref=mp.log(mp.mpf(z))
                lo=mp.mpf(str(x.log().lower_float()))
                hi=mp.mpf(str(x.log().upper_float()))
                self.assertLessEqual(lo,ref)
                self.assertGreaterEqual(hi,ref)
        v=I('-2','3')*I('-4','5')
        self.assertEqual(v.lower_float(),-12)
        self.assertEqual(v.upper_float(),15)

    def test_point_objective_independent_high_precision(self):
        rows=rows_two()
        d=logistic_model(rows)
        model=FirthObjective(d)
        for b0,b1 in [('-3','-.2'), ('-1','1'), ('0.3','-0.7')]:
            v,_=model.objective([I(b0),I(b1)])
            with mp.workdps(90):
                info=mp.matrix(2,2)
                ll=mp.mpf(0)
                for row in rows:
                    x=[mp.mpf(i) for i in row['x']]
                    eta=x[0]*mp.mpf(b0)+x[1]*mp.mpf(b1)
                    p=1/(1+mp.exp(-eta));w=p*(1-p)
                    ll+=row['y']*eta-mp.log(1+mp.exp(eta))
                    for i in range(2):
                        for j in range(2): info[i,j]+=w*x[i]*x[j]
                expected=ll+mp.log(mp.det(info))/2
                self.assertLessEqual(mp.mpf(v.lower_float())-mp.mpf('1e-14'),expected)
                self.assertGreaterEqual(mp.mpf(v.upper_float())+mp.mpf('1e-14'),expected)

    def test_gradient_hessian_numeric(self):
        d=logistic_model(rows_two())
        m=FirthObjective(d)
        at=['-1','0.3']
        jet=m.jet([I(x) for x in at])
        with mp.workdps(70):
            def fun(a,b):
                rows=rows_two()
                info=mp.matrix(2);ll=mp.mpf('0')
                for row in rows:
                    x0=mp.mpf(row['x'][0]); x1=mp.mpf(row['x'][1]);eta=a*x0+b*x1
                    p=1/(1+mp.exp(-eta));w=p*(1-p)
                    ll+=row['y']*eta-mp.log(1+mp.exp(eta))
                    for i,x in enumerate([x0,x1]):
                        for j,y in enumerate([x0,x1]):info[i,j]+=w*x*y
                return ll+mp.log(mp.det(info))/2
            vals=[mp.mpf(v) for v in at]
            for i in range(2):
                derivative=mp.diff(lambda t:fun(*(vals[:i]+[t]+vals[i+1:])),vals[i])
                self.assertAlmostEqual(jet.g[i].mid_approx(),float(derivative),places=9)
            for i in range(2):
                for j in range(2):
                    derivative_orders = tuple((2 if k==i else 0) if i==j else (1 if k in (i,j) else 0)
                                              for k in range(2))
                    h=mp.diff(fun,tuple(vals),derivative_orders)
                    self.assertAlmostEqual(jet.h[i][j].mid_approx(),float(h),places=8)
                    self.assertLess(jet.h[i][j].upper_float()-jet.h[i][j].lower_float(),1e-12)

    def test_one_coefficient_certification_and_replay(self):
        cert=solve(rows_intercept(21,3), [['-5','1']],tol='0.001',max_nodes=150)
        self.assertEqual(cert['status'],'CERTIFIED_BOUNDED_GAP')
        replay=verify(cert)
        self.assertEqual(replay['result'],'VERIFIED_BOUNDED_GAP')
        self.assertGreater(cert['split_count'],0)
        self.assertIn('interval_hessian_taylor',cert['leaf_methods'])
        self.assertFalse(replay['claim_is_global_on_Rd'])

    def test_all_zero_bounded_box(self):
        cert=solve(rows_intercept(18,0), [['-6','1']],tol='0.002',max_nodes=200)
        self.assertEqual(cert['status'],'CERTIFIED_BOUNDED_GAP')
        self.assertEqual(verify(cert)['result'],'VERIFIED_BOUNDED_GAP')

    def test_tight_budget_fails_closed(self):
        cert=solve(rows_intercept(21,3), [['-5','1']],tol='0.00000001',max_nodes=1)
        self.assertEqual(cert['status'],'UNRESOLVED_REFUSE_CERTIFICATION')
        self.assertEqual(verify(cert)['result'],'REPLAYED_BUT_UNRESOLVED')
        cert['status']='CERTIFIED_BOUNDED_GAP'
        with self.assertRaises(ValueError):verify(cert)

    def test_2d_small_compact_box(self):
        cert=solve(rows_two(),[['-2.1','-1.5'],['-.4','.4']],tol='0.025',max_nodes=180)
        self.assertEqual(cert['status'],'CERTIFIED_BOUNDED_GAP')
        self.assertEqual(verify(cert)['result'],'VERIFIED_BOUNDED_GAP')

    def test_tamper_tree_rejected(self):
        cert=solve(rows_intercept(21,3), [['-5','1']],tol='0.001',max_nodes=150)
        altered=copy.deepcopy(cert)
        altered['nodes'][1]['box'][0][0]='-999'
        with self.assertRaises(ValueError):verify(altered)
        altered=copy.deepcopy(cert)
        altered['model']['rows'][0]['s']=42
        with self.assertRaises(ValueError):verify(altered)
        altered=copy.deepcopy(cert)
        altered['incumbent'][0]='999'
        with self.assertRaises(ValueError):verify(altered)

    def test_three_coefficient_directed_curvature_replay(self):
        rows=[{'x':['1',str(i%3-1),str((i//3)%3-1)],'y':0} for i in range(27)]
        box=[['-4.04','-3.96'],['-0.02','0.02'],['-0.02','0.02']]
        cert=solve(rows,box,tol='0.07',max_nodes=1)
        self.assertEqual(cert['status'],'CERTIFIED_BOUNDED_GAP')
        self.assertEqual(cert['leaf_methods'],{'interval_hessian_taylor':1})
        self.assertEqual(verify(cert)['result'],'VERIFIED_BOUNDED_GAP')
        # Same numerical domain at a stricter precision goal must refuse.
        refused=solve(rows,box,tol='0.000001',max_nodes=1)
        self.assertEqual(refused['status'],'UNRESOLVED_REFUSE_CERTIFICATION')

    def test_hessian_box_contains_independent_derivatives(self):
        rows=rows_two(12)
        model=FirthObjective(logistic_model(rows))
        region=model.jet([I('-1.1','-0.9'),I('.2','.4')])
        with mp.workdps(70):
            def f(a,b):
                ll=mp.mpf(0); info=mp.matrix(2)
                for row in rows:
                    x0=mp.mpf(row['x'][0]);x1=mp.mpf(row['x'][1])
                    eta=a*x0+b*x1
                    prob=1/(1+mp.exp(-eta)); w=prob*(1-prob)
                    ll+=row['y']*eta-mp.log(1+mp.exp(eta))
                    for i,x in enumerate([x0,x1]):
                        for j,z in enumerate([x0,x1]): info[i,j]+=w*x*z
                return ll+mp.log(mp.det(info))/2
            for a,b in [('-1','.3'),('-1.05','.22'),('-.94','.37')]:
                for i in range(2):
                    for j in range(2):
                        orders=tuple((2 if k==i else 0) if i==j
                                     else (1 if k==i or k==j else 0) for k in range(2))
                        actual=mp.diff(f,(mp.mpf(a),mp.mpf(b)),orders)
                        self.assertLessEqual(region.h[i][j].lower_float()-1e-10,float(actual))
                        self.assertGreaterEqual(region.h[i][j].upper_float()+1e-10,float(actual))

    def test_invalid_inputs_refuse(self):
        for rows in ([{'x':['1','2'],'y':1}],[{'x':[0.1],'y':0}], [{'x':['1'],'y':2}]):
            with self.assertRaises((ValueError,TypeError)):
                solve(rows,[['-1','1']],max_nodes=1)
        with self.assertRaises(ValueError):
            solve(rows_intercept(5,0),[['2','1']])
        with self.assertRaises(ValueError):
            solve(rows_intercept(5,0),[['-1','1']],seeds=[['500']])

if __name__=='__main__':unittest.main()
