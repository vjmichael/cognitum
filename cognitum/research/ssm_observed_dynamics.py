"""Frozen real sensor trajectories: causal, bounded and deliberately non-authorizing.

This is empirical one-step system identification, NOT discovery of a physical law.
KAN is the existing trainable one-layer research network. HDC uses actual MAP
Spec and Cleanup, and the teacher-forced state transition is an SSM reference.
"""
import csv
from datetime import datetime, timedelta
from hashlib import sha256
from io import StringIO
import json
import math
import numpy as np
from scipy.linalg import lstsq as scipy_lstsq

EXPECTED_MANIFEST_SHA = '66697a34d7a6f221490dcbaf87f490634dc5a4faf7e6dde18acade1cb5b9eebe'
SOURCE = {
    'uci374': dict(sha='c917e564a9d9805c394bdc093058bd591ceebff22c03364cac611abb6c437d78',
                   archive='2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a',
                   columns=('date','T1','T2','T_out','RH_1','Appliances'),target='T1',forcing=('T_out','RH_1'),interval=600),
    'uci501': dict(sha='75b3ee40df3c81edf643d12b368e5d070b79a172e08af1a0ba9d6203e3eba70a',
                   archive='b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4',
                   columns=('year','month','day','hour','PM2.5','TEMP','PRES','WSPM'),target='TEMP',forcing=('PRES','WSPM'),interval=3600),
}

def require(ok,msg):
    if not ok: raise ValueError(msg)

def hashbytes(raw): return sha256(raw).hexdigest()

def ingest(name, raw, manifest_raw):
    """Require canonical pinned original-derived bytes; preserve missing-data count."""
    require(name in SOURCE and type(raw) is bytes and type(manifest_raw) is bytes,'source type')
    s=SOURCE[name]
    require(hashbytes(manifest_raw)==EXPECTED_MANIFEST_SHA and hashbytes(raw)==s['sha'],'source digest')
    manifest=json.loads(manifest_raw)
    require(manifest['license'].startswith('CC BY 4.0') and len(manifest['entries'])==2,'source rights metadata')
    row=next(a for a in manifest['entries'] if a['id']==name)
    require(row['archive_sha256']==s['archive'] and row['excerpt_sha256']==s['sha'] and row['excerpt_rows']==6144,'source/archive custody')
    require(tuple(row['columns'])==s['columns'],'source schema')
    records=list(csv.DictReader(StringIO(raw.decode('utf-8')),strict=True))
    require(len(records)==6144 and set(records[0])==set(s['columns']),'observations/columns')
    times=[];Y=[];X=[];missing=0
    for row in records:
        if name=='uci374': t=datetime.strptime(row['date'],'%Y-%m-%d %H:%M:%S')
        else: t=datetime(*(int(row[k]) for k in ('year','month','day','hour')))
        if times: require((t-times[-1]).total_seconds()==s['interval'],'nonuniform time index')
        times.append(t)
        missing+=sum(str(z).strip().upper() in ('NA','') for z in row.values())
        y=float(row[s['target']]); x=[float(row[k]) for k in s['forcing']]
        require(np.isfinite([y,*x]).all() and max(abs(y),*(abs(z) for z in x))<=1e6,'target/forcing nonfinite')
        Y.append(y);X.append(x)
    require(missing==next(a['missing_selected_cells'] for a in manifest['entries'] if a['id']==name),'missingness provenance')
    require(np.ptp(Y)>0 and np.ptp(X,axis=0).min()>0,'no observation variability')
    return dict(dataset=name,times=tuple(times),state=np.array(Y),forcing=np.array(X),
                missing_auxiliary=missing,sha256=s['sha'],archive_sha256=s['archive'],
                attribution=next(a['author'] for a in manifest['entries'] if a['id']==name),
                interval_seconds=s['interval'])

def split(s):
    """Fixed chronological 60/20/20; no cross-boundary transition or test peeking."""
    n=len(s['state']);require(n==6144,'split source')
    edges=(0,int(.60*n),int(.80*n),n)
    return tuple(np.arange(a,b-1,dtype=np.int64) for a,b in zip(edges,edges[1:]))

def design(s,train):
    y=s['state'];u=s['forcing'];p=np.column_stack((y,u));m=p[train].mean(0);sd=p[train].std(0)
    require((sd>1e-7).all(),'train features not identified')
    v=(p-m)/sd
    d=np.column_stack((v[:,1],v[:,2],v[:,0],np.ones(len(v))))
    delta=(y[1:]-y[:-1])/sd[0]
    return d,delta,m,sd

def learn_ssm(d,delta,train):
    """Stable-ish teacher-forced ARX state-space step, no causal interpretation."""
    x=d[train];y=delta[train];penalty=np.diag([.02,.02,.02,0.])
    coef=np.linalg.lstsq(np.vstack((x,penalty)),np.r_[y,np.zeros(4)],rcond=None)[0]
    independent=scipy_lstsq(np.vstack((x,penalty)),np.r_[y,np.zeros(4)])[0]
    require(np.max(abs(coef-independent))<1e-9 and np.isfinite(coef).all() and abs(1+coef[2])<=1.2,'independent SSM fit')
    return coef

def normalized(s,train):
    p=np.column_stack((s['state'],s['forcing']));low=p[train].min(0);high=p[train].max(0)
    require(np.min(high-low)>1e-5,'KAN domain')
    raw=(p-low)/(high-low)
    ok=np.all((raw>=0)&(raw<=1),axis=1)
    return raw,ok

def kan_fit(normalized_values,residual,train):
    from .kan_trainable import Layer,Network
    idx=train[np.linspace(0,len(train)-1,2048,dtype=int)]
    require(normalized_values.shape[1]==3 and np.all((normalized_values[idx]>=0)&(normalized_values[idx]<=1)),'KAN train domain')
    layer=Layer('chebyshev',3,np.tile([0.,1.],(3,1)),np.zeros((1,3,4)),np.ones((1,3)),np.zeros(1))
    model=Network((layer,)).fit_linear(normalized_values[idx],residual[idx,None],ridge=.05)
    snapshot,pin=model.research_snapshot()
    return model,pin

def batch_kan(model,x,mask):
    result=np.zeros(len(x));indices=np.flatnonzero(mask)
    for chunk in np.array_split(indices,max(1,int(np.ceil(len(indices)/1024)))):
        if len(chunk):result[chunk]=model.evaluate(x[chunk])[0][:,0]
    return result

def train_hdc(x,mask,train,residual):
    """Existing Spec(MAP) + Cleanup; retrieval is only a candidate."""
    from .hdc_algebra import Spec
    from .hdc_associative import Cleanup
    spec=Spec('MAP',256);rng=np.random.default_rng(3405)
    symbols=rng.choice([-1.,1.],size=(3,8,256)).astype(np.float32)
    prototype_labels=(x[train,1]>np.median(x[train,1])).astype(int)
    def encode(v):
        bins=np.minimum((np.clip(v,0,1)*8).astype(int),7)
        return spec.bundle(np.stack([symbols[j,bins[j]] for j in range(3)]))
    select=train[np.linspace(0,len(train)-1,1536,dtype=int)]
    codes=np.array([encode(x[i]) for i in select]);labels=(x[select,1]>np.median(x[train,1])).astype(int)
    require(labels.min()==0 and labels.max()==1,'HDC train groups')
    prototypes=np.array([codes[labels==k].mean(axis=0) for k in (0,1)],dtype=np.float32)
    bank=Cleanup(spec,prototypes)
    bias=np.array([np.mean(residual[train][prototype_labels==k]) for k in (0,1)])
    return (spec,bank,encode,bias,prototypes)

def hdc_predict(hdc,x,mask,indices):
    spec,bank,encode,bias,prototypes=hdc
    predicted=np.zeros(len(x));abstain=0;accepted=0
    for i in indices:
        if not mask[i]:abstain+=1;continue
        q=encode(x[i]);cand=bank.propose(q,minimum=.12,margin=.005)
        if cand is None:abstain+=1;continue
        # Independent integer cosine score and actual engine agreement.
        manual=np.array([spec.similarity(q,prototypes[k]) for k in (0,1)])
        require(int(np.argmax(manual))==cand.index,'HDC ranking parity')
        predicted[i]=bias[cand.index];accepted+=1
    return predicted,dict(accepted=accepted,abstained=abstain)

def one_step_reference(coef,p,sd,indices):
    """Check learned linear transition against the existing SSM recurrence."""
    from .ssm_learned import recurrence
    F=np.array([[1+coef[2]]]);G=np.array([[coef[0],coef[1],coef[3]]]);C=np.array([[1.]])
    for j in indices[:8]:
        v=np.array([[p[j,1],p[j,2],1.]])
        actual=recurrence(F,G,C,v,np.array([p[j,0]]))['outputs'][0,0]
        expected=p[j,0]+p[j]@np.array([coef[2],coef[0],coef[1]])+coef[3]
        require(abs(actual-expected)<1e-10,'SSM recurrence reference parity')

def eval_scores(actual,pred):
    return float(np.sqrt(np.mean((actual-pred)**2)))

def rank_radius(residual,alpha=.1):
    v=np.sort(np.abs(residual));n=len(v);k=int(np.ceil((n+1)*(1-alpha)))-1
    require(0<=k<n,'calibration sample count');return float(v[k])

def bootstrap(delta,block,seed=721):
    """Consecutive-block bootstrap, conditional on a single observed trajectory."""
    rng=np.random.default_rng(seed);N=len(delta);blocks=[delta[i:i+block] for i in range(0,N-block+1,block)]
    require(len(blocks)>=8,'bootstrap blocks');boots=[]
    for _ in range(200):
        ids=rng.integers(0,len(blocks),len(blocks));v=np.concatenate([blocks[j] for j in ids]);boots.append(np.mean(v))
    return [float(a) for a in np.quantile(boots,[.025,.975])]

def experiment(name,raw,manifest_raw,integrated=True):
    s=ingest(name,raw,manifest_raw);train,cal,test=split(s)
    D,delta,mean,sd=design(s,train);co=learn_ssm(D,delta,train)
    p=np.column_stack((s['state'],s['forcing']));px=(p-mean)/sd
    y=s['state'];truth=y[1:];ssm=y[:-1]+sd[0]*(D[:-1]@co)
    no_future=bool(np.all(np.isfinite(ssm)))
    one_step_reference(co,px,sd,train) if integrated else None
    x,domain=normalized(s,train);correction=np.zeros(len(y)-1);hdc_bias=np.zeros(len(y)-1);stats={'accepted':0,'abstained':len(test)};kan_pin=None
    if integrated:
        # Predicted next state uses only state and forcing at current index t.
        model,kan_pin=kan_fit(x,(truth-ssm)/sd[0],train)
        correction=batch_kan(model,x[:-1],domain[:-1])*sd[0]
        residual=np.zeros(len(y));residual[:-1]=(truth-ssm-correction)
        hdc=train_hdc(x,domain,train,residual)
        hdc_bias,stats=hdc_predict(hdc,x[:-1],domain[:-1],test)
    corrected=ssm+correction;full=corrected+hdc_bias
    cal_err=truth[cal]-full[cal];radius=rank_radius(cal_err)
    covered=np.abs(truth[test]-full[test])<=radius
    # Negative hypothesis is fixed wrong-sign derivative; test it rather than assume failure.
    wrong=y[:-1]-(ssm-y[:-1]);prior=y[:-1]
    err_p=np.abs(truth[test]-prior[test]);err_model=np.abs(truth[test]-full[test])
    metrics=dict(persistence_rmse=eval_scores(truth[test],prior[test]),
       ssm_rmse=eval_scores(truth[test],ssm[test]),kan_rmse=eval_scores(truth[test],corrected[test]),
       integrated_rmse=eval_scores(truth[test],full[test]),wrong_sign_rmse=eval_scores(truth[test],wrong[test]),
       coverage_90=float(np.mean(covered)),coverage_first_half=float(np.mean(covered[:len(covered)//2])),
       coverage_second_half=float(np.mean(covered[len(covered)//2:])),
       calibration_radius=radius,domain_ood_count=int(np.sum(~domain[test])),
       hdc_accepted=int(stats['accepted']),hdc_abstained=int(stats['abstained']),
       bootstrap_mae_gain_95=bootstrap(err_p-err_model,24 if name=='uci501' else 144))
    # Shift stress is a counterfactual metric, not a new real observed trajectory.
    metrics['counterfactual_shift_coverage_90']=float(np.mean(np.abs(truth[test]+3*radius-full[test])<=radius))
    if not integrated:
        metrics['kan_rmse']=None;metrics['integrated_rmse']=None
        metrics['hdc_accepted']=None;metrics['hdc_abstained']=None
    return dict(dataset=name,source_sha256=s['sha256'],source_archive_sha256=s['archive_sha256'],
      source_member_match_oracle=(name=='uci374'),train_size=len(train),cal_size=len(cal),test_size=len(test),
      observation_step_seconds=s['interval_seconds'],missing_selected_cells=s['missing_auxiliary'],
      kan_snapshot_sha256=kan_pin,integrated=integrated,
      model_kind=('teacher-forced-one-step-state-space-with-learned-KAN-residual-and-HDC-candidate' if integrated else 'teacher-forced-linear-SSM-only'),
      evidence_class='empirical-heldout-forecast',metrics=metrics,prequential=True,
      verified_physical_law=False,full_scientific_scope_complete=False,execution_authorized=False)
