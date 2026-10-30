"""C14 P4E G9: seeded, auditable synthetic interval comparison (OFFLINE / RESEARCH ONLY).

Compare G8 population-mix Wald, nonparametric pairs bootstrap percentile/basic/BCa,
and two-fold cross-fitted augmented inverse-probability-weighting (AIPW) IF Wald.
All causal interpretations require consistency, conditional exchangeability, positivity.
AIPW doubly-robust *consistency* is conditional on one nuisance model being correct,
not protection against hidden confounding, time dependence or arbitrary bias.
None of these confidence intervals is a causal-certainty or host-security receipt.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import norm
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g8_uncertainty as g8

PHASE='C14 P4E G9'
METHODS=('G8_POPULATION_MIX_WALD','PAIRS_BOOT_PERCENTILE','PAIRS_BOOT_BASIC',
         'PAIRS_BOOT_BCA','PAIRS_BOOT_NORMAL','AIPW_CROSSFIT_IF_WALD')
SCENARIOS=g7.SCENARIOS
MAX_RESAMPLES=1999


def counted(rows):
    x=g8.require_binary(rows)
    cells=np.bincount((x[:,0]*4+x[:,1]*2+x[:,2]).astype(int),minlength=8)
    return cells.astype(np.int64)


def _standardized_from_counts(cells,min_arm=5):
    """Vectorized standardization of binary 2x2x2 contingency tables."""
    c=np.asarray(cells,dtype=float)
    if c.shape[-1]!=8:raise ValueError('EIGHT_CELL_COUNTS_REQUIRED')
    original_ndim=c.ndim
    c=np.atleast_2d(c)
    arm=c.reshape(-1,2,2,2).sum(axis=-1)
    n=c.sum(axis=1)
    eligible=(arm>=min_arm).all(axis=(1,2))&(n>0)
    successes=c.reshape(-1,2,2,2)[:,:,:,1]
    rate=np.divide(successes,arm,out=np.zeros_like(successes),where=arm>0)
    weights=arm.sum(axis=2)/n[:,None]
    effects=(weights*(rate[:,:,1]-rate[:,:,0])).sum(axis=1)
    effects[~eligible]=np.nan
    return float(effects[0]) if original_ndim==1 else effects


def bootstrap_intervals(rows, *, seed, resamples=399, confidence=.95, min_arm=5):
    if not isinstance(seed,int) or seed<0 or seed>2**32-1 or not 99<=resamples<=MAX_RESAMPLES or not .5<=confidence<1:
        raise ValueError('INVALID_BOOTSTRAP_BUDGET')
    cells=counted(rows);n=int(cells.sum())
    theta=_standardized_from_counts(cells,min_arm)
    if not math.isfinite(theta):
        return {'status':'REJECTED_INSUFFICIENT_POSITIVITY','valid_resamples':0,'requested_resamples':resamples}
    # Sampling entire iid observed triples, NOT separate z/t/y columns.
    random=np.random.default_rng(seed)
    draws=random.multinomial(n,cells/n,size=resamples)
    values=_standardized_from_counts(draws,min_arm)
    valid=values[np.isfinite(values)]
    if len(valid)!=resamples:
        # Never quietly discard failures and report a nominal CI.
        return {'status':'REJECTED_BOOTSTRAP_OVERLAP_FAILURE','valid_resamples':int(len(valid)),
                'requested_resamples':resamples,'estimate':theta}
    alpha=(1-confidence)/2
    lo,hi=np.quantile(valid,[alpha,1-alpha])
    methods={
      'PAIRS_BOOT_PERCENTILE':(float(lo),float(hi)),
      'PAIRS_BOOT_BASIC':(float(2*theta-hi),float(2*theta-lo)),
    }
    # Bootstrap normal interval: standard error estimated from bootstrap SD.
    sd=float(np.std(valid,ddof=1));zcrit=float(norm.ppf(1-alpha))
    methods['PAIRS_BOOT_NORMAL']=(theta-zcrit*sd,theta+zcrit*sd)
    # BCa bias correction and jackknife acceleration; only eight unique leave-one-out
    # counts exist in the binary 2x2x2 empirical distribution.
    jack=[];multiplicity=[]
    for k,ct in enumerate(cells):
        if ct:
            reduced=cells.copy();reduced[k]-=1
            estimate=_standardized_from_counts(reduced,min_arm)
            if not math.isfinite(estimate):
                return {'status':'REJECTED_BCA_JACKKNIFE_OVERLAP','valid_resamples':resamples,
                        'requested_resamples':resamples,'estimate':theta}
            jack.append(estimate);multiplicity.append(int(ct))
    jack=np.asarray(jack);multiplicity=np.asarray(multiplicity)
    mean=float(np.average(jack,weights=multiplicity))
    diff=mean-jack
    cubed=float(np.sum(multiplicity*diff**3));square=float(np.sum(multiplicity*diff**2))
    a=cubed/(6*square**1.5) if square>1e-22 else 0.0
    smaller=int(np.count_nonzero(valid<theta));ties=int(np.count_nonzero(valid==theta))
    fraction=(smaller+0.5*ties)/resamples
    fraction=max(1/(2*resamples),min(1-1/(2*resamples),fraction))
    z0=float(norm.ppf(fraction))
    target=[]
    for tail in (alpha,1-alpha):
        zz=z0+float(norm.ppf(tail));denom=1-a*zz
        if abs(denom)<1e-8:
            return {'status':'REJECTED_BCA_UNSTABLE_ACCELERATION','valid_resamples':resamples,
                    'requested_resamples':resamples,'estimate':theta}
        target.append(float(norm.cdf(z0+zz/denom)))
    if target[0]>=target[1] or min(target)<0 or max(target)>1:
        return {'status':'REJECTED_BCA_DEGENERATE','valid_resamples':resamples,
                'requested_resamples':resamples,'estimate':theta}
    bca=np.quantile(valid,target)
    methods['PAIRS_BOOT_BCA']=(float(bca[0]),float(bca[1]))
    return {'status':'COMPUTED','estimate':theta,'resamples':resamples,
            'bootstrap_standard_error':sd,'valid_resamples':resamples,
            'requested_resamples':resamples,'bca_acceleration':a,
            'methods':{name:{'lower':float(max(-1,lo)),'upper':float(min(1,hi))}
                       for name,(lo,hi) in methods.items()}}


def aipw_crossfit(rows, *, seed, confidence=.95, propensity_spec='stratified',
                  outcome_spec='stratified', min_arm=5):
    """2-fold out-of-sample nuisance estimation + empirical IF SE.

    Binary Z,T,Y. Laplace-smoothed saturated nuisance means; pooled forms are
    knowingly misspecified on confounded/heterogeneous fixtures. Cross-fitting
    avoids using each target outcome to fit its own predicted outcome.
    """
    if propensity_spec not in ('stratified','pooled') or outcome_spec not in ('stratified','pooled'):
        raise ValueError('INVALID_NUISANCE_SPEC')
    if not isinstance(seed,int) or seed<0 or seed>2**32-1 or not .5<=confidence<1:
        raise ValueError('INVALID_AIPW_PARAMETERS')
    x=g8.require_binary(rows);n=len(x)
    if not math.isfinite(_standardized_from_counts(counted(x),min_arm)):
        return {'status':'REJECTED_INSUFFICIENT_POSITIVITY'}
    fold=np.empty(n,dtype=np.int8)
    perm=np.random.default_rng(seed).permutation(n)
    fold[perm[:n//2]]=0;fold[perm[n//2:]]=1
    scores=np.empty(n)
    for holdout in (0,1):
        train=x[fold!=holdout];test=x[fold==holdout]
        # require observed treatment positivity *in each train fold*
        z=train[:,0];t=train[:,1];y=train[:,2]
        if any(int(np.sum((z==j)&(t==k)))<min_arm for j in (0,1) for k in (0,1)):
            return {'status':'REJECTED_TRAINING_FOLD_OVERLAP'}
        ps=np.empty(2);m=np.empty((2,2))
        for j in (0,1):
            group=train[z==j] if propensity_spec=='stratified' else train
            ps[j]=(float(group[:,1].sum())+0.5)/(len(group)+1)
            for k in (0,1):
                arm=train[(z==j)&(t==k)] if outcome_spec=='stratified' else train[t==k]
                m[j,k]=(float(arm[:,2].sum())+0.5)/(len(arm)+1)
        if not np.all((ps>.05)&(ps<.95)):
            return {'status':'REJECTED_EXTREME_PROPENSITY'}
        ix=np.flatnonzero(fold==holdout)
        zz=test[:,0];tt=test[:,1];yy=test[:,2]
        ee=ps[zz];m0=m[zz,0];m1=m[zz,1]
        scores[ix]=m1-m0+tt*(yy-m1)/ee-(1-tt)*(yy-m0)/(1-ee)
    effect=float(scores.mean())
    se=float(np.std(scores,ddof=1)/math.sqrt(n))
    crit=float(norm.ppf((1+confidence)/2))
    return {'status':'COMPUTED','estimate':effect,'standard_error':se,
            'lower':float(max(-1,effect-crit*se)),'upper':float(min(1,effect+crit*se)),
            'propensity_spec':propensity_spec,'outcome_spec':outcome_spec,
            'double_robustness_is_asymptotic':True,'crossfit_folds':2}


def _interval(estimate,low,high):
    if not all(map(math.isfinite,(estimate,low,high))) or low>high:
        return {'status':'REJECTED_NONFINITE_OR_INVERTED_INTERVAL'}
    return {'status':'COMPUTED','estimate':float(estimate),'lower':float(low),
            'upper':float(high),'width':float(high-low)}


def one_case(scenario,seed,n,*,resamples=399,confidence=.95):
    rows,fx=g7.make_fixture(scenario,seed,n)
    w=g8.stratified_wald_interval(rows,confidence,include_covariate_mix_variation=True)
    boot=bootstrap_intervals(rows,seed=seed^0x9E3779B9,resamples=resamples,confidence=confidence)
    dr=aipw_crossfit(rows,seed=seed^0xC2B2AE35,confidence=confidence)
    point={}
    point['G8_POPULATION_MIX_WALD']=(_interval(w['ate'],w['lower'],w['upper'])
           if w['status']=='APPROXIMATE_INTERVAL_COMPUTED' else {'status':w['status']})
    for method in ('PAIRS_BOOT_PERCENTILE','PAIRS_BOOT_BASIC','PAIRS_BOOT_BCA','PAIRS_BOOT_NORMAL'):
        point[method]=(_interval(boot['estimate'],**{'low':boot['methods'][method]['lower'],
                'high':boot['methods'][method]['upper']}) if boot['status']=='COMPUTED'
                else {'status':boot['status']})
    point['AIPW_CROSSFIT_IF_WALD']=(_interval(dr['estimate'],dr['lower'],dr['upper'])
          if dr['status']=='COMPUTED' else {'status':dr['status']})
    supported=scenario not in ('hidden_confounder','no_overlap')
    for m,v in point.items():
        if v['status']=='COMPUTED':
            v['contains_synthetic_oracle_descriptive']=bool(v['lower']<=fx['oracle_ate']<=v['upper'])
            v['causal_calibration_eligible']=bool(supported)
    partial=g8.manski_binary_bounds(rows,confidence)
    return {'fixture':fx,'methods':point,
            'bootstrap_status':boot['status'],'aipw_status':dr['status'],
            'identification_assumptions_supported_by_generator':supported,
            'partial_identification_envelope_contains_truth':bool(partial['population_coverage_envelope_lower']<=fx['oracle_ate']<=partial['population_coverage_envelope_upper']),
            'warning':'CAUSAL_IDENTIFICATION_NOT_PROVEN_UNDER_ANY_METHOD'}


def wilson_interval(successes, trials, confidence=.95):
    if trials<=0: return None
    z=float(norm.ppf((1+confidence)/2));p=successes/trials
    den=1+z*z/trials
    center=(p+z*z/(2*trials))/den
    half=z*math.sqrt(p*(1-p)/trials+z*z/(4*trials*trials))/den
    return [max(0,center-half),min(1,center+half)]


def aggregate(records,confidence=.95):
    summary={}
    for key in sorted({(r['fixture']['scenario'],r['fixture']['n']) for r in records}):
        selected=[r for r in records if (r['fixture']['scenario'],r['fixture']['n'])==key]
        by_method={}
        for m in ('G8_POPULATION_MIX_WALD','PAIRS_BOOT_PERCENTILE','PAIRS_BOOT_BASIC',
                  'PAIRS_BOOT_BCA','PAIRS_BOOT_NORMAL','AIPW_CROSSFIT_IF_WALD'):
            usable=[r['methods'][m] for r in selected if r['methods'][m]['status']=='COMPUTED']
            eligible=key[0] not in ('hidden_confounder','no_overlap')
            covered=sum(bool(r['contains_synthetic_oracle_descriptive']) for r in usable)
            by_method[m]={'attempts':len(selected),'computed':len(usable),
                'status_counts':dict(sorted({s:sum(r['methods'][m]['status']==s for r in selected)
                       for s in set(r['methods'][m]['status'] for r in selected)}.items())),
                'causal_coverage_eligible':eligible,
                'empirical_coverage':(covered/len(usable) if eligible and usable else None),
                'coverage_wilson_95':(wilson_interval(covered,len(usable)) if eligible and usable else None),
                'mean_interval_width':(sum(r['width'] for r in usable)/len(usable) if usable else None),
                'point_bias_descriptive':(sum(r['estimate']-selected_i['fixture']['oracle_ate']
                      for r,selected_i in ((q['methods'][m],q) for q in selected if q['methods'][m]['status']=='COMPUTED'))/len(usable) if usable else None),
            }
        summary[f'{key[0]}@{key[1]}']=by_method
    return summary


def conduct(*,seeds=tuple(range(2001,2101)),sizes=(300,900),resamples=399,confidence=.95):
    if not 1<=len(seeds)<=200 or len(seeds)!=len(set(seeds)) or any(not isinstance(s,int) or not 0<=s<=2**32-1 for s in seeds):
        raise ValueError('INVALID_SEED_GRID')
    if not 1<=len(sizes)<=3 or len(sizes)!=len(set(sizes)) or any(not 50<=n<=g7.MAX_N for n in sizes):
        raise ValueError('INVALID_SAMPLE_SIZE_GRID')
    if not 99<=resamples<=MAX_RESAMPLES or not .5<=confidence<1:raise ValueError('INVALID_DESIGN')
    records=[one_case(s,seed,n,resamples=resamples,confidence=confidence)
             for n in sizes for s in SCENARIOS for seed in seeds]
    return {'phase':PHASE,'kind':'BOUNDED_OFFLINE_RESEARCH_NOT_MODEL_FACING',
            'design':{'seeds':list(seeds),'sizes':list(sizes),'resamples':resamples,
                      'confidence':confidence,'scenarios':list(SCENARIOS),
                      'unit_of_resampling':'WHOLE_IID_OBSERVATION_TRIPLES',
                      'no_overlap_policy':'FAIL_CLOSED_NO_SILENT_BOOTSTRAP_DROPS'},
            'results':records,'summary':aggregate(records,confidence),
            'claims':{'causal_identification_proven':False,'host_authorized':False,
                      'windows_security_attested':False,'research_only':True,
                      'uncertainty_calibration_is_empirical_not_guarantee':True},
            'limitations':['Cross-fitting uses binary Z saturated or pooled nuisance models only',
                 'AIPW influence-function uncertainty is asymptotic; folds may be unstable',
                 'Bootstrap intervals can under-cover small-sample, rare-event or weak-overlap cases',
                 'Hidden confounding violates identification for all tested estimators',
                 'Whole-row bootstrap assumes independent observations; not valid for time-series clusters',
                 'No external package authentication, Lu host authorization, or Windows sandbox']}


def verify_report(report):
    try:
        d=report['design']
        if report['phase']!=PHASE or report['kind']!='BOUNDED_OFFLINE_RESEARCH_NOT_MODEL_FACING' or report['claims']!={
            'causal_identification_proven':False,'host_authorized':False,
            'windows_security_attested':False,'research_only':True,
            'uncertainty_calibration_is_empirical_not_guarantee':True}:return False
        if (d['scenarios']!=list(SCENARIOS) or d.get('unit_of_resampling')!='WHOLE_IID_OBSERVATION_TRIPLES' or d.get('no_overlap_policy')!='FAIL_CLOSED_NO_SILENT_BOOTSTRAP_DROPS' or len(set(d['seeds']))!=len(d['seeds']) or len(set(d['sizes']))!=len(d['sizes'])):return False
        if not (1<=len(d['seeds'])<=200 and 1<=len(d['sizes'])<=3 and 99<=d['resamples']<=MAX_RESAMPLES):return False
        if len(report['results'])!=len(d['seeds'])*len(d['sizes'])*len(SCENARIOS):return False
        # Independent of ordering: unique fixture keys, exact deterministic method replay.
        matched=set()
        for row in report['results']:
            f=row['fixture'];key=f['scenario'],f['seed'],f['n']
            if key in matched or f['seed'] not in d['seeds'] or f['n'] not in d['sizes'] or f['scenario'] not in SCENARIOS:return False
            matched.add(key)
            if row!=one_case(*key,resamples=d['resamples'],confidence=d['confidence']):return False
        if report['summary']!=aggregate(report['results'],d['confidence']):return False
        return True
    except (KeyError,ValueError,TypeError,OverflowError,IndexError,ZeroDivisionError):return False


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--seeds',type=int,default=100)
    p.add_argument('--sizes',nargs='+',type=int,default=[300,900])
    p.add_argument('--resamples',type=int,default=399)
    args=p.parse_args()
    report=conduct(seeds=tuple(range(2001,2001+args.seeds)),sizes=tuple(args.sizes),resamples=args.resamples)
    if not verify_report(report):raise RuntimeError('G9_REPLAY_FAILED')
    report['numerical_replay_verified']=True
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,sort_keys=True,allow_nan=False,indent=2)+'\n')
    print(json.dumps({'cases':len(report['results']),'summary':report['summary']},indent=2))

if __name__=='__main__':main()
