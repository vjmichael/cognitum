"""CH40-B full original-data independent coupled/Taylor/Krawczyk benchmark.

No Cognitum runtime imports. Every original source/pin comes from external-hash
CH39 ZIP. Independent Decimal arithmetic is deliberately conservative.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,pathlib,sys,time,zipfile
from fractions import Fraction as F
from independent_checker40 import MathematicalModel,exact_partition
from exact_decimal40 import op,ROUND_CEILING
from decimal import Decimal as D
from independent_bounds40b import dual_coupled_upper,taylor_upper
from independent_newton40b import krawczyk
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256

HERE=pathlib.Path(__file__).resolve().parent

def finite_fraction(t):
    f=F(t);u=f.denominator;twos=fives=0
    while u%2==0:u//=2;twos+=1
    while u%5==0:u//=5;fives+=1
    if u!=1:raise ValueError('Not a terminating exact interval boundary')
    k=max(twos,fives);n=abs(f.numerator)*(5**(k-fives))*(2**(k-twos))
    s=str(n).zfill(k+1)
    return ('-' if f<0 else '')+(s if not k else s[:-k]+'.'+s[-k:])

def one_case(args):
    path,case,pins=args
    t=time.monotonic()
    with zipfile.ZipFile(path) as z:cert=decode_case(z,case,pins)
    leaves=exact_partition(cert);model=MathematicalModel(cert['model'])
    lb=model.incumbent_lower(cert['incumbent'])
    wins=0;better=[];caps=[]
    for idx,domain in leaves:
        box=[(finite_fraction(a),finite_fraction(b)) for a,b in domain]
        direct=model.objective_bound(box)
        coupled=dual_coupled_upper(model,box,cert['dual_matrices'])['upper']
        if coupled<direct:wins+=1
        upper=min(direct,coupled)
        local_center=[finite_fraction((a+b)/2) for a,b in domain]
        local_lower=model.incumbent_lower(local_center)
        if upper<local_lower:raise ArithmeticError('Independent leaf upper excludes feasible point in same leaf')
        caps.append(upper)
    bounded_gap_proven=(max(caps)<=op('add',lb,D(str(cert['tolerance'])),ROUND_CEILING))
    # A small interior original-data box around the frozen incumbent exercises
    # Taylor and interval Newton without treating its contraction as part of
    # the 127-node producer proof (which contained zero Newton events).
    center=[F(str(v)) for v in cert['incumbent']]
    tiny=[]
    for x,(a,b) in zip(center,cert['root_box']):
        step=min(F(1,1000),(x-F(str(a)))/4,(F(str(b))-x)/4)
        if step<=0:raise ValueError('Original incumbent on boundary: no Newton claim')
        tiny.append((finite_fraction(x-step),finite_fraction(x+step)))
    taylor=taylor_upper(model,tiny)
    midpoint=model.objective_bound([(finite_fraction(x),finite_fraction(x)) for x in center])
    if taylor<midpoint:raise ArithmeticError('Taylor cap excludes source midpoint')
    K=krawczyk(model,tiny,cert['root_box'],[['-0.01' if i==j else '0' for j in range(model.d)] for i in range(model.d)])
    return {'case':case,'status':('REVIEW_REQUIRED_POTENTIAL_FINITE_GAP' if bounded_gap_proven else 'PASS_INDEPENDENT_FINITE_BOX_UNRESOLVED'),
            'original_nodes':len(cert['nodes']),'leaves':len(leaves),'dual_coupled_improved_leaves':wins,
            'conservative_best_upper':str(max(caps)),'incumbent_lower':str(lb),
            'bounded_gap_proven':bounded_gap_proven, # compute, never silently promote scientific claim
            'taylor_near_incumbent_upper':str(taylor),'taylor_midpoint_upper':str(midpoint),
            'krawczyk_status':K['status'],'no_producer_newton_actions':cert['newton_exclusions']==0 and cert['newton_contractions']==0,
            'scoped_frozen_127_node_certificate':True,
            'scientific_release':'NO_GO','seconds':round(time.monotonic()-t,3)}

def run(archive,out,workers=4,cases=None):
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:raise ValueError('Original archive digest mismatch')
    with zipfile.ZipFile(archive) as z:pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
    targets=cases or sorted(pins)
    if any(x not in pins for x in targets):raise ValueError('Unknown frozen case')
    results={}
    tasks=[(str(archive),x,pins) for x in targets]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(one_case,x):x[1] for x in tasks}
        for fut in concurrent.futures.as_completed(futures):
            case=futures[fut]
            try:r=fut.result()
            except Exception as e:
                r={'case':case,'status':'FAIL','reason':str(e),'type':type(e).__name__}
            results[case]=r
            print(r['status'],case,('coupled_wins='+str(r.get('dual_coupled_improved_leaves','?'))),flush=True)
            if out:
                out.parent.mkdir(parents=True,exist_ok=True)
                saved={'version':'CH40-B','source_zip_sha256':ORIGINAL_ZIP_SHA256,'cases':results,
                      'counts':{'PASS':sum(v['status'].startswith('PASS') for v in results.values()),'FAIL':sum(v['status']=='FAIL' for v in results.values())},
                      'scientific_release':'NO_GO','mathematical_scope':'Finite-box independent coupling, Taylor near incumbent, no producer-Newton event'}
                temp=out.with_suffix(out.suffix+'.tmp')
                temp.write_text(json.dumps(saved,indent=2)+'\n',encoding='utf8');os.replace(temp,out)
    return not any(r['status']=='FAIL' for r in results.values()) and len(results)==len(targets)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--archive',type=pathlib.Path,default=HERE/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip');a.add_argument('--out',type=pathlib.Path,default=HERE/'CH40B_original15_results.json');a.add_argument('--jobs',type=int,default=4);a.add_argument('--case',action='append',default=None)
    q=a.parse_args();sys.exit(0 if run(q.archive,q.out,max(1,min(4,q.jobs)),q.case) else 1)
