"""Conservative native Arb objective enclosure over frozen root/leaf boxes.
No claim of superior bound unless an independently validated finite Arb enclosure exists.
"""
from pathlib import Path
import sys,time,json
from fractions import Fraction as F
sys.path[:0]=['/mnt/data/CH40M3/site','/mnt/data/CH40M2/source']
from frozen40m2 import load_cases
from flint import arb,arb_mat,ctx
from flint_arb_backend import dyadic, fraction_arb

def arb_box(lo,hi):
    lo,hi=F(lo),F(hi)
    assert lo<=hi
    return fraction_arb(lo,arb).union(fraction_arb(hi,arb))

def arb_upper_region(case,box,precision=256):
    old=ctx.prec
    try:
        ctx.prec=precision
        B=[arb_box(v[0],v[1]) for v in box]
        likelihood=arb(0)
        fisher=[[arb(0) for _ in range(3)] for __ in range(3)]
        for row in case.certificate['model']['rows']:
            x=[fraction_arb(F(v),arb) for v in row['x']]
            z=sum((a*b for a,b in zip(x,B)),arb(0));n,s=int(row['n']),int(row['s'])
            likelihood+=arb(s)*z-arb(n)*(arb(1)+z.exp()).log()
            p=arb(1)/(arb(1)+(-z).exp());w=arb(n)*p*(arb(1)-p)
            for i in range(3):
                for j in range(3):fisher[i][j]+=w*x[i]*x[j]
        D=arb_mat(fisher).det()
        if dyadic(D.lower())<=0:return {'status':'REFUSED_FISHER_INTERVAL_CROSSES_ZERO','det_upper':str(dyadic(D.upper()))}
        obj=likelihood+D.log()/2
        return {'status':'REGION_INTERVAL_ENCLOSED','upper':str(dyadic(obj.upper())), 'lower':str(dyadic(obj.lower()))}
    finally:ctx.prec=old

if __name__=='__main__':
    cases=load_cases(Path('/mnt/data/CH40K/traces'),Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))
    out=[]
    for c in cases:
        nodes=c.certificate['nodes'];leaves=[n for n in nodes if not n.get('children')]
        leaves=sorted(leaves,key=lambda n:n['upper_bound_ceil_display'],reverse=True)
        n=leaves[0]
        start=time.process_time()
        try:r=arb_upper_region(c,n['effective_box']);
        except Exception as ex:r={'status':'REFUSED_EXCEPTION','error':str(ex)[:200]}
        r['case']=c.name;r['leaf_id']=n['id'];r['frozen_leaf_cap_display']=n['upper_bound_ceil_display'];r['cpu_seconds']=round(time.process_time()-start,6)
        out.append(r);print(r['case'],r['status'],'upper',r.get('upper','--'),flush=True)
    Path('/mnt/data/CH40M3/results/flint15_terminal_region.json').write_text(json.dumps({'protocol':'CH40-M3-ARB-REGION-TRIAGE-V1','scientific_release':'NO_GO','cases':out},indent=2)+'\n')

