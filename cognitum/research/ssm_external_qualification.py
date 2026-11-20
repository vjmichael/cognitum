"""Offline external scientific reference and falsification protocols.

Independent certified numerical references (NIST StRD) are NOT model training
information. These datasets are calibration measurements, NOT time-series
state trajectories. NIST source pages and origin audit belong in the ledger.
"""
import csv
import hashlib
import io
import json
import math
import numpy as np
from scipy.optimize import least_squares
from .ssm_stochastic import need, receipt, array
from .ssm_interop import digest, wire, read, hashid

# SHA256 of our canonical CSV transcription; NOT the original NIST .dat bytes.
SOURCES={
    'misra1a': dict(n=14,sha256='ae55d8e2a3f3d5bdc169a08cb46ef2669fd872c46657c859b3edd65f48875217',
       url='https://www.itl.nist.gov/div898/strd/nls/data/LINKS/DATA/Misra1a.dat',
       domain='dental-monolayer-adsorption',formula='b0*(1-exp(-b1*x))',
       certified=(238.94212918,.00055015643181),certified_sse=.12455138894),
    'norris':dict(n=36,sha256='75973a50205dadcc2876336eb7a9645128602b1463d18b8d928ed5cbf5bd59b0',
       url='https://itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Norris.dat',
       domain='ozone-monitor-calibration',formula='b0+b1*x',
       certified=(-.262323073774029,1.00211681802045),certified_sse=26.6173985294224)
}


def source_snapshot(name,raw,expected_sha256):
    need(name in SOURCES and type(raw) is bytes and len(raw)<8192 and hashid(expected_sha256)==digest(raw)==SOURCES[name]['sha256'],'external snapshot digest')
    try:
        t=raw.decode('ascii');rows=list(csv.reader(io.StringIO(t,newline=''),strict=True));need(rows[0]==['response','predictor'] and len(rows)==SOURCES[name]['n']+1,'source schema/row count')
        need(all(len(r)==2 and all(len(s)<=26 and s==s.strip() for s in r) for r in rows[1:]),'source cells')
        yx=np.array([[float(a),float(b)] for a,b in rows[1:]])
    except (ValueError,UnicodeError,csv.Error,IndexError,TypeError) as e:raise ValueError('invalid external snapshot') from e
    need(np.isfinite(yx).all() and np.max(abs(yx))<=1e8 and np.min(yx[:,1])>=0,'observation profile')
    if name=='misra1a':need(np.all(np.diff(yx[:,1])>0),'pressure order')
    m=SOURCES[name]
    return receipt(observations=yx,source_url=m['url'],canonical_transcription_sha256=digest(raw),n=len(yx),domain=m['domain'],source_type='observed-calibration-data',time_series=False,certified_values=m['certified'],certified_sse=m['certified_sse'],license_scope_verified=False,raw_upstream_bytes_authenticated=False)


def predict(name,coef,x):
    z=np.asarray(coef,dtype=float);x=np.asarray(x,dtype=float);need(z.shape==(2,) and np.isfinite(z).all(),'parameter profile')
    if name=='norris':return z[0]+z[1]*x
    need(name=='misra1a' and z[0]>=0 and z[1]>=0,'positive adsorption model')
    return -z[0]*np.expm1(-z[1]*x)


def fit(name,observations,idx):
    obs=array(observations,2);i=np.asarray(idx);need(name in SOURCES and obs.shape==(SOURCES[name]['n'],2) and i.ndim==1 and i.dtype.kind in 'iu' and 5<=len(i)<=len(obs) and len(np.unique(i))==len(i) and np.all(i<len(obs)),'fitting selection')
    y,x=obs[i,0],obs[i,1]
    if name=='norris':
        D=np.column_stack((np.ones(len(x)),x));s=np.linalg.svd(D,compute_uv=False);need(s[-1]>1e-10*s[0],'nonidentifiable calibration');b=np.linalg.lstsq(D,y,rcond=None)[0]
    else:
        def resid(p):return predict(name,p,x)-y
        def jac(p):
            z=np.exp(-p[1]*x);return np.column_stack((-np.expm1(-p[1]*x),p[0]*x*z))
        sols=[]
        # Generic, noncertified starting points. NIST certified parameters are never used in fitting.
        for guess in ((150.,.0004),(400.,.001)):
            sol=least_squares(resid,guess,jac=jac,bounds=([0,0],[10000,1]),max_nfev=500,xtol=1e-13,ftol=1e-13,gtol=1e-13)
            need(sol.success,'nonlinear calibration convergence');sols.append(sol)
        sol=min(sols,key=lambda z:sum(z.fun*z.fun));b=sol.x
        need(abs(np.sum(sols[0].fun**2)-np.sum(sols[1].fun**2))<=1e-6,'nonlinear starting-point mismatch')
    sse=float(np.sum((predict(name,b,x)-y)**2));return receipt(parameters=b,sse=sse,n=len(x))


def certified_fit(name,raw,expected_sha256):
    x=source_snapshot(name,raw,expected_sha256)['observations'];z=fit(name,x,np.arange(len(x)));m=SOURCES[name]
    # Compare all-data regression to independent NIST certified numerical values.
    r=np.asarray(m['certified']);rel=np.max(abs(z['parameters']-r)/np.maximum(1e-9,abs(r)))
    sse_rel=abs(z['sse']-m['certified_sse'])/max(1,m['certified_sse'])
    need(rel<1e-6 and sse_rel<5e-7,'NIST certified reference disagreement')
    return receipt(parameters=z['parameters'],sse=z['sse'],certified_parameters=r,certified_sse=m['certified_sse'],max_relative_parameter_error=float(rel),relative_sse_error=float(sse_rel),pass_certified_numerics=True,not_dynamic_validation=True)


def freeze(name,raw,seed,alpha=.25,required_gain=.02,candidate='scientific-family'):
    source_snapshot(name,raw,SOURCES[name]['sha256'])
    need(candidate in ('scientific-family','negative-control') and type(seed) is int and 0<=seed<2**32 and type(alpha) is float and .05<=alpha<=.4 and type(required_gain) is float and 0<=required_gain<=.3,'frozen experiment parameters')
    n=SOURCES[name]['n'];num_train=7 if n==14 else 18;num_cal=4 if n==14 else 10
    order=np.random.default_rng(seed).permutation(n)
    tr,ca,te=order[:num_train],order[num_train:num_train+num_cal],order[num_train+num_cal:]
    need(len(te)>=3 and math.ceil((len(ca)+1)*(1-alpha))<=len(ca),'conformal quantile needs finite sample')
    return wire(dict(version=1,kind='external-reference-experiment',dataset=name,canonical_snapshot_sha256=digest(raw),seed=seed,train=tr.tolist(),calibration=ca.tolist(),test=te.tolist(),alpha=alpha,required_gain=required_gain,source_certification_not_training=True,statistical_exchangeability_unverified=True,candidate=candidate))


def experiment(name,raw,protocol_raw,expected_protocol_sha256):
    need(hashid(expected_protocol_sha256)==digest(protocol_raw),'out-of-band frozen protocol pin')
    obs=source_snapshot(name,raw,SOURCES[name]['sha256'])['observations'];p=read(protocol_raw)
    need(set(p)=={'version','kind','dataset','canonical_snapshot_sha256','seed','train','calibration','test','alpha','required_gain','source_certification_not_training','statistical_exchangeability_unverified','candidate'} and p['version']==1 and p['kind']=='external-reference-experiment' and p['dataset']==name and p['canonical_snapshot_sha256']==digest(raw) and p['source_certification_not_training'] is True and p['statistical_exchangeability_unverified'] is True,'protocol schema')
    need(freeze(name,raw,p['seed'],p['alpha'],p['required_gain'],p['candidate'])==protocol_raw,'protocol split integrity')
    tr=np.asarray(p['train']);ca=np.asarray(p['calibration']);te=np.asarray(p['test']);z=fit(name,obs,tr)
    def null_prediction(idx):
        x=obs[idx,1]
        if name=='norris':return np.full(len(idx),obs[tr,0].mean())
        D=np.column_stack((np.ones(len(tr)),obs[tr,1]));beta=np.linalg.lstsq(D,obs[tr,0],rcond=None)[0]
        return beta[0]+beta[1]*x
    yc,xc=obs[ca,0],obs[ca,1];yt,xt=obs[te,0],obs[te,1]
    model_predict=lambda ix:predict(name,z['parameters'],obs[ix,1])
    if p['candidate']=='scientific-family':proposal=model_predict;baseline_model=null_prediction
    else:proposal=null_prediction;baseline_model=model_predict
    errors=np.abs(yc-proposal(ca))
    kth=math.ceil((len(ca)+1)*(1-p['alpha']))
    need(kth<=len(ca),'nonfinite conformal quantile');q=float(np.sort(errors)[kth-1]);yhat=proposal(te)
    baseline=baseline_model(te)
    rmse=float(np.sqrt(np.mean((yt-yhat)**2)));rmse_base=float(np.sqrt(np.mean((yt-baseline)**2)));need(rmse_base>0,'degenerate baseline')
    falsified=rmse>(1-p['required_gain'])*rmse_base
    artifact=wire(dict(version=1,kind='external-scientific-evidence',dataset=name,source_sha256=digest(raw),protocol_sha256=digest(protocol_raw),model=p['candidate'],fit_parameters=z['parameters'].tolist(),fit_selection='train-only',calibration_selection='calibration-only',test_selection='test-only',test_count=len(te),test_rmse=rmse,predeclared_baseline_rmse=rmse_base,required_gain=p['required_gain'],falsified=bool(falsified),alpha=p['alpha'],conformal_abs_radius=q,empirical_test_coverage=float(np.mean(np.abs(yt-yhat)<=q)),coverage_guarantee_claimed=False,finite_sample_exchangeability_assumed=True,real_world_calibration_verified=False,independent_nist_certification_is_external_check_only=True,execution_authorized=False))
    return receipt(evidence=artifact,diagnostic=read(artifact),model_errors=yt-yhat,baseline_errors=yt-baseline)


def replay(name,raw,protocol_raw,expected_protocol_sha256,evidence_raw):
    z=experiment(name,raw,protocol_raw,expected_protocol_sha256);need(z['evidence']==evidence_raw,'falsification or evidence artifact mismatch')
    return receipt(replayed=True,evidence_sha256=digest(evidence_raw),scientific_truth_verified=False)


def kan_hypotheses(true_fields,wrong_fields,initial,observed_final,step_seconds,steps,*,tolerance,expected_true_hashes,expected_wrong_hashes):
    """Two genuine checkpoint vector-field hypotheses; observations never fit either.

    This only falsifies numerical predictions at declared held-out initial conditions.
    It does not discover a physical law or learn a new KAN model.
    """
    from .ssm_interop import kan_evolve
    x=array(initial,1);y=array(observed_final,1)
    need(x.shape==y.shape==(2,) and np.all((x>=0)&(x<=1)) and np.all((y>=0)&(y<=1)) and type(tolerance) is float and 1e-9<=tolerance<=.2,'nonlinear test domain')
    need(type(true_fields) in (list,tuple) and type(wrong_fields) in (list,tuple) and len(true_fields)==len(wrong_fields)==2,'checkpoint profile')
    need(tuple(digest(c) for c in true_fields)==tuple(expected_true_hashes) and tuple(digest(c) for c in wrong_fields)==tuple(expected_wrong_hashes),'out-of-band checkpoint pin')
    good=kan_evolve(true_fields,x,step_seconds,steps);bad=kan_evolve(wrong_fields,x,step_seconds,steps)
    g=float(np.linalg.norm(good['states'][-1]-y));b=float(np.linalg.norm(bad['states'][-1]-y))
    return receipt(true_error=g,alternative_error=b,true_rejected=g>tolerance,alternative_rejected=b>tolerance,declared_tolerance=tolerance,checkpoint_source_only=True,autonomous_discovery_claim=False,execution_authorized=False)
