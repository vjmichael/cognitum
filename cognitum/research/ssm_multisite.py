"""POST-NATIVE-04 bounded, observational, *not* autonomous physical-law discovery.

Pre-registered causal multi-step forecasts, fixed chronological partitions, and
block-wise empirical uncertainty diagnostics.  UCI source data and units are
not interchangeable, and future weather measurements are never given to a
forecast at its origin.  No external execution authority.
"""
import csv
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
import numpy as np
from . import ssm_observed_dynamics as prior

MANIFEST_SHA='3f47ec84d49d9a169124f3c9778a87c42f10f910b334a4faf906bf76774112f3'
SITES=('Changping','Dingling','Guanyuan')
BEIJING_ARCHIVE='b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4'
LAGS=(1,2,3,6,12,24)
HORIZONS={'building':(1,6,12),'beijing':(1,6,24)}

def need(condition, message):
    if not condition:raise ValueError(message)

def hashbytes(raw):return sha256(raw).hexdigest()

def ingest_site(site, raw, manifest_raw):
    need(type(site) is str and site in SITES and type(raw) is bytes and type(manifest_raw) is bytes,'source type/site')
    need(hashbytes(manifest_raw)==MANIFEST_SHA,'manifest hash')
    manifest=json.loads(manifest_raw)
    need(manifest['license']=='CC BY 4.0' and manifest['outer_archive_sha256']==BEIJING_ARCHIVE and len(manifest['entries'])==3,'manifest schema/rights')
    entry=next(e for e in manifest['entries'] if e['site']==site)
    need(hashbytes(raw)==entry['excerpt_sha256'] and entry['rows']==6144 and entry['missing_target_temp']==0 and entry['missing_selected_forcing']==0,'site source digest/missing')
    rows=list(csv.DictReader(StringIO(raw.decode('utf-8'),newline='')))
    need(len(rows)==6144 and tuple(rows[0])==tuple(entry['columns']),'row/schema count')
    state=[];forcing=[];times=[];missing=0
    for row in rows:
        t=datetime(*(int(row[k]) for k in ('year','month','day','hour')))
        if times:need((t-times[-1]).total_seconds()==3600,'non-hourly time')
        times.append(t)
        missing+=row['PM2.5'] in ('NA','')
        values=np.array([float(row[k]) for k in ('TEMP','WSPM')]);need(np.isfinite(values).all(),'missing/not finite forcing')
        v=row['PM2.5'];state.append(float('nan') if v in ('NA','') else float(v));forcing.append(values)
    need(missing==entry['missing_aux_pm25'] and np.isfinite(np.asarray(state)[np.isfinite(state)]).all() and np.nanmin(state)>=0,'target missingness/physical range')
    return dict(dataset='beijing-'+site,site=site,times=tuple(times),state=np.array(state),forcing=np.array(forcing),missing_target=missing,missing_auxiliary=0,target_unit='ug/m3',sha256=entry['excerpt_sha256'],archive_sha256=BEIJING_ARCHIVE,interval_seconds=3600,attribution=manifest['attribution'])

def specs(series):
    need(len(series['state'])==6144 and len(series['forcing'])==6144,'series size')
    building=series['interval_seconds']==600
    need(series['interval_seconds'] in (600,3600),'frequency')
    return dict(period=144 if building else 24,block=36 if building else 24,horizons=HORIZONS['building' if building else 'beijing'])

def partitions(series,history,hmax):
    """Forecast origins in each block; both past context and final target stay inside."""
    n=len(series['state']);need(n==6144 and type(history) is int and 24<=history<=144 and 1<=hmax<=24,'partition budget')
    edges=(0,int(.6*n),int(.8*n),n)
    regions=[]
    for a,b in zip(edges,edges[1:]):
        origins=np.arange(a+history-1,b-hmax,dtype=int)
        if not np.all(np.isfinite(series['state'])):
            observed=np.isfinite(series['state']).astype(int)
            coverage=np.convolve(observed,np.ones(history+hmax,dtype=int),mode='valid')
            origins=origins[coverage[origins-history+1]==history+hmax]
        regions.append(origins)
    return tuple(regions)

def features(y,origins,season):
    """All lagged observations lie at or before the forecast origin."""
    need(season in (24,144) and np.min(origins)>=23 and np.max(origins)<len(y),'feature origin')
    v=np.column_stack([y[origins+1-lag] for lag in LAGS]);phase=(origins%season)*2*np.pi/season
    return np.column_stack((v,np.sin(phase),np.cos(phase),np.ones(len(origins))))

def direct_fit(y,train,season,horizons):
    """Train-only ridge direct multi-step prediction, predeclared penalty 1.0."""
    y=np.asarray(y,dtype=float);need(len(train)>500 and np.isfinite(y[train+max(horizons)]).all(),'direct data')
    D=features(y,train,season);need(np.isfinite(D).all(),'lagged direct data')
    means=D[:,:-1].mean(0);scale=D[:,:-1].std(0);need(np.all(scale>1e-8),'direct rank')
    X=np.column_stack(((D[:,:-1]-means)/scale,np.ones(len(train))))
    gram=X.T@X+np.diag([1.0]*(X.shape[1]-1)+[0.]);inverse=np.linalg.solve(gram,X.T)
    weights={h:inverse@y[train+h] for h in horizons}
    return dict(means=means,scales=scale,weights=weights,season=season)

def direct_forecast(model,y,origins,horizons):
    D=features(y,origins,model['season']);X=np.column_stack(((D[:,:-1]-model['means'])/model['scales'],np.ones(len(origins))))
    return {h:X@model['weights'][h] for h in horizons}

def ar_fit(y,train):
    D=np.column_stack([y[train+1-lag] for lag in LAGS]);need(np.isfinite(D).all() and np.isfinite(y[train+1]).all(),'AR train mask');means=D.mean(0);scales=D.std(0);need(np.all(scales>1e-8),'AR scale')
    X=np.column_stack(((D-means)/scales,np.ones(len(train))));reg=np.diag([3.0]*len(LAGS)+[0.]);coef=np.linalg.solve(X.T@X+reg,X.T@y[train+1])
    return dict(means=means,scales=scales,coef=coef)

def ar_forecast(fit,y,origins,hmax):
    history=np.column_stack([y[origins-k] for k in range(24)])
    out=[]
    for _ in range(hmax):
        D=history[:,np.asarray(LAGS)-1];n=(D-fit['means'])/fit['scales'];pred=n@fit['coef'][:-1]+fit['coef'][-1]
        need(np.isfinite(pred).all() and np.max(abs(pred))<1e6,'AR recursion stability')
        out.append(pred);history=np.column_stack((pred,history[:,:-1]))
    return np.array(out)

def relaxation_fit(y,train,season):
    """Phenomenological diurnal equilibrium + exponentially damped displacement.

    It is a *baseline*, NOT a thermodynamic law or identified heat balance.
    """
    clim=np.array([np.mean(y[train[train%season==j]]) for j in range(season)])
    a=y[train]-clim[train%season];b=y[train+1]-clim[(train+1)%season]
    rho=float(np.clip((a@b)/(a@a+1e-8),0.,.999))
    return dict(season=season,climatology=clim,rho=rho)

def relaxation_forecast(fit,y,origins,hmax):
    return np.array([fit['climatology'][(origins+h)%fit['season']]+(fit['rho']**h)*(y[origins]-fit['climatology'][origins%fit['season']]) for h in range(1,hmax+1)])


def heat_exchange_fit(series,train):
    """Constrained one-zone Newtonian exchange with *frozen observed* outdoor T.

    Simplified phenomenological thermal baseline; no occupancy/solar model or
    actual future exterior measurements.  Applicable to building only.
    """
    need(series['interval_seconds']==600,'heat baseline domain')
    y=series['state'];outside=series['forcing'][:,0]
    drive=outside[train]-y[train];change=y[train+1]-y[train]
    gain=float(np.clip((drive@change)/(drive@drive+1e-9),0.,1.))
    return gain

def heat_exchange_forecast(gain,series,origins,hmax):
    y=series['state'][origins];outside=series['forcing'][origins,0]
    return np.array([outside+(1-gain)**h*(y-outside) for h in range(1,hmax+1)])

def wind_dilution_fit(series,train,season):
    """Phenomenological nonnegative sink toward train-only diurnal mean.

    Observed wind at origin is held fixed; NOT a dispersion or transport PDE.
    """
    need(series['interval_seconds']==3600 and series['dataset'].startswith('beijing-'),'wind domain')
    y=series['state'];clim=np.array([y[train[train%season==j]].mean() for j in range(season)])
    wind=np.maximum(series['forcing'][train,1],0);drive=wind*(y[train]-clim[train%season])
    target=y[train+1]-clim[(train+1)%season]-(y[train]-clim[train%season])
    k=float(np.clip(-(drive@target)/(drive@drive+1e-8),0.,.5))
    return dict(climatology=clim,k=k,season=season)

def wind_dilution_forecast(fit,series,origins,hmax):
    y=series['state'][origins];wind=np.maximum(series['forcing'][origins,1],0)
    return np.array([np.maximum(0.,fit['climatology'][(origins+h)%fit['season']]+(y-fit['climatology'][origins%fit['season']])*np.exp(-fit['k']*wind*h)) for h in range(1,hmax+1)])

def baseline_forecasts(y,train,origins,season,horizons):
    hmax=max(horizons);fit_d=direct_fit(y,train,season,horizons);fit_a=ar_fit(y,train);fit_r=relaxation_fit(y,train,season)
    seasonal=np.array([y[origins+h-season] for h in range(1,hmax+1)])
    predictions={
      'persistence':np.tile(y[origins],(hmax,1)),
      'seasonal_naive':seasonal,
      'ridge_AR24':ar_forecast(fit_a,y,origins,hmax),
      'daily_relaxation':relaxation_forecast(fit_r,y,origins,hmax),
    }
    direct=direct_forecast(fit_d,y,origins,horizons)
    return predictions,direct,dict(direct=fit_d,autoregressive=fit_a,relaxation=fit_r)

def causal_model(series,train):
    """Genuine existing SSM/KAN/HDC interfaces with train-only parameters."""
    s=series;y=s['state'];D,delta,mean,sd=prior.design(s,train);coef=prior.learn_ssm(D,delta,train)
    p=np.column_stack((y,s['forcing']));ssm=y[:-1]+sd[0]*(D[:-1]@coef);residual=(y[1:]-ssm)/sd[0]
    norm,mask=prior.normalized(s,train);network,snapshot=prior.kan_fit(norm,residual,train)
    corr=prior.batch_kan(network,norm[:-1],mask[:-1])*sd[0]
    r=np.zeros(len(y));r[:-1]=y[1:]-ssm-corr
    hdc=prior.train_hdc(norm,mask,train,r)
    low=p[train].min(0);high=p[train].max(0)
    return dict(coef=coef,mean=mean,sd=sd,low=low,high=high,network=network,hdc=hdc,snapshot_sha=snapshot,train_n=len(train),residual_based=True)

def hybrid_forecast(model,series,origins,hmax,enable_kan=True,enable_hdc=True):
    """Recursive, no future targets or future weather. Hold origin forcing fixed.

    HDC context is queried at origin and kept fixed. OOD KAN inputs abstain
    to SSM only; no auto-authorized physical actions are possible.
    """
    y=series['state'];force=series['forcing'][origins];current=y[origins].copy();result=[]
    all_input=np.column_stack((y,series['forcing']));normalized=(all_input-model['low'])/(model['high']-model['low'])
    valid=np.all((normalized>=0)&(normalized<=1),axis=1)
    bias=np.zeros(len(origins));abstain=len(origins)
    # Lookup is grounded in observed state at forecast origin and frozen for the horizon.
    if enable_hdc and model['hdc'] is not None:
        full_bias,stats=prior.hdc_predict(model['hdc'],normalized,valid,origins)
        bias=full_bias[origins];abstain=stats['abstained']
    out_of_domain=0
    for _ in range(hmax):
        p=np.column_stack((current,force));px=(p-model['mean'])/model['sd']
        d=model['coef'][2]*px[:,0]+model['coef'][0]*px[:,1]+model['coef'][1]*px[:,2]+model['coef'][3]
        x=(p-model['low'])/(model['high']-model['low']);domain=np.all((x>=0)&(x<=1),axis=1)
        out_of_domain+=int(np.sum(~domain))
        correction=(prior.batch_kan(model['network'],x,domain)*model['sd'][0] if enable_kan else np.zeros(len(origins)))
        current=np.maximum(0.,current+model['sd'][0]*d+correction+bias) if series['dataset'].startswith('beijing-') else current+model['sd'][0]*d+correction+bias
        need(np.isfinite(current).all() and np.max(abs(current))<1e6,'hybrid recursion instability')
        result.append(current.copy())
    return np.asarray(result),dict(origin_hdc_abstained=int(abstain),kan_out_of_domain_steps=out_of_domain,origin_count=len(origins),reused_future_forcing=False,teacher_forced=False)

def rank_radius(errors,alpha=.1):
    values=np.sort(np.asarray(errors,dtype=float));n=len(values);k=int(np.ceil((n+1)*(1-alpha)))-1
    need(n>0 and 0<=k<n and np.isfinite(values).all(),'conformal rank budget')
    return float(values[k])

def contiguous_blocks(residual,indices,block):
    """Only genuine adjacent-time, nonoverlapping blocks; never bridge NA gaps."""
    v=np.asarray(residual);i=np.asarray(indices)
    need(v.ndim==1 and i.shape==v.shape and np.all(np.diff(i)>0),'chronological blocks')
    start=np.r_[0,np.flatnonzero(np.diff(i)!=1)+1];end=np.r_[start[1:],len(i)]
    chunks=[v[a+q:a+q+block] for a,b in zip(start,end) for q in range(0,b-a-block+1,block)]
    need(len(chunks)>=20,'insufficient independent blocks')
    return np.stack(chunks)

def block_radius(residual,block,alpha=.1,origins=None):
    """Nonoverlapping calibration blocks, order statistic on block maxima.

    Empirical dependence-aware diagnostic only; stationarity/block exchangeability
    must NOT be assumed, hence this is NOT an unconditional coverage guarantee.
    """
    r=np.abs(np.asarray(residual,dtype=float));need(r.ndim==1 and type(block) is int and 12<=block<=48 and len(r)//block>=20,'block calibration budget')
    count=len(r)//block;maxima=(r[:count*block].reshape(count,block).max(1) if origins is None else contiguous_blocks(r,origins,block).max(1));count=len(maxima)
    return rank_radius(maxima,alpha),count

def block_bootstrap_gain(reference,model,block,seed=4901,draws=256,origins=None):
    a=np.asarray(reference,dtype=float);b=np.asarray(model,dtype=float)
    need(a.shape==b.shape and a.ndim==1 and type(block) is int and 12<=block<=48 and len(a)>=block*20,'bootstrap input')
    gain=a-b;n=len(a);starts=np.arange(0,n-block+1);rng=np.random.default_rng(seed)
    if origins is not None:
        i=np.asarray(origins);need(i.shape==a.shape,'bootstrap origin shape')
        starts=starts[(i[starts+block-1]-i[starts])==block-1]
        need(len(starts)>=20,'insufficient contiguous bootstrap blocks')
    est=[]
    for _ in range(draws):
        ix=rng.choice(starts,size=int(np.ceil(n/block)),replace=True)
        draw=np.concatenate([gain[i:i+block] for i in ix])[:n]
        est.append(float(draw.mean()))
    return tuple(map(float,np.quantile(est,[.025,.975])))

def score_by_horizon(y,origins,forecast,horizons):
    result={}
    for h in horizons:
        actual=y[origins+h];pred=forecast[h-1] if isinstance(forecast,np.ndarray) else forecast[h]
        errors=actual-pred
        result[str(h)]=dict(rmse=float(np.sqrt(np.mean(errors**2))),mae=float(np.mean(np.abs(errors))))
    return result

def evaluate(series,include_hybrid=False):
    s=series;config=specs(s);season=config['period'];horizons=config['horizons'];H=max(horizons)
    train,cal,test=partitions(s,season,H);y=s['state'];need(len(train)>500 and len(cal)>500 and len(test)>500,'min periods')
    cal_baseline,cal_direct,model=baseline_forecasts(y,train,cal,season,horizons)
    test_baseline={
        'persistence':np.tile(y[test],(H,1)),
        'seasonal_naive':np.array([y[test+h-season] for h in range(1,H+1)]),
        'ridge_AR24':ar_forecast(model['autoregressive'],y,test,H),
        'daily_relaxation':relaxation_forecast(model['relaxation'],y,test,H)}
    test_direct=direct_forecast(model['direct'],y,test,horizons)
    if s['dataset'].startswith('beijing-'):
        fitwind=wind_dilution_fit(s,train,season)
        cal_baseline['wind_dilution']=wind_dilution_forecast(fitwind,s,cal,H)
        test_baseline['wind_dilution']=wind_dilution_forecast(fitwind,s,test,H)
    if s['interval_seconds']==600:
        k=heat_exchange_fit(s,train)
        cal_baseline['newtonian_heat_exchange']=heat_exchange_forecast(k,s,cal,H)
        test_baseline['newtonian_heat_exchange']=heat_exchange_forecast(k,s,test,H)
    allmetrics={name:score_by_horizon(y,test,p,horizons) for name,p in test_baseline.items()}
    allmetrics['direct_ridge']=score_by_horizon(y,test,test_direct,horizons)
    hy_stats=None;kan_snapshot=None
    if include_hybrid:
        fit=causal_model(s,train);kan_snapshot=fit['snapshot_sha']
        hybrid_cal,stats_cal=hybrid_forecast(fit,s,cal,H)
        hybrid_test,hy_stats=hybrid_forecast(fit,s,test,H)
        allmetrics['HDC_KAN_SSM']=score_by_horizon(y,test,hybrid_test,horizons)
        without_hdc,_=hybrid_forecast(fit,s,test,H,enable_hdc=False)
        allmetrics['SSM_KAN_without_HDC']=score_by_horizon(y,test,without_hdc,horizons)
        without_kan,_=hybrid_forecast(fit,s,test,H,enable_kan=False)
        allmetrics['SSM_HDC_without_KAN']=score_by_horizon(y,test,without_kan,horizons)
    else:
        hybrid_cal=cal_baseline['ridge_AR24'];hybrid_test=test_baseline['ridge_AR24']
    interval={};negative={}
    for h in horizons:
        idx=h-1;observed=y[test+h];cal_actual=y[cal+h]
        err_cal=cal_actual-hybrid_cal[idx];err_test=observed-hybrid_test[idx]
        iid=rank_radius(np.abs(err_cal));rad,blocks=block_radius(err_cal,config['block'],origins=cal)
        coverage=np.abs(err_test)<=rad
        max_test=contiguous_blocks(np.abs(err_test),test,config['block']).max(1);ncomplete=len(max_test)
        interval[str(h)]=dict(iid_radius=iid,block_max_radius=rad,calibration_blocks=blocks,
           coverage_empirical=float(np.mean(coverage)),test_blocks=ncomplete,
           simultaneous_block_coverage_empirical=float(np.mean(max_test<=rad)),
           first_half=float(np.mean(coverage[:len(coverage)//2])),second_half=float(np.mean(coverage[len(coverage)//2:])),
           shift_plus_3radius_coverage=float(np.mean(np.abs(err_test+3*rad)<=rad)))
        best=min(allmetrics,key=lambda name:allmetrics[name][str(h)]['rmse'])
        gains={name:block_bootstrap_gain(np.abs(observed-test_baseline['persistence'][idx]),np.abs(observed-(p[idx] if isinstance(p,np.ndarray) else p[h])),config['block'],origins=test) for name,p in {**test_baseline,'direct_ridge':test_direct,**({'HDC_KAN_SSM':hybrid_test} if include_hybrid else {})}.items() if name!='persistence'}
        negative[str(h)]=dict(best_rmse_model=best,bootstrap_persistence_mae_gains_95=gains,insufficient_dependence_guarantee=True)
    return dict(dataset=s['dataset'],source_sha256=s['sha256'],train_origins=len(train),cal_origins=len(cal),test_origins=len(test),horizons=horizons,unit=('ug/m3' if s['dataset'].startswith('beijing-') else 'degC'),
       models=allmetrics,intervals=interval,falsification=negative,hybrid_stats=hy_stats,kan_snapshot_sha256=kan_snapshot,
       future_forcing_or_target_used_in_forecast=False,model_selection_on_test=False,physical_law_discovered=False,
       distribution_free_dependent_coverage_claim=False,execution_authorized=False)

def cross_site_transfer(donor,recipient,horizons=(1,6,24)):
    """Zero-shot learned direct ridge forecast from site A on heldout site B.
    Same UCI publisher and region; independent sensor locations, not independent
    historical archive/publisher or independent weather system.
    """
    need(donor['dataset']!=recipient['dataset'] and donor['interval_seconds']==recipient['interval_seconds']==3600 and donor['dataset'].startswith('beijing-') and recipient['dataset'].startswith('beijing-') and donor.get('target_unit')==recipient.get('target_unit')=='ug/m3','cross-site target-domain units')
    dtrain,_,_=partitions(donor,24,24);_,_,test=partitions(recipient,24,24)
    fit=direct_fit(donor['state'],dtrain,24,horizons)
    pred=direct_forecast(fit,recipient['state'],test,horizons)
    return dict(donor=donor['dataset'],recipient=recipient['dataset'],donor_sha256=donor['sha256'],recipient_sha256=recipient['sha256'],
      zero_shot_direct=score_by_horizon(recipient['state'],test,pred,horizons),
      persistence=score_by_horizon(recipient['state'],test,np.tile(recipient['state'][test],(24,1)),horizons),
      test_origins=len(test),research_only=True,execution_authorized=False)
