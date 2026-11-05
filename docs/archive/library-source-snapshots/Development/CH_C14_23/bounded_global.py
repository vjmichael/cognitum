"""Compact parameter-box objective upper bounds for Jeffreys logistic fits.
The inequalities hold in exact arithmetic; these float64 computations are
NOT verified interval arithmetic, thus not formal machine-checked certificates.
"""
import heapq,json,hashlib
from pathlib import Path
import numpy as np
from scipy.special import expit
from scipy.optimize import minimize
import run
D=Path(__file__).resolve().parent
P=json.loads((D/'frozen_protocol.json').read_text())


def objective_upper(box,X,y):
    box=np.asarray(box,dtype=float)
    mid=box.mean(axis=1); rad=(box[:,1]-box[:,0])/2
    eta=X@mid; delta=np.abs(X)@rad
    low=eta-delta; high=eta+delta
    # For y in {0,1}, each loglik contribution is monotone in eta.
    best_eta=np.where(y==1,high,low)
    ub_lik=float(np.sum(y*best_eta-np.logaddexp(0,best_eta)))
    closest=np.where(low>0,low,np.where(high<0,high,0.0))
    pp=expit(closest); w=pp*(1-pp)
    info=X.T@(w[:,None]*X)
    s,l=np.linalg.slogdet(info)
    if s<=0:return float('inf')
    return ub_lik + .5*float(l)

def branch(box,X,y,incumbent,limit):
    heap=[];serial=0;pruned=0; expanded=0
    upper=objective_upper(box,X,y)
    heapq.heappush(heap,(-upper,serial,np.array(box,dtype=float)))
    while heap and expanded<limit:
        minusub,_,cell=heapq.heappop(heap)
        if -minusub <= incumbent:
            pruned+=1;continue
        widths=cell[:,1]-cell[:,0]
        j=int(np.argmax(widths/np.array([11.,10.,10.])))
        half=(cell[j,0]+cell[j,1])/2
        for side in [0,1]:
            sub=cell.copy()
            sub[j,1 if side==0 else 0]=half
            ub=objective_upper(sub,X,y)
            if ub<=incumbent:pruned+=1
            else:
                serial+=1;heapq.heappush(heap,(-ub,serial,sub))
        expanded+=1
    gap=max(0,-heap[0][0]-incumbent) if heap else 0
    return {'initial_upper_bound':upper,'incumbent':incumbent,'nodes_expanded':expanded,'nodes_pruned':pruned,'frontier_nodes':len(heap),'remaining_upper_bound': -heap[0][0] if heap else incumbent,'upper_minus_incumbent':gap,'compact_box_optimality_proven':bool(not heap),'machine_certified':False}

def case(fam,n):
    i=0;seed=int(P['seed_namespace']+n*100000+P['families'].index(fam)*10000+i)
    X,y=run.generator(fam,n,seed)
    rng=np.random.default_rng(seed+998877)
    base=np.array([np.log((y.sum()+.5)/(n-y.sum()+.5)),0,0])
    starts=[base]+[base+rng.normal(0,[2,1.5,1.5]) for _ in range(5)]
    candidates=[]
    for x in starts:
        opt=minimize(lambda b:-run.val_score(b,X,y)[0],x,jac=lambda b:-run.val_score(b,X,y)[1],method='L-BFGS-B',bounds=[(-10,1),(-5,5),(-5,5)],options={'maxiter':600})
        b=opt.x; v,s=run.val_score(b,X,y)
        if np.isfinite(v) and np.max(np.abs(s))<1e-3:candidates.append(v)
    if not candidates:
        # Endpoint baseline is still feasible by clipping.
        candidates=[run.val_score(np.clip(base,[-10,-5,-5],[1,5,5]),X,y)[0]]
    best=max(candidates)
    ans=branch(P['additional_bounded_certification']['box'],X,y,best,P['additional_bounded_certification']['max_branch_nodes'])
    ans.update({'family':fam,'n':n,'seed':seed,'events':int(y.sum()),'data_digest':hashlib.sha256(X.tobytes()+y.tobytes()).hexdigest()})
    return ans

if __name__=='__main__':
    records=[case(fam,n) for fam in P['families'] for n in P['n_values']]
    (D/'bounded_results.json').write_text(json.dumps(records,indent=2,allow_nan=False)+'\n')
    print('bounded cases',len(records),'min/max gap',min(x['upper_minus_incumbent'] for x in records),max(x['upper_minus_incumbent'] for x in records),'certified',sum(x['compact_box_optimality_proven'] for x in records))