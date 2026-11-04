"""Native FLINT/Arb independently recomputable *region* bound for frozen CH23 terminal boxes.
Each upper is an interval upper via direct likelihood and Hadamard upper on Fisher logdet.
The independent rational checker is used as a conservative acceptance baseline;
NO global optimum claim or reuse of signed authority.
"""
from pathlib import Path
import json,sys,time,math,signal,hashlib
from fractions import Fraction as F
sys.path[:0]=['/mnt/data/CH40M3/site','/mnt/data/CH40M2/source','/mnt/data/CH40J/source']
from flint import arb,ctx
from flint_arb_backend import fraction_arb,dyadic
from frozen40m2 import load_cases
from rational_kernel40d import direct_upper

def R(x):return fraction_arb(F(x),arb)
def interval(lo,hi):return R(lo).union(R(hi))
def upper_weight(z):
    lo,hi=dyadic(z.lower()),dyadic(z.upper())
    if lo<=0<=hi:return F(1,4)
    def weight(t):
        a=R(t)
        val=arb(1)/(arb(2)+a.exp()+(-a).exp())
        return dyadic(val.upper())
    return min(F(1,4),max(weight(lo),weight(hi)))
def rank3(rows):
    from itertools import combinations
    xs=[[F(v) for v in row['x']] for row in rows]
    for a,b,c in combinations(xs,3):
      det=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
      if det:return True
    return False

def compute(cert,box):
    previous=ctx.prec;ctx.prec=256
    try:
      rows=cert['model']['rows'];assert cert['model']['d']==3
      if not rank3(rows):raise ArithmeticError('Rank deficient exact model')
      B=[interval(lo,hi) for lo,hi in box]
      ll_hi=F(0); diagonal=[F(0)]*3
      for row in rows:
        x=[R(v) for v in row['x']]
        z=sum((a*b for a,b in zip(x,B)),arb(0))
        n,s=int(row['n']),int(row['s'])
        if s==0:
          term=-arb(n)*(arb(1)+R(dyadic(z.lower())).exp()).log()
        elif s==n:
          term=-arb(n)*(arb(1)+(-R(dyadic(z.upper()))).exp()).log()
        else:
          term=arb(s)*z-arb(n)*(arb(1)+z.exp()).log()
        ll_hi+=dyadic(term.upper())
        wup=upper_weight(z)
        for i in range(3):diagonal[i]+=n*F(row['x'][i])**2*wup
      detup=diagonal[0]*diagonal[1]*diagonal[2]
      if detup<=0:raise ArithmeticError('Unusable Fisher determinant upper')
      detlogup=dyadic(R(detup).log().upper())
      upper=ll_hi+F(1,2)*detlogup
      return upper
    finally:ctx.prec=previous

def timedout(*_):raise TimeoutError('Independent rational comparison timed out')

if __name__=='__main__':
  cases=load_cases(Path('/mnt/data/CH40K/traces'),Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))
  result={'protocol':'CH40-M3-FLINT-HADAMARD-REGION-EXPERIMENT-V1','scientific_release':'NO_GO','claims':'One original highest-cap terminal box per dataset; no global optimum; no signed evidence changed','cases':[]}
  output=Path('/mnt/data/CH40M3/results/flint15_region_hadamard.json')
  signal.signal(signal.SIGALRM,timedout)
  for i,c in enumerate(cases):
    leaf=max((n for n in c.certificate['nodes'] if not n.get('children')),key=lambda n:n['upper_bound_ceil_display'])
    r={'case':c.name,'source_sha256':c.source_sha256,'leaf_id':leaf['id'],'frozen_leaf_upper_display':leaf['upper_bound_ceil_display']}
    t=time.process_time()
    try:
      a=compute(c.certificate,leaf['effective_box'])
      r['arb_upper']=str(a);r['arb_upper_approx']=float(a)
      signal.alarm(12)
      try:b=direct_upper(c.certificate,leaf['effective_box']).hi
      finally:signal.alarm(0)
      r['independent_direct_upper']=str(b)
      # Conservative agreement gate: accept only a bound not optimistically tighter than an independent rigorously computed reference upper.
      r['status']='REGION_BOUND_CONSERVATIVE_AGREEMENT' if a>=b else 'REJECTED_TIGHTER_THAN_REFERENCE_FOR_THIS_GATE'
      r['improves_frozen_leaf_cap']=float(a)<leaf['upper_bound_ceil_display']
    except Exception as e:r['status']='UNRESOLVED';r['error']=repr(e)[:220]
    r['cpu_seconds']=round(time.process_time()-t,4)
    result['cases'].append(r);output.write_text(json.dumps(result,indent=2)+'\n')
    print(i+1,c.name,r['status'],'candidate',round(r.get('arb_upper_approx',float('nan')),4),flush=True)
  result['conservative_agreement']=sum(r['status']=='REGION_BOUND_CONSERVATIVE_AGREEMENT' for r in result['cases'])
  result['unresolved']=15-result['conservative_agreement']
  output.write_text(json.dumps(result,indent=2)+'\n')

