"""POST-NATIVE-05-R4: real elapsed-time physical SSM + native KAN/HDC research.

These are observational comparisons, not laws, causal identification, conformal
coverage guarantees, or actuator authorization. Future observed forcing is never used.
"""
from __future__ import annotations
import csv
import hashlib
import io
import math
from datetime import datetime, timezone

import numpy as np
from scipy.linalg import expm

from . import ssm_independent_publishers as old
from .kan_trainable import Layer, Network
from .hdc_algebra import Spec
from .hdc_associative import Cleanup

DAY = 86400
USGS_BLOBS = {
    "Rac": "0277bb41d84dc49d85b9a016fbfbce4f4ac59ed7",
    "Musk": "964a615050252f4a05ebca9d69caffed847444d1",
}
META_BLOB = "174a59d509ceb3a56d6b7c44f38cb687ed24648d"
NOAA = "noaa_partner_water_level"
HORIZONS = {"Rac": (DAY, 3 * DAY, 7 * DAY, 30 * DAY),
            "Musk": (DAY, 3 * DAY, 7 * DAY, 30 * DAY),
            NOAA: (300, 1800, 7200)}
LAGS = {"Rac": (DAY, 7 * DAY),
        "Musk": (DAY, 7 * DAY),
        NOAA: (300, 1800)}
BLOCK = {"Rac": 14, "Musk": 14, NOAA: 24}
PERIODS = {"Rac": (365.2425 * DAY, 365.2425 * DAY / 2),
           "Musk": (365.2425 * DAY, 365.2425 * DAY / 2),
           NOAA: tuple(h * 3600 for h in (12.4206, 12., 23.9345, 25.8193))}
TAUS = {"Rac": np.array([1, 3, 7, 14, 30, 60, 90], dtype=float) * DAY,
        "Musk": np.array([1, 3, 7, 14, 30, 60, 90], dtype=float) * DAY,
        NOAA: np.array([.25, .5, 1, 3, 6, 12, 24, 48, 96]) * 3600}
UPSTREAM = {
    "Rac": "DOI-USGS/loadflexBatch: Hirsch_sites/input/Q/Rac.csv",
    "Musk": "DOI-USGS/loadflexBatch: Hirsch_sites/input/Q/Musk.csv",
    NOAA: "NOAA-CO-OPS/CO-OPS-Tidal-Analysis-Datum-Calculator: data/test_timeseries_uneventimesampling.csv",
}


def need(v, desc):
    if not v:
        raise ValueError(desc)


def ingest(name, raw, metadata=None):
    """Exact publisher-hosted Git bytes, processed USGS EGRET rows or NOAA RA."""
    need(name in HORIZONS and type(raw) is bytes, "source identity/type")
    if name == NOAA:
        x = old.ingest(name, raw)
        return dict(name=name, times=x["times"], state=x["values"], unit="unverified partner source units",
                    provenance="NOAA-hosted RA partner station; original sensor and units unverified",
                    source_blob=x["source_git_blob"], excluded_duplicates=x["quarantined_rows"],
                    original_rows=x["original_records"], metadata_blob=None)
    need(old.git_blob(raw) == USGS_BLOBS[name], "USGS publisher source blob mismatch")
    need(type(metadata) is bytes and old.git_blob(metadata) == META_BLOB, "USGS site metadata digest")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"),newline="")))
    need(len(rows) >= 3000 and tuple(rows[0]) == ("date", "Q"), "USGS discharge schema/budget")
    info = list(csv.DictReader(io.StringIO(metadata.decode("utf-8"),newline="")))
    site = [r for r in info if r["site.id"] == name and r["constituent"] == "Q"]
    need(len(site) == 1 and site[0]["units"] == "cms"
         and "Discharge" in site[0]["consti.name"], "USGS unit metadata")
    t = np.array([int(datetime.strptime(r["date"],"%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()) for r in rows],dtype=np.int64)
    y = np.array([float(r["Q"]) for r in rows],dtype=float)
    need(np.isfinite(y).all() and (y >= 0).all() and np.all(np.diff(t) == DAY),
         "USGS daily dates/finite discharge")
    return dict(name=name,times=t,state=y,unit="cubic meters per second",
                provenance="USGS-hosted EGRET-derived daily discharge research examples; not signed raw instrument bytes",
                site_name=site[0]["site.name"],source_blob=USGS_BLOBS[name],
                metadata_blob=META_BLOB,original_rows=len(y),excluded_duplicates=0)


def partition(n):
    need(n >= 3000,"insufficient physical records")
    a, b = int(n * .6),int(n * .8)
    return ((0,a),(a,b),(b,n))


def eligible(s, fold, h):
    """Timestamp-exact target and history; origin/target/history must be in fold."""
    name=s["name"];t=s["times"];a,b=fold
    lut={int(q):i for i,q in enumerate(t)}
    origins=[];targets=[]
    for i in range(a,b):
        now=int(t[i]);j=lut.get(now+h)
        if j is None or not (a<=j<b):
            continue
        if all((k:=lut.get(now-lag)) is not None and a<=k<b for lag in LAGS[name]):
            origins.append(i);targets.append(j)
    return np.asarray(origins,dtype=np.int64),np.asarray(targets,dtype=np.int64)


def harmonics(name,t):
    t=np.asarray(t,dtype=float)
    c=[np.ones(len(t))]
    for period in PERIODS[name]:
        theta=2*np.pi*np.mod(t,period)/period
        c.extend((np.sin(theta),np.cos(theta)))
    return np.column_stack(c)


def harmonic_fit(s,first_fold):
    a,b=first_fold;W=harmonics(s["name"],s["times"][a:b])
    X=W.T@W+np.diag([0.]+[1e-5]*(W.shape[1]-1))
    return np.linalg.solve(X,W.T@s["state"][a:b])


def base_prediction(model,s,origins,h):
    tm=s["times"][origins]
    y=s["state"][origins]
    phase=harmonics(s["name"],tm+h)@model["harmonic"]
    origin_phase=harmonics(s["name"],tm)@model["harmonic"]
    F=ssm_zoh_rate(model["tau"],h)
    return phase+F*(y-origin_phase)


def ssm_zoh_rate(tau,elapsed):
    """Physical clock in seconds; continuous stable 1D A=-1/tau, exact ZOH."""
    need(0<float(elapsed)<=30*DAY and 0<float(tau)<=365*DAY,"elapsed clock/rate")
    scalar=math.exp(-float(elapsed)/float(tau))
    check=float(expm(np.array([[-1/float(tau)]])*float(elapsed))[0,0])
    need(abs(scalar-check)<1e-13,"independent exact exponential state transition")
    return scalar


def phi(s,origin):
    t=s["times"][origin]
    state=s["state"][origin]
    # No phase at a future measured value is read. Calendar basis is known.
    seasonal=2*np.pi*np.mod(t.astype(float),PERIODS[s["name"]][0])/PERIODS[s["name"]][0]
    z=np.log1p(state) if s["name"]!="noaa_partner_water_level" else state
    return np.column_stack((z,np.sin(seasonal),np.cos(seasonal)))


def fit(s):
    """All learned coefficients, HDC prototypes and KAN weights are train-only."""
    name=s["name"]; folds=partition(len(s["times"]));train=folds[0]
    step=min(HORIZONS[name]);o,z=eligible(s,train,step)
    need(len(o)>800,"train-only observed transition budget")
    harmonic=harmonic_fit(s,train)
    y=s["state"];t=s["times"]
    h_now=harmonics(name,t[o])@harmonic
    h_then=harmonics(name,t[z])@harmonic
    tau_candidates=TAUS[name]
    errs=[]
    for tau in tau_candidates:
        p=h_then+np.exp(-step/tau)*(y[o]-h_now)
        errs.append(float(np.mean(np.abs(y[z]-p))))
    tau=float(tau_candidates[int(np.argmin(errs))])
    model={"name":name,"tau":tau,"harmonic":harmonic,"first_horizon":step,
           "train_transitions":len(o),"train_last_timestamp":int(t[train[1]-1]),
           "ssm_generator":-1/tau,"physical_law_discovered":False}
    ssm=base_prediction(model,s,o,step)
    residual=y[z]-ssm
    state_scale=max(float(np.std(y[train[0]:train[1]])),1e-8)
    raw=phi(s,o)
    lo=raw.min(0);hi=raw.max(0);span=np.maximum(hi-lo,1e-8)
    norm=np.clip((raw-lo)/span,0,1)
    # Fixed predeclared regular subset of train transitions; no test-driven tuning.
    keep=np.linspace(0,len(o)-1,min(1536,len(o)),dtype=int)
    lay=Layer("chebyshev",3,np.tile([0.,1.],(3,1)),np.zeros((1,3,4)),
              np.ones((1,3)),np.zeros(1))
    kan=Network((lay,)).fit_linear(norm[keep],(residual[keep]/state_scale)[:,None],ridge=2.)
    _,snap=kan.research_snapshot()
    zkan=kan.evaluate(norm[keep])[0][:,0]*state_scale
    left=residual[keep]-zkan
    hdc_spec=Spec("MAP",256)
    rng=np.random.default_rng(5504)
    symbols=rng.choice([-1.,1.],size=(3,8,256)).astype(np.float32)
    def encode(row):
        bins=np.minimum((np.clip(row,0,1)*8).astype(int),7)
        return hdc_spec.bundle(np.stack([symbols[j,bins[j]] for j in range(3)]))
    labs=(raw[keep,0]>np.median(raw[keep,0])).astype(int)
    hdc=None
    if set(labs.tolist())=={0,1}:
        allcodes=np.stack([encode(x) for x in norm[keep]])
        prototypes=np.stack([allcodes[labs==k].mean(0) for k in (0,1)])
        hdc=(Cleanup(hdc_spec,prototypes),encode,
             np.array([float(np.mean(left[labs==k])) for k in (0,1)]))
    model.update(kan=kan,kan_snapshot=snap,hdc=hdc,lo=lo,span=span,
                 correction_cap=3*max(float(np.std(residual)),1e-8),
                 state_scale=state_scale,train_hdc_prototypes=(0 if hdc is None else 2))
    return model


def hybrid_forecast(model,s,o,h,*,kan=True,hdc=True):
    """Exact Δt state transition, native KAN/HDC residuals, strict OOD fallback."""
    need(model["name"]==s["name"],"cross-site fit mismatch")
    need(h in HORIZONS[s["name"]],"unregistered horizon")
    base=base_prediction(model,s,o,h)
    q=(phi(s,o)-model["lo"])/model["span"]
    valid=np.all((q>=0)&(q<=1),axis=1)
    correction=np.zeros(len(o))
    if kan and valid.any():
        for chunk in np.array_split(np.flatnonzero(valid),max(1,int(np.ceil(valid.sum()/1024)))):
            if len(chunk):
                correction[chunk]+=model["kan"].evaluate(q[chunk])[0][:,0]*model["state_scale"]
    accepted=0;abstain=len(o)
    if hdc and model["hdc"] is not None:
        bank,encode,bias=model["hdc"]
        accepted=0
        for i in np.flatnonzero(valid):
            candidate=bank.propose(encode(q[i]),minimum=.12,margin=.01)
            if candidate is not None:
                correction[i]+=bias[candidate.index]
                accepted+=1
        abstain=len(o)-accepted
    # Bounded empirical residual extrapolation; *not* estimated transport physics.
    factor=min(2.,math.expm1(-h/model["tau"])/math.expm1(-model["first_horizon"]/model["tau"]))
    correction=np.clip(correction,-model["correction_cap"],model["correction_cap"])*factor
    prediction=base+correction
    if s["name"] in USGS_BLOBS:prediction=np.maximum(0.,prediction)
    need(np.isfinite(prediction).all(),"finite observed-domain forecast")
    return prediction,{"kan_out_of_domain_origins":int((~valid).sum()),
                       "hdc_accepted_origins":accepted,"hdc_abstained_origins":abstain,
                       "teacher_forced":False,"future_sensor_value_used":False,
                       "elapsed_seconds":h}


def ridge_design(s,o,h):
    lut={int(t):i for i,t in enumerate(s["times"])}
    t=s["times"][o]
    ys=[s["state"][o]]
    for lag in LAGS[s["name"]]:
        ys.append(s["state"][[lut[int(x)-lag] for x in t]])
    calendar=harmonics(s["name"],t+h)
    return np.column_stack((*ys,*[calendar[:,j] for j in range(1,calendar.shape[1])],np.ones(len(o))))


def ridge_fit(x,y):
    means=x[:,:-1].mean(0);sd=x[:,:-1].std(0);sd=np.maximum(sd,1e-7)
    z=np.column_stack(((x[:,:-1]-means)/sd,np.ones(len(x))))
    reg=np.diag([4.]*len(means)+[0.])
    w=np.linalg.solve(z.T@z+reg,z.T@y)
    return (means,sd,w)


def ridge_predict(m,x):
    mean,sd,w=m
    z=np.column_stack(((x[:,:-1]-mean)/sd,np.ones(len(x))))
    return z@w


def metrics(y,p):
    need(np.isfinite(y).all() and np.isfinite(p).all() and len(y)>0,"scoring finite")
    err=y-p
    return {"n":len(y),"mae":float(np.mean(np.abs(err))),
            "rmse":float(np.sqrt(np.mean(err*err)))}


def blocks(v,t,step,size):
    need(len(v)==len(t) and len(v)>0 and np.all(np.diff(t)>0),"ordered residual blocks")
    bounds=np.r_[0,np.flatnonzero(np.diff(t)!=step)+1,len(t)]
    arr=[v[a+j:a+j+size] for a,b in zip(bounds[:-1],bounds[1:])
         for j in range(0,b-a-size+1,size)]
    return np.stack(arr) if arr else np.empty((0,size))


def block_calibrate(cal_y,cal_pred,cal_t,test_y,test_pred,test_t,name):
    size=BLOCK[name];step=300 if name==NOAA else DAY
    train=blocks(np.abs(cal_y-cal_pred),cal_t,step,size)
    test=blocks(np.abs(test_y-test_pred),test_t,step,size)
    if len(train)<20 or len(test)<10:
        return {"status":"REFUSED_INSUFFICIENT_DEPENDENT_BLOCKS",
                "cal_blocks":len(train),"test_blocks":len(test),
                "nominal":.9,"conditional_coverage_guaranteed":False}
    k=math.ceil((len(train)+1)*.9)-1
    need(k<len(train),"finite rank")
    rad=float(np.sort(train.max(axis=1))[k])
    hit=np.abs(test_y-test_pred)<=rad
    return {"status":"DESCRIPTIVE_BLOCK_MAX_ONLY","nominal":.9,
            "cal_blocks":len(train),"test_blocks":len(test),
            "radius":rad,"origin_coverage":float(np.mean(hit)),
            "simultaneous_block_coverage":float(np.mean(test.max(1)<=rad)),
            "first_half":float(np.mean(hit[:len(hit)//2])),
            "second_half":float(np.mean(hit[len(hit)//2:])),
            "synthetic_shift_3r_coverage":float(np.mean(np.abs(test_y-test_pred+3*rad)<=rad)),
            "conditional_coverage_guaranteed":False}


def bootstrap_gain(y,base,hybrid,t,name):
    step=300 if name==NOAA else DAY
    size=BLOCK[name]
    base_error=np.abs(y-base);gain=base_error-np.abs(y-hybrid)
    b=blocks(gain,t,step,size)
    if len(b)<12:
        return {"status":"REFUSED_DEPENDENT_BOOTSTRAP","blocks":len(b)}
    rng=np.random.default_rng(5506)
    draws=[]
    for _ in range(320):
        ix=rng.integers(0,len(b),len(b))
        draws.append(float(np.mean(b[ix])))
    return {"status":"DESCRIPTIVE_MOVING_CONSECUTIVE_BLOCK_BOOTSTRAP",
            "mean_gain":float(np.mean(gain)),"block_count":len(b),
            "interval_95":[float(v) for v in np.quantile(draws,[.025,.975])],
            "strict_superiority":bool(np.quantile(draws,.025)>0),
            "not_proof_of_generalization":True}


def missing_audit(s,o,target,y,p,h):
    """Outage censors *sensor times*; outcome selection shown only retrospectively."""
    n=len(o);idx=np.arange(len(s["times"]))
    # 72 consecutive observed slots out of each 1000 in held-out time window.
    offline=(idx%1000)<72
    lookup={int(v):i for i,v in enumerate(s["times"])}
    remain=np.ones(n,dtype=bool)
    for lag in (0,*LAGS[s["name"]]):
        historical=np.array([lookup[int(s["times"][j])-lag] for j in o])
        remain &= ~offline[historical]
    remain &= ~offline[target]
    need(remain.any(),"outage selection exhausted")
    cutoff=np.quantile(y,.9)
    high=y<cutoff
    need(high.any(),"upper-tail censoring exhausted")
    return {"full":metrics(y,p),"synthetic_outage":metrics(y[remain],p[remain]),
            "retained_outage_fraction":float(remain.mean()),
            "counterfactual_upper_decile_censored":metrics(y[high],p[high]),
            "retained_upper_tail_fraction":float(high.mean()),
            "imputed_missing_observations":False,
            "retrospective_heldout_targets_only_for_sensitivity":True}


def evaluate(s,*,with_ablation=True):
    f=partition(len(s["times"]));m=fit(s);name=s["name"]
    y=s["state"];t=s["times"];outputs={}
    for h in HORIZONS[name]:
        fold=[eligible(s,g,h) for g in f]
        (ot,zt),(oc,zc),(oe,ze)=fold
        need(len(ot)>500 and len(oc)>100 and len(oe)>100,"horizon effective sample budget")
        ridge=ridge_fit(ridge_design(s,ot,h),y[zt])
        models={};statistics={}
        for foldname,o,z in (("cal",oc,zc),("test",oe,ze)):
            direct=ridge_predict(ridge,ridge_design(s,o,h))
            simple=harmonics(name,t[o]+h)@m["harmonic"]
            ssm=base_prediction(m,s,o,h)
            full,stats=hybrid_forecast(m,s,o,h)
            preds={"persistence":y[o],"harmonic":simple,"direct_ridge":direct,
                   "timeaware_ssm":ssm,"HDC_KAN_SSM":full}
            if with_ablation:
                preds["SSM_KAN_no_HDC"]=hybrid_forecast(m,s,o,h,hdc=False)[0]
                preds["SSM_HDC_no_KAN"]=hybrid_forecast(m,s,o,h,kan=False)[0]
            models[foldname]=preds;statistics[foldname]=stats
        # Baseline chosen *only* on calibration. Do not pick test winner.
        baselines=("persistence","harmonic","direct_ridge","timeaware_ssm")
        chosen=min(baselines,key=lambda k:metrics(y[zc],models["cal"][k])["mae"])
        mc=models["cal"];mt=models["test"];truth=y[ze]
        report={k:metrics(truth,v) for k,v in mt.items()}
        uncertainty=block_calibrate(y[zc],mc["HDC_KAN_SSM"],t[oc],truth,mt["HDC_KAN_SSM"],t[oe],name)
        baseline_interval=block_calibrate(y[zc],mc[chosen],t[oc],truth,mt[chosen],t[oe],name)
        bootstrap=bootstrap_gain(truth,mt[chosen],mt["HDC_KAN_SSM"],t[oe],name)
        outputs[str(h)]={"forecast_horizon_seconds":h,"train_origins":len(ot),
                         "cal_origins":len(oc),"test_origins":len(oe),
                         "calibration_selected_baseline":chosen,
                         "heldout_metrics":report,"hybrid_interval":uncertainty,
                         "baseline_interval":baseline_interval,
                         "hybrid_mae_gain_bootstrap_95":bootstrap,
                         "sensor_outage_sensitivity":missing_audit(s,oe,ze,truth,mt["HDC_KAN_SSM"],h),
                         "hybrid_stats":statistics["test"],
                         "selection_on_test":False}
    return {"source":name,"publisher":("DOI-USGS" if name in USGS_BLOBS else "NOAA-CO-OPS"),
            "unit":s["unit"],"physical_provenance":s["provenance"],
            "observations":len(t),"source_blob":s["source_blob"],
            "model_native_components":["continuous_time_scalar_SSM_exact_exponential",
                "trained_Cognitum_Chebyshev_KAN","Cognitum_MAP_HDC_Cleanup"],
            "kan_snapshot_sha256":m["kan_snapshot"],"train_last_timestamp":m["train_last_timestamp"],
            "tau_seconds_train_only":m["tau"],"trained_hdc_prototypes":m["train_hdc_prototypes"],
            "real_elapsed_time_not_index":True,"future_sensor_value_used":False,
            "full_hybrid_universal_superiority_proven":False,
            "physical_law_discovered":False,"causal_transport_model":False,
            "conditional_dependent_coverage_guaranteed":False,
            "original_sensor_signed_attestation_verified":False,
            "execution_authorized":False,"horizons":outputs}
