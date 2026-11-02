"""Independent formula-level audit: no imports from candidate run or bounded_global."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.special import expit
from scipy.optimize._numdiff import approx_derivative
D=Path(__file__).resolve().parent
P=json.loads((D/'frozen_protocol.json').read_text())

def independent_generator(fam,n,seed):
    r=np.random.default_rng(seed); a=r.normal(size=n);b=r.normal(size=n)
    if fam=='zero_imbalanced':
        a=np.where(r.random(n)<.08,r.normal(3,.6,n),r.normal(-.3,.25,n));b=.8*a+r.normal(0,.35,n)
    if fam=='quasi_separated':a=r.normal(size=n);b=r.normal(size=n)
    x=np.stack([np.ones(n),a,b],axis=1)
    if fam.startswith('zero'):y=np.zeros(n)
    elif fam=='one_event':y=np.zeros(n);y[r.integers(n)]=1
    elif fam=='rare_1pct':y=r.binomial(1,expit(-4.9+.6*a-.25*b))
    elif fam=='rare_5pct':y=r.binomial(1,expit(-3.2+.6*a-.25*b))
    elif fam=='quasi_separated':y=(a+.3*b>1.4).astype(float)
    else:raise ValueError(fam)
    return x,y

def independent_objective(b,x,y):
    eta=x@b;p=expit(eta);w=p*(1-p)
    info=(x*np.sqrt(w)[:,None]).T@(x*np.sqrt(w)[:,None]);sign,logdet=np.linalg.slogdet(info)
    if sign<=0:return -np.inf
    return float(np.dot(y,eta)-np.logaddexp(0,eta).sum()+.5*logdet)

def audit():
    recs=[json.loads(s) for s in (D/'results.jsonl').read_text().splitlines()]
    assert len(recs)==len(P['families'])*len(P['n_values'])*P['seeds_per_cell']
    seen=set();attempts=valid=ambiguous=roots=0;maxobj=maxgrad=0
    for row in recs:
        key=(row['family'],row['n'],row['index']);assert key not in seen;seen.add(key)
        assert row['seed']==P['seed_namespace']+row['n']*100000+P['families'].index(row['family'])*10000+row['index']
        x,y=independent_generator(*key[:2],row['seed']);assert hashlib.sha256(x.tobytes()+y.tobytes()).hexdigest()==row['data_digest']
        assert row['events']==int(y.sum())
        assert row['attempts']==2*P['starts_per_dataset']==len(row['optimizations'])
        assert row['valid_attempts']==sum(v['validated_local_max'] for v in row['optimizations'])
        assert row['ambiguous']==(len(row['clusters'])>1)
        assert not row['causal_certification'] and not row['production_accepted']
        attempts+=row['attempts'];valid+=row['valid_attempts'];ambiguous+=row['ambiguous']
        for cl in row['clusters']:
            b=np.array(cl['beta']);v=independent_objective(b,x,y)
            diff=abs(v-cl['objective']);assert diff<1e-8;maxobj=max(maxobj,diff)
            g=approx_derivative(lambda a:independent_objective(a,x,y),b,method='3-point',abs_step=1e-5)
            gm=float(np.max(np.abs(g)));assert gm<2e-4;maxgrad=max(maxgrad,gm);roots+=1
    bounds=json.loads((D/'bounded_results.json').read_text());assert len(bounds)==12
    numerical_bound_checks=0; min_slack=float('inf')
    for b in bounds:
        x,y=independent_generator(b['family'],b['n'],b['seed'])
        box=np.array(P['additional_bounded_certification']['box'])
        # Independent upper-bound derivation: monotone Bernoulli log-likelihood + Loewner-upper Fisher information.
        lo=x@box.mean(axis=1)-np.abs(x)@((box[:,1]-box[:,0])/2)
        hi=x@box.mean(axis=1)+np.abs(x)@((box[:,1]-box[:,0])/2)
        eta_best=np.where(y>0,hi,lo)
        ll=float((y*eta_best-np.logaddexp(0,eta_best)).sum())
        t=np.where(lo>0,lo,np.where(hi<0,hi,0))
        w=1/(2+np.exp(t)+np.exp(-t))
        sign,l=np.linalg.slogdet(x.T@(w[:,None]*x));assert sign>0
        upper=ll+.5*l
        assert abs(upper-b['initial_upper_bound'])<1e-8
        r=np.random.default_rng(b['seed']+811)
        for j in range(60):
            pt=r.uniform(box[:,0],box[:,1]);v=independent_objective(pt,x,y)
            slack=upper-v; assert slack>=-1e-8
            min_slack=min(min_slack,slack);numerical_bound_checks+=1
        assert b['upper_minus_incumbent']>=0 and not b['machine_certified']
    result={'audit':'PASS','dataset_count':len(recs),'attempts':attempts,'validated_local_attempts':valid,'ambiguous_datasets':ambiguous,'independently_recomputed_local_maxima':roots,'max_abs_objective_error':maxobj,'max_independent_fd_gradient':maxgrad,'compact_box_bound_cases':len(bounds),'random_points_checked_under_bound':numerical_bound_checks,'min_random_sample_upper_bound_slack':min_slack,'certified_global_optima':0,'machine_proof':False}
    (D/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':print(json.dumps(audit(),indent=2))
