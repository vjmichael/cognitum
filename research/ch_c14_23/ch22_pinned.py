"""Prospectively frozen CH22 numerical ambiguity study; research-only."""
import json,hashlib,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.optimize._numdiff import approx_derivative
D=Path(__file__).resolve().parent
P=json.loads((D/'frozen_protocol.json').read_text())

def generator(fam,n,seed):
    rng=np.random.default_rng(seed)
    x1=rng.normal(size=n)
    x2=rng.normal(size=n)
    if fam=='zero_imbalanced':
        x1=np.where(rng.random(n)<.08,rng.normal(3,.6,n),rng.normal(-.3,.25,n));x2=.8*x1+rng.normal(0,.35,n)
    if fam=='quasi_separated':
        x1=rng.normal(size=n); x2=rng.normal(size=n)
    X=np.column_stack([np.ones(n),x1,x2]);
    if fam.startswith('zero'):y=np.zeros(n)
    elif fam=='one_event':y=np.zeros(n);y[rng.integers(n)]=1
    elif fam=='rare_1pct':y=rng.binomial(1,expit(-4.9+.6*x1-.25*x2))
    elif fam=='rare_5pct':y=rng.binomial(1,expit(-3.2+.6*x1-.25*x2))
    elif fam=='quasi_separated':y=(x1+.3*x2>1.4).astype(float)
    else:raise ValueError(fam)
    return X,y

def val_score(beta,X,y):
    eta=X@beta;p=expit(eta);w=p*(1-p)
    I=X.T@(w[:,None]*X)
    s,l=np.linalg.slogdet(I)
    if s<=0 or not np.isfinite(l):return -np.inf,np.full(len(beta),np.nan)
    h=w*np.sum(X*np.linalg.solve(I,X.T).T,axis=1)
    return float(y@eta-np.logaddexp(0,eta).sum()+.5*l), X.T@(y-p+(.5-p)*h)

def evaluate_one(fam,n,index):
    ss=int(P['seed_namespace']+n*100000+P['families'].index(fam)*10000+index)
    X,y=generator(fam,n,ss)
    rng=np.random.default_rng(ss+998877)
    a=(float(y.sum())+.5)/(n+1)
    base=np.array([np.log(a/(1-a)),0,0])
    starts=[base]
    for _ in range(7):starts.append(base+rng.normal([0,0,0],[2,1.5,1.5]))
    results=[]
    for i,start in enumerate(starts):
        for method in P['methods']:
            try:
                opt=minimize(lambda b:-val_score(b,X,y)[0],start,jac=lambda b:-val_score(b,X,y)[1],method=method,options={'maxiter':P['maxiter'],'gtol':1e-7})
                b=np.asarray(opt.x,dtype=float)
                obj,s=val_score(b,X,y);smax=float(np.max(np.abs(s)))
                if np.isfinite(smax) and smax<P['score_inf_threshold']:
                    H=approx_derivative(lambda v:val_score(v,X,y)[1],b,method='3-point',abs_step=2e-4)
                    e=float(np.linalg.eigvalsh((H+H.T)/2).max())
                else:e=None
                valid=bool(np.isfinite(obj) and np.isfinite(smax) and smax<P['score_inf_threshold'] and e is not None and e<P['max_hessian_eigenvalue_threshold'])
                results.append({'start':i,'method':method,'beta':b.tolist(),'objective':obj if np.isfinite(obj) else None,'score_inf':smax if np.isfinite(smax) else None,'max_hessian_eig':e,'optimizer_success':bool(opt.success),'validated_local_max':valid})
            except (ValueError,np.linalg.LinAlgError,FloatingPointError) as exc:
                results.append({'start':i,'method':method,'exception':type(exc).__name__,'validated_local_max':False})
    clusters=[]
    for rec in results:
        if not rec['validated_local_max']:continue
        b=np.array(rec['beta']); obj=rec['objective']
        match=next((z for z in clusters if np.max(np.abs(b-np.array(z['beta']))) <P['distinct_beta_supnorm_threshold'] and abs(obj-z['objective'])<P['distinct_objective_threshold']),None)
        if match:match['count']+=1
        else:clusters.append({'beta':b.tolist(),'objective':obj,'count':1})
    clusters.sort(key=lambda z:-z['objective'])
    ambiguous=len(clusters)>1
    return {'family':fam,'n':n,'index':index,'seed':ss,'events':int(y.sum()),'data_digest':hashlib.sha256(X.tobytes()+y.tobytes()).hexdigest(),'attempts':len(results),'valid_attempts':sum(r['validated_local_max'] for r in results),'distinct_valid_local_maxima':len(clusters),'clusters':clusters,'ambiguous':ambiguous,'decision':'REFUSED_ambiguous_local_maxima' if ambiguous else 'REFUSED_no_valid_maximum' if not clusters else 'RESEARCH_only_single_observed_maximum_global_unproven','production_accepted':False,'causal_certification':False,'optimizations':results}

def main():
    outfile=D/'results.jsonl'; count=0
    with outfile.open('w') as f:
        for fam in P['families']:
            for n in P['n_values']:
                for idx in range(P['seeds_per_cell']):
                    rec=evaluate_one(fam,n,idx)
                    f.write(json.dumps(rec,allow_nan=False)+'\n');f.flush();count+=1
                    if count%16==0:print('completed',count,flush=True)
    print('finished',count)
if __name__=='__main__':main()
