"""C14 P4E G7 -- bounded offline *research-only* multi-fixture causal study.

The user-provided DoWhy main source is an unauthenticated release snapshot.
Runs *real* DoWhy and EconML in a researcher-provisioned environment. No Lu host
or OS sandbox admission is provided here. Do not expose to LLM-selected paths.
Known simulator interventions give a ground-truth ATE for each fixture;
observational estimators do not certify that their supplied graph is true.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import time

MAX_N = 3000
ALLOWED_SEEDS = (101, 202, 303, 404, 505)
SCENARIOS = ('observed_homogeneous', 'observed_heterogeneous', 'hidden_confounder',
             'null_effect', 'no_overlap')
SOURCE_ASSURANCE = 'SYNTHETIC_ORACLE_RESEARCH_NOT_CAUSAL_CERTIFICATE'


def make_fixture(scenario: str, seed: int, n: int):
    if scenario not in SCENARIOS or not 1 <= n <= MAX_N or seed < 0 or seed > 2**32 - 1:
        raise ValueError('BOUNDED_FIXTURE_PARAMETERS_REQUIRED')
    import numpy as np
    r = np.random.default_rng(seed)
    z = r.binomial(1, .5, n)
    u = r.binomial(1, .5, n)  # generator-only latent; never included in observation rows
    if scenario == 'observed_homogeneous':
        pt = .19 + .48*z
        py0 = .12 + .18*z
        tau0, tau1 = .24, .24
    elif scenario == 'observed_heterogeneous':
        pt = .16 + .53*z
        py0 = .10 + .17*z
        tau0, tau1 = .12, .47
    elif scenario == 'hidden_confounder':
        pt = .12 + .22*z + .43*u
        py0 = .08 + .12*z + .36*u
        tau0, tau1 = .20, .20
    elif scenario == 'null_effect':
        pt = .22 + .41*z
        py0 = .14 + .22*z
        tau0, tau1 = 0., 0.
    else:
        pt = z.astype(float)  # deterministic assignment => adjustment positivity fails
        py0 = .11 + .21*z
        tau0, tau1 = .18, .18
    t = r.binomial(1, pt)
    y = r.binomial(1, py0 + np.where(z == 0, tau0, tau1)*t)
    observations = np.column_stack((z,t,y)).astype('int64')
    assert observations.shape == (n,3)
    # Analytic interventional expectation over Bernoulli Z and latent U priors;
    # z/u are independent fair coins by construction.
    truth_ate = (tau0 + tau1) / 2
    digest = hashlib.sha256(observations.tobytes() + scenario.encode() +
                            seed.to_bytes(8,'big') + n.to_bytes(8,'big')).hexdigest()
    return observations, {
        'scenario': scenario, 'seed': seed, 'n': n,
        'observations_sha256': digest, 'oracle_ate': truth_ate,
        'oracle_cate_z0': tau0, 'oracle_cate_z1': tau1,
        'unobserved_common_cause_in_generator': scenario == 'hidden_confounder',
        'source_of_truth': 'KNOWN_SYNTHETIC_INTERVENTION_EQUATIONS',
        'oracle_does_not_validate_assumed_graph': True,
    }


def exact_stratified(data, min_arm=5):
    """Reuse Cognitum P2A's exact rational standardization and independent algebra."""
    from cognitum import causal_estimation as reference
    buckets = defaultdict(lambda:[[0,0],[0,0]])
    for z,t,y in data:
        arm = buckets[(int(z),)][int(t)]
        arm[0] += 1
        arm[1] += int(y)
    if any(arm[0] < min_arm for pair in buckets.values() for arm in pair):
        return {'status':'REJECTED_INSUFFICIENT_POSITIVITY',
                'observed_arm_counts':{str(k[0]):[v[0][0],v[1][0]] for k,v in buckets.items()}}
    a = reference._effect(buckets,len(data))
    b = reference._independent_effect(buckets,len(data))
    if a != b: raise AssertionError('INDEPENDENT_REFERENCE_DISAGREEMENT')
    return {'status':'EMPIRICAL_CONTRAST_COMPUTED', 'ate':float(a),
            'exact_fraction':str(a),
            'cate_z0':float(Fraction(buckets[(0,)][1][1],buckets[(0,)][1][0])-
                            Fraction(buckets[(0,)][0][1],buckets[(0,)][0][0])),
            'cate_z1':float(Fraction(buckets[(1,)][1][1],buckets[(1,)][1][0])-
                            Fraction(buckets[(1,)][0][1],buckets[(1,)][0][0])),
            'independently_checked':True}


def load_dependencies(source_root:Path):
    root = source_root.resolve(strict=True)
    src = root/'dowhy'/'__init__.py'
    if not src.is_file() or '__version__ = "0.0.0"' not in src.read_text():
        raise ValueError('EXPECTED_UNATTESTED_DOWHY_MAIN_SOURCE_MISSING')
    sys.path.insert(0,str(root))  # explicit researcher source path, not user/model input
    import dowhy
    if dowhy.__version__ != '0.0.0': raise ValueError('UNEXPECTED_DOWHY_SOURCE_VERSION')
    import econml
    from statsmodels.formula.api import ols
    if getattr(econml,'__version__',None) != '0.17.0':
        raise ValueError('ECONML_EXACT_VERSION_NOT_AVAILABLE')
    from dowhy import CausalModel
    from econml.dml import LinearDML
    from sklearn.linear_model import LinearRegression, LogisticRegression
    import numpy as np
    import pandas as pd
    import networkx as nx
    return {'source_root':root,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
            'econml_version':getattr(econml,'__version__','unknown'),
            'CausalModel':CausalModel,'LinearDML':LinearDML,
            'LinearRegression':LinearRegression,'LogisticRegression':LogisticRegression,
            'np':np,'pd':pd,'nx':nx,'ols':ols}


def do_why_regression(data, libs, *, known_latent=False, placebo_seed=None):
    """Return actual DoWhy identification+estimation, or explicit blocked status."""
    nx, pd = libs['nx'], libs['pd']
    graph = nx.DiGraph()
    for v in ('v0','v1','v2'):
        graph.add_node(v,observed='yes')
    graph.add_edges_from([('v0','v1'),('v0','v2'),('v1','v2')])
    if known_latent:
        graph.add_node('u0', observed='no')
        graph.add_edges_from([('u0','v1'),('u0','v2')])
    df = pd.DataFrame(data,columns=['v0','v1','v2'])
    model = libs['CausalModel'](data=df,treatment='v1',outcome='v2',
                graph='\n'.join(nx.generate_gml(graph)),proceed_when_unidentifiable=False)
    try:
        identified = model.identify_effect(proceed_when_unidentifiable=False)
    except Exception as ex:
        return {'status':'IDENTIFICATION_NOT_ESTABLISHED', 'reason_type':type(ex).__name__}
    adjustment = set(identified.get_backdoor_variables() or [])
    if known_latent:
        # Do not issue an estimate when oracle knows U0 confounds T and Y.
        # Even an estimand object cannot make this hidden variable observable.
        return {'status':'BLOCKED_KNOWN_UNOBSERVED_CONFOUNDER',
                'identified_backdoor_variables':sorted(adjustment)}
    if adjustment != {'v0'}:
        return {'status':'REJECTED_ADJUSTMENT_MISMATCH',
                'identified_backdoor_variables':sorted(adjustment)}
    try:
        estimate = model.estimate_effect(identified,method_name='backdoor.linear_regression',
                    control_value=0,treatment_value=1,target_units='ate',
                    test_significance=False,confidence_intervals=False)
    except Exception as ex:
        return {'status':'ESTIMATION_FAILED','reason_type':type(ex).__name__}
    value = float(estimate.value)
    if not math.isfinite(value):
        return {'status':'NONFINITE_EFFECT'}
    result={'status':'ESTIMATED', 'ate':value,
            'identification':'ASSUMED_OBSERVED_BACKDOOR_GRAPH',
            'method':'backdoor.linear_regression'}
    if placebo_seed is not None:
        # Diagnostic with no claim of identification or no hidden confounding.
        placebo = model.refute_estimate(identified,estimate,
            method_name='placebo_treatment_refuter',placebo_type='permute',
            random_state=int(placebo_seed),num_simulations=10)
        placebo_effect=float(placebo.new_effect)
        if not math.isfinite(placebo_effect): raise ValueError('PLACEBO_NONFINITE')
        result['placebo_permutation_new_effect']=placebo_effect
        result['placebo_assurance']='DIAGNOSTIC_ONLY_NOT_UNCONFOUNDEDNESS_PROOF'
    return result


def econml_dml(data, libs, seed):
    np=libs['np']
    estimator=libs['LinearDML'](model_y=libs['LinearRegression'](),
        model_t=libs['LogisticRegression'](max_iter=600),
        discrete_treatment=True,random_state=int(seed),cv=3)
    z=data[:,0].reshape(-1,1).astype(float)
    try:
        estimator.fit(data[:,2],data[:,1],X=z)
        cate=estimator.effect(np.asarray([[0.],[1.]]))
        ate=float(np.mean(estimator.effect(z)))
        values=[float(c) for c in cate]
    except Exception as ex:
        return {'status':'ESTIMATION_FAILED','reason_type':type(ex).__name__}
    if not all(math.isfinite(v) for v in [ate]+values):
        return {'status':'NONFINITE_EFFECT'}
    return {'status':'ESTIMATED','ate':ate,
            'cate_z0':values[0],'cate_z1':values[1],
            'method':'LinearDML',
            'assumptions':'UNCONFOUNDEDNESS_AND_OVERLAP_NOT_EMPIRICALLY_PROVEN'}



def saturated_interaction_ols(data,libs):
    """Independent explicitly heterogeneous OLS specification (not DoWhy)."""
    df=libs['pd'].DataFrame(data,columns=['v0','v1','v2'])
    fit=libs['ols']('v2 ~ v1 * v0',data=df).fit()
    a=float(fit.params['v1']); b=float(fit.params['v1:v0'])
    effect=float(a + b*float(df['v0'].mean()))
    z0,z1=a,a+b
    if not all(math.isfinite(v) for v in (effect,z0,z1)):
        return {'status':'NONFINITE_EFFECT'}
    return {'status':'ESTIMATED','method':'statsmodels_ols_with_explicit_treatment_by_covariate_interaction',
            'ate':effect,'cate_z0':z0,'cate_z1':z1,
            'assumptions':'DESCRIPTIVE_SATURATED_BINARY_REGRESSION_ASSUMED_GRAPH_NOT_PROVEN'}


def run_one(scenario,seed,n,libs):
    data, oracle = make_fixture(scenario,seed,n)
    reference = exact_stratified(data)
    outcome={'fixture':oracle,'reference':reference,'method_results':{},
             'assumption_flags':[], 'status':'COMPLETE'}
    if scenario=='no_overlap':
        outcome['status']='PRECHECK_REJECTED'
        outcome['assumption_flags']=['POSITIVITY_VIOLATED_BY_GENERATOR']
        outcome['method_results']={'dowhy_assumed_graph':{'status':'NOT_RUN_PRECHECK'},
                                   'econml_assumed_graph':{'status':'NOT_RUN_PRECHECK'},
                                   'statsmodels_interaction':{'status':'NOT_RUN_PRECHECK'}}
        return outcome
    if reference['status']!='EMPIRICAL_CONTRAST_COMPUTED':
        outcome['status']='PRECHECK_REJECTED'
        outcome['method_results']={'dowhy_assumed_graph':{'status':'NOT_RUN_PRECHECK'},
                                   'econml_assumed_graph':{'status':'NOT_RUN_PRECHECK'},
                                   'statsmodels_interaction':{'status':'NOT_RUN_PRECHECK'}}
        return outcome
    if scenario=='hidden_confounder':
        outcome['assumption_flags']=['GROUND_TRUTH_LATENT_CONFOUNDING_OMITTED_FROM_ASSUMED_GRAPH',
                                   'OBSERVED_BACKDOOR_ESTIMATES_NOT_IDENTIFIED_FROM_RECORDED_VARIABLES']
        outcome['method_results']['dowhy_explicit_latent_graph'] = do_why_regression(data,libs,known_latent=True)
    else:
        outcome['assumption_flags']=['GRAPH_IS_SUPPLIED_NOT_EMPIRICALLY_PROVEN']
    outcome['method_results']['dowhy_assumed_graph'] = do_why_regression(
        data,libs,placebo_seed=seed if scenario=='observed_homogeneous' else None)
    outcome['method_results']['econml_assumed_graph'] = econml_dml(data,libs,seed)
    outcome['method_results']['statsmodels_interaction'] = saturated_interaction_ols(data,libs)
    for key,val in outcome['method_results'].items():
        if val['status']!='ESTIMATED': continue
        val['absolute_oracle_ate_error']=abs(val['ate']-oracle['oracle_ate'])
        val['absolute_empirical_reference_difference']=abs(val['ate']-reference['ate'])
        if 'cate_z0' in val:
            val['absolute_oracle_cate_error_z0']=abs(val['cate_z0']-oracle['oracle_cate_z0'])
            val['absolute_oracle_cate_error_z1']=abs(val['cate_z1']-oracle['oracle_cate_z1'])
    outcome['reference']['absolute_oracle_ate_error']=abs(reference['ate']-oracle['oracle_ate'])
    return outcome


def summarize(rows):
    summary={}
    for scenario in SCENARIOS:
        cases=[row for row in rows if row['fixture']['scenario']==scenario]
        entries={}
        for method in ('reference','dowhy_assumed_graph','econml_assumed_graph','statsmodels_interaction'):
            samples=[(r['reference'] if method=='reference' else r['method_results'].get(method,{})) for r in cases]
            valid=[x for x in samples if x.get('status') in ('ESTIMATED','EMPIRICAL_CONTRAST_COMPUTED')]
            vals=[x['absolute_oracle_ate_error'] for x in valid]
            entries[method]={'estimated_count':len(valid),'rejected_or_unavailable_count':len(samples)-len(valid),
                'mean_absolute_error_to_known_oracle':round(sum(vals)/len(vals),7) if vals else None}
        summary[scenario]={'n_cases':len(cases),'methods':entries}
    return summary


def conduct(source_root, seeds=ALLOWED_SEEDS, n=900):
    if len(seeds)<1 or len(seeds)>5 or len(set(seeds))!=len(seeds):
        raise ValueError('INVALID_SEED_GRID')
    libs=load_dependencies(source_root)
    start=time.monotonic()
    rows=[run_one(s,seed,n,libs) for s in SCENARIOS for seed in seeds]
    return {
        'phase':'C14 P4E G7', 'kind':'OFFLINE_DEVELOPMENT_RESEARCH_NOT_PRODUCTION_GATE',
        'design':{'scenarios':list(SCENARIOS),'seeds':list(seeds),'observations_per_case':n,
                  'pre_declared_status_rule':'REJECT MISSING ARM OVERLAP; FLAG KNOWN LATENT CONFOUNDING; NO CAUSAL PROOF',
                  'matched_observations_for_all_methods':True},
        'scientific_backends':{'dowhy_source_version':'0.0.0','dowhy_tag_authenticated':False,
                               'dowhy_init_sha256':libs['source_sha256'],
                               'econml_version':libs['econml_version'],
                               'production_authorization_attested':False},
        'results':rows, 'summary':summarize(rows),
        'limitations':['Source ZIP is not independently authenticated DoWhy v0.14',
                       'Hidden-confounder scenario intentionally violates identifying assumptions',
                       'No causal proof follows from numerical agreement or negative controls',
                       'Small fixed synthetic study is not a reliability/interval-coverage benchmark',
                       'No Windows native isolation, Lu authorization, or model benchmarks'],
        'elapsed_seconds':round(time.monotonic()-start,4),
    }



def verify_study_report(report):
    """Recompute synthetic oracle and numerical summaries without third-party libraries.

    Verifies provenance and mathematical self-consistency, not a library source
    signature, authenticated host execution, or empirical causal assumptions.
    """
    try:
        if (report['phase'] != 'C14 P4E G7' or
            report['kind'] != 'OFFLINE_DEVELOPMENT_RESEARCH_NOT_PRODUCTION_GATE' or
            report['scientific_backends']['dowhy_tag_authenticated'] or
            report['scientific_backends']['production_authorization_attested'] or
            report['scientific_backends']['econml_version'] != '0.17.0'):
            return False
        design=report['design']
        seeds=design['seeds']
        n=design['observations_per_case']
        if (design['scenarios'] != list(SCENARIOS) or not 1<=len(seeds)<=5 or
            len(seeds)!=len(set(seeds)) or not 1<=n<=MAX_N or
            len(report['results'])!=len(seeds)*len(SCENARIOS)):
            return False
        expected={(scenario,seed) for scenario in SCENARIOS for seed in seeds}
        actual={(row['fixture']['scenario'],row['fixture']['seed']) for row in report['results']}
        if actual!=expected:return False
        for row in report['results']:
            fx=row['fixture'];scenario=fx['scenario'];seed=fx['seed']
            data,oracle=make_fixture(scenario,seed,n)
            if fx!=oracle:return False
            check=exact_stratified(data)
            original=row['reference']
            if check['status']!=original['status']:return False
            if check['status']=='EMPIRICAL_CONTRAST_COMPUTED':
                for field in ('ate','exact_fraction','cate_z0','cate_z1','independently_checked'):
                    if check[field]!=original[field]:return False
                if not math.isclose(original['absolute_oracle_ate_error'],
                    abs(check['ate']-oracle['oracle_ate']),rel_tol=0,abs_tol=1e-12):return False
            else:
                if original!=check or row['status']!='PRECHECK_REJECTED':return False
                if any(r.get('status')!='NOT_RUN_PRECHECK' for r in row['method_results'].values()):
                    return False
            for name,result in row['method_results'].items():
                if result['status']!='ESTIMATED':continue
                if not name in ('dowhy_assumed_graph','econml_assumed_graph','statsmodels_interaction'):
                    return False
                if not math.isfinite(result['ate']):return False
                if not math.isclose(result['absolute_oracle_ate_error'],
                        abs(result['ate']-oracle['oracle_ate']),rel_tol=0,abs_tol=1e-12):return False
                if not math.isclose(result['absolute_empirical_reference_difference'],
                        abs(result['ate']-check['ate']),rel_tol=0,abs_tol=1e-12):return False
                for label,field in ((0,'cate_z0'),(1,'cate_z1')):
                    if field in result:
                        if not math.isclose(result[f'absolute_oracle_cate_error_z{label}'],
                            abs(result[field]-oracle[f'oracle_cate_z{label}']),rel_tol=0,abs_tol=1e-12):
                            return False
            if scenario=='hidden_confounder':
                if row['method_results']['dowhy_explicit_latent_graph']['status']!='BLOCKED_KNOWN_UNOBSERVED_CONFOUNDER':
                    return False
                if not oracle['unobserved_common_cause_in_generator']:return False
        if report['summary']!=summarize(report['results']):return False
        return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,ZeroDivisionError):
        return False


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--n',type=int,default=900)
    p.add_argument('--seeds',type=int,nargs='+',default=list(ALLOWED_SEEDS))
    args=p.parse_args()
    report=conduct(args.source_root,tuple(args.seeds),args.n)
    if not verify_study_report(report):raise RuntimeError('STUDY_REPLAY_VERIFICATION_FAILED')
    report['fixture_and_summary_replay_verified']=True
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'phase':report['phase'],'cases':len(report['results']),
                      'seconds':report['elapsed_seconds'],'summary':report['summary']},indent=2))

if __name__=='__main__':main()
