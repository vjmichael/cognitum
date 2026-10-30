"""C14 G11: independent synthetic holdout + deliberate covariate-shift evaluation.

G10 policy and its G9 calibration archive are frozen. Never train, calibrate,
or select a method using this holdout. This tool is offline and research-only;
not model-facing, causal proof, clinical/safety advice or Lu authorization.
"""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
import numpy as np
from scipy.stats import binomtest
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g8_uncertainty as g8
from tools import run_c14_p4e_g9_interval_comparison as g9
from cognitum import causal_interval_comparison as g9_wire
from cognitum import causal_assurance_policy as g10
from cognitum.proto import causal_interval_comparison_pb2 as gp
from cognitum.proto import causal_assurance_policy_pb2 as ap

ROOT=Path(__file__).resolve().parents[1]
PHASE='C14 P4E G11'
HOLDOUT_SEEDS=tuple(range(51001,51201))
SHIFT_SEEDS=tuple(range(61001,61101))
SIZES=(300,900)
RESAMPLES=399
CONFIDENCE=.95
SHIFT_Z_PROB=.80
METHODS=g9.METHODS
SHIFT_SCENARIOS=('observed_homogeneous','observed_heterogeneous','null_effect')


def shifted_fixture(scenario,seed,n,p_z=SHIFT_Z_PROB):
    """New DGP, not a relabeled/reweighted G7 run: same mechanism, new Z mix.

    Oracle ATE for heterogeneous treatment is explicitly transported to P(Z=1)=p_z.
    Time-series/bootstrap or latent-confounder validity is NOT implied.
    """
    if scenario not in SHIFT_SCENARIOS or seed not in SHIFT_SEEDS or n not in SIZES or p_z!=SHIFT_Z_PROB:
        raise ValueError('OUT_OF_SCOPE_SHIFT_DESIGN')
    r=np.random.default_rng(seed)
    z=r.binomial(1,p_z,n)
    if scenario=='observed_homogeneous':
        pt=.19+.48*z;py0=.12+.18*z;tau0=tau1=.24
    elif scenario=='observed_heterogeneous':
        pt=.16+.53*z;py0=.10+.17*z;tau0,tau1=.12,.47
    else:
        pt=.22+.41*z;py0=.14+.22*z;tau0=tau1=0.
    t=r.binomial(1,pt);y=r.binomial(1,py0+np.where(z==0,tau0,tau1)*t)
    rows=np.column_stack((z,t,y)).astype('int64')
    oracle=(1-p_z)*tau0+p_z*tau1
    return rows,{'scenario':scenario,'seed':seed,'n':n,'oracle_ate':oracle,
        'oracle_cate_z0':tau0,'oracle_cate_z1':tau1,
        'z_probability':p_z,'generator':'INDEPENDENT_SHIFTED_COVARIATE_MIX',
        'observations_sha256':hashlib.sha256(rows.tobytes()).hexdigest(),
        'not_transportable_from_G9_without_validation':True}


def shifted_one_case(scenario,seed,n):
    rows,fx=shifted_fixture(scenario,seed,n)
    w=g8.stratified_wald_interval(rows,CONFIDENCE,include_covariate_mix_variation=True)
    boot=g9.bootstrap_intervals(rows,seed=seed^0x9e3779b9,resamples=RESAMPLES,confidence=CONFIDENCE)
    dr=g9.aipw_crossfit(rows,seed=seed^0xc2b2ae35,confidence=CONFIDENCE)
    point={}
    point[METHODS[0]]=(g9._interval(w['ate'],w['lower'],w['upper'])
                     if w['status']=='APPROXIMATE_INTERVAL_COMPUTED' else {'status':w['status']})
    for method in METHODS[1:5]:
        point[method]=(g9._interval(boot['estimate'],boot['methods'][method]['lower'],boot['methods'][method]['upper'])
            if boot['status']=='COMPUTED' else {'status':boot['status']})
    point[METHODS[5]]=(g9._interval(dr['estimate'],dr['lower'],dr['upper'])
        if dr['status']=='COMPUTED' else {'status':dr['status']})
    for value in point.values():
        if value['status']=='COMPUTED':
            value['contains_synthetic_oracle_descriptive']=bool(value['lower']<=fx['oracle_ate']<=value['upper'])
            value['causal_calibration_eligible']=True # internally to oracle, never G10 domain-applicable
    return {'fixture':fx,'methods':point,'identification_assumptions_supported_by_generator':True,
        'not_G9_calibration_domain':True,
        'warning':'SHIFTED_GENERATOR_DO_NOT_TRANSPORT_G9_CALIBRATION'}


def frozen_g10_advisory(scenario,n,method):
    exp=gp.IntervalComparisonRequest(schema_version=1,trace_id='g11-prelocked-g10',
        scenario=scenario,seed=1001,sample_size=n,bootstrap_resamples=RESAMPLES,confidence=CONFIDENCE)
    candidate,receipt=g9_wire.calculate(exp)
    req=ap.CausalAssuranceRequest(schema_version=1,trace_id='g11-prelocked-g10',experiment=exp,
        candidate=candidate,calculation_receipt=receipt,selected_method=method)
    result,pr=g10.calculate(req)
    if not g10.verify(req,result,pr):raise RuntimeError('G10_FROZEN_REPLAY_FAILURE')
    return ap.CausalAssuranceDisposition.Name(result.disposition)


def _decision(method_summary,base_disposition,eligible,domain='FROZEN_SYNTHETIC_HOLDOUT'):
    # Predeclared gating rules frozen before inspecting G11 results.
    if domain!='FROZEN_SYNTHETIC_HOLDOUT':return 'ABSTAIN_DISTRIBUTION_SHIFT'
    if not eligible:return 'ABSTAIN_IDENTIFICATION'
    if base_disposition!='CAUSAL_ASSURANCE_DESCRIBE_SYNTHETIC_ONLY':return 'ABSTAIN_G10_POLICY'
    m=method_summary
    if (m['computed']<g10.MIN_COMPLETED or
        m['computed']/m['attempts']<g10.MIN_COMPLETION_FRACTION or
        m['empirical_coverage'] is None):return 'ABSTAIN_HOLDOUT_INSUFFICIENT'
    if m['empirical_coverage']<CONFIDENCE-g10.CALIBRATION_TOLERANCE:
        return 'ABSTAIN_HOLDOUT_UNDERCOVERAGE'
    return 'DESCRIBE_INDEPENDENT_SYNTHETIC_ONLY'


def drift_diagnostics(holdout_seeds,shift_seeds):
    """Fixed known-generator covariate-shift diagnostic, not a universal OOD detector.

    Exact binomial null H0: P(Z=1)=0.5, two-sided alpha=0.01.
    A failed rejection DOES NOT certify the training distribution is unchanged.
    """
    result={}
    for n in SIZES:
        null_hits=0;shift_hits=0;null_freq=[];shift_freq=[]
        for seed in holdout_seeds:
            rows,_=g7.make_fixture('observed_heterogeneous',seed,n)
            z=int(rows[:,0].sum());null_freq.append(z/n)
            null_hits+=int(binomtest(z,n,.5).pvalue<.01)
        for seed in shift_seeds:
            rows,_=shifted_fixture('observed_heterogeneous',seed,n)
            z=int(rows[:,0].sum());shift_freq.append(z/n)
            shift_hits+=int(binomtest(z,n,.5).pvalue<.01)
        result[str(n)]={'nominal_alpha':.01,'tested_statistic':'EXACT_BINOMIAL_Z_MIX',
            'null_fixture_trials':len(holdout_seeds),'shift_fixture_trials':len(shift_seeds),
            'false_alarms_on_known_null':null_hits,'detections_on_known_shift':shift_hits,
            'null_mean_z':float(np.mean(null_freq)),'shift_mean_z':float(np.mean(shift_freq)),
            'not_a_proof_of_no_shift_when_test_is_nonsignificant':True}
    return result


def conduct(*,holdout_seeds=HOLDOUT_SEEDS,shift_seeds=SHIFT_SEEDS):
    if (not holdout_seeds or not shift_seeds or not set(holdout_seeds).isdisjoint(set(shift_seeds))
        or not set(holdout_seeds).isdisjoint(set(range(2001,2201)))
        or not set(shift_seeds).isdisjoint(set(range(2001,2201)))
        or any(s not in HOLDOUT_SEEDS for s in holdout_seeds)
        or any(s not in SHIFT_SEEDS for s in shift_seeds)):
        raise ValueError('HOLDOUT_SEED_PARTITION_VIOLATION')
    report=g9.conduct(seeds=tuple(holdout_seeds),sizes=SIZES,resamples=RESAMPLES,confidence=CONFIDENCE)
    holdout={}
    for key,methods in report['summary'].items():
        scenario,n=key.split('@');n=int(n)
        holdout[key]={}
        for method,values in methods.items():
            baseline=frozen_g10_advisory(scenario,n,method)
            holdout[key][method]={**values,'G10_frozen_disposition':baseline,
                'G11_disposition':_decision(values,baseline,values['causal_coverage_eligible'])}
    shifted=[shifted_one_case(s,seed,n) for n in SIZES for s in SHIFT_SCENARIOS for seed in shift_seeds]
    shifted_summary=g9.aggregate(shifted,CONFIDENCE)
    for methods in shifted_summary.values():
        for vals in methods.values():
            vals['G11_disposition']='ABSTAIN_DISTRIBUTION_SHIFT'
            vals['G9_calibration_applicable']=False
    return {'phase':PHASE,'status':'OFFLINE_SYNTHETIC_RESEARCH_ONLY',
      'design':{'holdout_seeds':list(holdout_seeds),'shift_seeds':list(shift_seeds),
        'g9_training_calibration_seeds':list(range(2001,2201)),
        'sample_sizes':list(SIZES),'resamples':RESAMPLES,'confidence':CONFIDENCE,
        'heldout_scenarios':list(g7.SCENARIOS),'shift_scenarios':list(SHIFT_SCENARIOS),
        'shift_P_z1':SHIFT_Z_PROB,'method_selection':'FROZEN_G10_NO_TUNING',
        'advisory_minimum_coverage':CONFIDENCE-g10.CALIBRATION_TOLERANCE,
        'advisory_minimum_completed':g10.MIN_COMPLETED,
        'advisory_minimum_completion_fraction':g10.MIN_COMPLETION_FRACTION},
      'frozen_G10_policy_sha256':hashlib.sha256((ROOT/'cognitum/causal_assurance_policy.py').read_bytes()).hexdigest(),
      'frozen_G9_calibration_sha256':g10.G9_EVIDENCE_SHA256,
      'holdout_summary':holdout,'shifted_summary':shifted_summary,
      'drift_diagnostics':drift_diagnostics(holdout_seeds,shift_seeds),
      'counts':{'holdout_datasets':len(report['results']),'shifted_datasets':len(shifted)},
      'claims':{'causal_identification_proven':False,'Lu_host_authorized':False,
        'intervention_authorized':False,'real_world_calibration_certified':False,
        'windows_security_attested':False,'research_only':True},
      'limitations':[
        'G10 frozen thresholds were informed by G9; the new holdout is independent only by generator seeds, not by source family',
        'No data-dependent tuning or best-method selection permitted after reading holdout',
        'Coverage Wilson intervals quantify sampling uncertainty; a passing point estimate is not a coverage guarantee',
        'Shifted fixtures have known population oracles but are outside the G9 calibration domain',
        'A covariate shift may not be evident to a caller; metadata from a model is never trusted as attestation',
        'Known hidden confounding/positivity violations cannot be fixed by interval estimation',
        'No real-world datasets, external authorization, Windows security or release attestation']}


def write_report(path=ROOT/'docs/components/causal/P4E-G11-holdout-evidence.json'):
    result=conduct()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,sort_keys=True,allow_nan=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=write_report()
    print(json.dumps({'counts':result['counts'],
      'decision_counts':{k:sum(v['G11_disposition']==k for methods in result['holdout_summary'].values() for v in methods.values())
        for k in sorted(set(v['G11_disposition'] for methods in result['holdout_summary'].values() for v in methods.values()))}},indent=2))
