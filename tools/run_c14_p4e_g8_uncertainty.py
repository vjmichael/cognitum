"""C14 P4E G8: bounded offline confidence-interval coverage and partial identification.

RESEARCH ONLY. No host authorization, model-facing execution or causal proof.
Repeated-sample frequentist intervals assume iid observed samples, observed
sufficient adjustment Z, overlap, and correct propensity/outcome structure.
Manski bounds instead require binary treatment/outcomes, consistency and iid
sampling, not unconfoundedness or treatment overlap. The empirical identified
set is NOT a confidence interval; a separate Hoeffding envelope covers finite-
sample sampling variability and is deliberately conservative.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from tools import run_c14_p4e_g7_study as g7

PHASE='C14 P4E G8'
SCENARIOS=g7.SCENARIOS
DEFAULT_SEEDS=tuple(range(1001,1101))
DESIGN_KIND='SYNTHETIC_OFFLINE_METHOD_EVALUATION_NOT_PRODUCTION'
Z_95=1.959963984540054


def require_binary(rows):
    import numpy as np
    x=np.asarray(rows)
    if x.ndim!=2 or x.shape[1]!=3 or x.shape[0]<2 or not np.isin(x,[0,1]).all():
        raise ValueError('BINARY_Z_T_Y_REQUIRED')
    return x


def manski_binary_bounds(rows, confidence=.95):
    """Empirical sharp ATE identification interval + conservative population envelope.

    Width exactly one for binary Y/T with no causal identification assumptions.
    Hoeffding simultaneous envelope (1-alpha) uses one-sided bounds on the two
    bounded [0,1] sample means representing -L and U; iid rows are essential.
    """
    x=require_binary(rows)
    if not 0.5 <= confidence < 1.0: raise ValueError('CONFIDENCE_OUT_OF_RANGE')
    n=len(x)
    t=x[:,1]; y=x[:,2]
    n11=int(((t==1)&(y==1)).sum()); n01=int(((t==0)&(y==1)).sum()); nt1=int((t==1).sum())
    # L = P(Y=1,T=1)-P(Y=1,T=0)-P(T=1)
    # U = P(Y=1,T=1)-P(Y=1,T=0)+P(T=0)
    lower=(n11-n01-nt1)/n
    upper=(n11-n01+(n-nt1))/n
    eps=math.sqrt(math.log(2/(1-confidence))/(2*n))
    return {
        'status':'PARTIALLY_IDENTIFIED_BINARY_OUTCOME',
        'n':n,'joint_count_y1_t1':n11,'joint_count_y1_t0':n01,'treated_count':nt1,
        'identified_set_plugin_lower':lower,'identified_set_plugin_upper':upper,
        'identified_set_width':upper-lower,
        'population_coverage_envelope_lower':max(-1.,lower-eps),
        'population_coverage_envelope_upper':min(1.,upper+eps),
        'envelope_nominal_confidence':confidence,
        'envelope_hoeffding_epsilon':eps,
        'causal_point_identified':False,
        'assumptions':'BINARY_POTENTIAL_OUTCOMES_CONSISTENCY_IID_SAMPLING; NO_UNCONFOUNDEDNESS',
        'sampling_uncertainty_separate_from_identification_uncertainty':True,
    }


def stratified_wald_interval(rows, confidence=.95, min_arm=5, *, include_covariate_mix_variation=False):
    """Approximate conditional-on-Z-mix adjusted risk-difference interval.

    Variance treats empirical Z proportions as fixed; intervals are not a proof
    of identifying assumptions, may have finite-sample undercoverage, and need
    independent calibration. Wald is not certified for tiny arm cell counts.
    """
    x=require_binary(rows)
    if not 0.5<=confidence<1.0 or min_arm<5:raise ValueError('INVALID_INTERVAL_PARAMETERS')
    reference=g7.exact_stratified(x,min_arm=min_arm)
    if reference['status']!='EMPIRICAL_CONTRAST_COMPUTED':
        return {'status':'REJECTED_INSUFFICIENT_POSITIVITY','confidence':confidence,
                'reason':'MINIMUM_TREATMENT_ARM_CELL_COUNT_NOT_MET',
                'assumptions_verified':False}
    from scipy.stats import norm
    z=float(norm.ppf((1+confidence)/2))
    n=len(x)
    variance=0.
    cell_counts={}
    strata_effects={};strata_weights={}
    for value in (0,1):
        subset=x[x[:,0]==value]
        w=len(subset)/n
        counts=[]; probs=[]
        for treatment in (0,1):
            y=subset[subset[:,1]==treatment,2]
            if len(y)<min_arm:raise AssertionError('OVERLAP_RECHECK_FAILED')
            p=float(y.mean()); counts.append(len(y));probs.append(p)
            variance+=w*w*p*(1-p)/len(y)
        cell_counts[str(value)]=counts
        strata_effects[value]=probs[1]-probs[0]
        strata_weights[value]=w
    effect=reference["ate"]
    between=sum(w*(strata_effects[z]-effect)**2 for z,w in strata_weights.items())/n
    if include_covariate_mix_variation:
        variance+=between
    se=math.sqrt(max(variance,0.))
    # Clipping to parameter's support does not weaken coverage of bounded ATE.
    lo=max(-1.,effect-z*se);hi=min(1.,effect+z*se)
    return {'status':'APPROXIMATE_INTERVAL_COMPUTED','ate':effect,
            'standard_error':se,'lower':lo,'upper':hi,'confidence':confidence,
            'method':'STRATIFIED_BINOMIAL_PLUGIN_WALD_' + ('POPULATION_Z_MIX_VARIATION' if include_covariate_mix_variation else 'CONDITIONAL_Z_MIX'),
            'between_strata_variance_component':between if include_covariate_mix_variation else 0.,
            'cell_counts':cell_counts,
            'assumptions_verified':False,
            'estimand':'POPULATION_ATE_UNDER_VALID_OBSERVED_BACKDOOR_AND_OVERLAP',
            'warning':'ASSUMPTION_DEPENDENT_APPROXIMATION_NOT_CAUSAL_CERTIFICATE'}


def one_case(scenario,seed,n,confidence=.95):
    data,fx=g7.make_fixture(scenario,seed,n)
    bounds=manski_binary_bounds(data,confidence)
    interval=stratified_wald_interval(data,confidence)
    population_interval=stratified_wald_interval(data,confidence,include_covariate_mix_variation=True)
    true_ate=fx['oracle_ate']
    identifying_ok=scenario not in ('hidden_confounder','no_overlap')
    interval_covered=(interval['lower']<=true_ate<=interval['upper']) if interval['status']=='APPROXIMATE_INTERVAL_COMPUTED' else None
    population_covered=(population_interval['lower']<=true_ate<=population_interval['upper']) if population_interval['status']=='APPROXIMATE_INTERVAL_COMPUTED' else None
    return {'fixture':fx, 'bounds':bounds,
            'point_interval':interval, 'population_point_interval':population_interval,
            'population_point_interval_contains_oracle':population_covered,
            'population_ate_in_plugin_identified_set':bounds['identified_set_plugin_lower']<=true_ate<=bounds['identified_set_plugin_upper'],
            'population_ate_in_conservative_sampling_envelope':bounds['population_coverage_envelope_lower']<=true_ate<=bounds['population_coverage_envelope_upper'],
            'point_interval_contains_oracle':interval_covered,
            'identification_assumptions_supported_by_generator':identifying_ok,
            'calibration_eligible':identifying_ok and interval_covered is not None,
            'causal_claim_verified':False,
            'warning':('ASSUMPTION_BREACH_POINT_COVERAGE_DESCRIPTIVE_ONLY' if scenario=='hidden_confounder' else
                       'NO_OVERLAP_NO_ADJUSTED_POINT_INTERVAL' if scenario=='no_overlap' else
                       'SYNTHETIC_CLEAN_ASSUMPTIONS_ONLY')}


def aggregate(rows,confidence):
    result={}
    for scenario in SCENARIOS:
        subset=[r for r in rows if r['fixture']['scenario']==scenario]
        eligible=[r for r in subset if r['calibration_eligible']]
        observed_point_coverage=(sum(bool(r['point_interval_contains_oracle']) for r in eligible)/len(eligible) if eligible else None)
        ci_width=(sum(r['point_interval']['upper']-r['point_interval']['lower'] for r in eligible)/len(eligible) if eligible else None)
        pop_covered=(sum(r['population_point_interval_contains_oracle'] for r in eligible)/len(eligible) if eligible else None)
        pop_width=(sum(r['population_point_interval']['upper']-r['population_point_interval']['lower'] for r in eligible)/len(eligible) if eligible else None)
        wrong_assumption_cases=sum(r['warning']=='ASSUMPTION_BREACH_POINT_COVERAGE_DESCRIPTIVE_ONLY' for r in subset)
        result[scenario]={
            'cases':len(subset),'calibration_eligible_cases':len(eligible),
            'empirical_point_interval_coverage_on_eligible_cases':observed_point_coverage,
            'mean_eligible_point_interval_width':ci_width,
            'population_mix_adjusted_interval_coverage':pop_covered,
            'population_mix_adjusted_mean_width':pop_width,
            'conservative_population_envelope_coverage':sum(r['population_ate_in_conservative_sampling_envelope'] for r in subset)/len(subset),
            'plugin_identified_set_oracle_containment_descriptive':sum(r['population_ate_in_plugin_identified_set'] for r in subset)/len(subset),
            'point_coverage_with_invalid_assumptions_is_not_calibration':bool(wrong_assumption_cases),
        }
    return result


def conduct(seeds=DEFAULT_SEEDS, sample_sizes=(300,900), confidence=.95):
    if not 1<=len(seeds)<=250 or len(set(seeds))!=len(seeds) or any(not isinstance(s,int) or s<0 or s>2**32-1 for s in seeds):
        raise ValueError('INVALID_SEED_GRID')
    if not sample_sizes or len(sample_sizes)>3 or len(set(sample_sizes))!=len(sample_sizes) or any(n<50 or n>g7.MAX_N for n in sample_sizes):
        raise ValueError('INVALID_SAMPLE_SIZE_GRID')
    if not .5<=confidence<1:raise ValueError('CONFIDENCE_OUT_OF_RANGE')
    summaries={};records=[]
    for n in sample_sizes:
        case_rows=[one_case(s,seed,n,confidence) for s in SCENARIOS for seed in seeds]
        summaries[str(n)]=aggregate(case_rows,confidence)
        records.extend(case_rows)
    return {'phase':PHASE,'kind':DESIGN_KIND,
            'design':{'seeds':list(seeds),'sample_sizes':list(sample_sizes),'scenarios':list(SCENARIOS),
                      'nominal_confidence':confidence,
                      'pre_registered_policy':'OMIT HIDDEN CONFOUNDING AND NO-OVERLAP FROM POINT-COVERAGE CALIBRATION; BOUNDS FOR ALL',
                      'seeded_data_generator':'G7 EXACT SOURCE'},
            'results':records,'summary':summaries,
            'claims':{'statistical_interval_coverage_studied':True,'causal_identification_proven':False,
                      'independent_host_execution_attested':False,'windows_security_certified':False,
                      'instrumental_variable_bounds_implemented':False},
            'limitations':['Stratified Wald plug-in, not universally valid confidence interval',
                           'Synthetic generator only; independence and ground-truth assumptions supplied by fixture',
                           'Bounds are worst-case for binary outcomes and do not identify a point',
                           'Point bounds are plug-in identified sets not population confidence intervals',
                           'Hoeffding envelope requires iid sampling, may be wide',
                           'No real-model benchmark, host admission or Windows containment']}


def verify_report(report):
    """Recreate every fixture and all numerical statistics; NOT third-party authentication."""
    try:
        if report['phase']!=PHASE or report['kind']!=DESIGN_KIND or report['claims']!={
                'statistical_interval_coverage_studied':True,'causal_identification_proven':False,
                'independent_host_execution_attested':False,'windows_security_certified':False,
                'instrumental_variable_bounds_implemented':False}:return False
        d=report['design'];seeds=d['seeds'];sizes=d['sample_sizes'];c=d['nominal_confidence']
        if len(set(seeds))!=len(seeds) or len(set(sizes))!=len(sizes) or not 1<=len(seeds)<=250 or not 1<=len(sizes)<=3 or not .5<=c<1:return False
        if d['scenarios']!=list(SCENARIOS) or len(report['results'])!=len(seeds)*len(sizes)*len(SCENARIOS):return False
        pairs=set()
        groups={str(n):[] for n in sizes}
        for row in report['results']:
            fx=row['fixture'];s=fx['scenario'];seed=fx['seed'];n=fx['n']
            key=(s,seed,n)
            if s not in SCENARIOS or seed not in seeds or n not in sizes or key in pairs:return False
            pairs.add(key)
            expected=one_case(s,seed,n,c)
            if row!=expected:return False
            groups[str(n)].append(row)
        if report['summary']!={k:aggregate(v,c) for k,v in groups.items()}:return False
        return True
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,ZeroDivisionError,OverflowError):
        return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--seeds',type=int,default=100)
    parser.add_argument('--sizes',type=int,nargs='+',default=[300,900])
    args=parser.parse_args()
    if not 1<=args.seeds<=250:parser.error('seeds 1..250')
    report=conduct(tuple(1001+i for i in range(args.seeds)),tuple(args.sizes))
    if not verify_report(report):raise RuntimeError('G8_REPLAY_FAILED')
    report['numerical_replay_verified']=True
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'phase':PHASE,'cases':len(report['results']),'summary':report['summary']},indent=2))

if __name__=='__main__':main()
