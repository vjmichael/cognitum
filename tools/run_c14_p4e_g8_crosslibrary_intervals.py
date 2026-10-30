"""Optional real DoWhy/EconML interval smoke; NOT comparable estimand certification.

DoWhy backdoor OLS gives ATE interval; EconML LinearDML gives two CATE
intervals. These cannot be numerically compared as the same estimand. Hidden
confounder intervals are deliberately excluded from valid coverage summaries.
No Lu/Windows authorization and DoWhy main source is not authenticated v0.14.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from tools import run_c14_p4e_g7_study as g7

SCENARIOS=('observed_homogeneous','observed_heterogeneous','null_effect','hidden_confounder')

def run_one(scenario,seed,n,libs):
    import numpy as np
    data,oracle=g7.make_fixture(scenario,seed,n)
    pd,nx=libs['pd'],libs['nx']
    graph=nx.DiGraph()
    graph.add_nodes_from(['v0','v1','v2'])
    graph.add_edges_from([('v0','v1'),('v0','v2'),('v1','v2')])
    df=pd.DataFrame(data,columns=['v0','v1','v2'])
    cm=libs['CausalModel'](data=df,treatment='v1',outcome='v2',graph='\n'.join(nx.generate_gml(graph)),proceed_when_unidentifiable=False)
    identified=cm.identify_effect(proceed_when_unidentifiable=False)
    if set(identified.get_backdoor_variables() or [])!={'v0'}:raise ValueError('BAD_IDENTIFICATION_SET')
    estimated=cm.estimate_effect(identified,method_name='backdoor.linear_regression',control_value=0,
                                 treatment_value=1,target_units='ate',confidence_intervals=True,test_significance=False)
    ci=np.asarray(estimated.get_confidence_intervals(),dtype=float).flatten()
    if ci.size!=2:raise ValueError('DOWHY_INTERVAL_WRONG_SHAPE')
    dw_est=float(estimated.value)
    est=libs['LinearDML'](model_y=libs['LinearRegression'](),model_t=libs['LogisticRegression'](max_iter=600),
                          discrete_treatment=True,cv=3,random_state=seed)
    z=data[:,0].reshape(-1,1).astype(float)
    est.fit(data[:,2],data[:,1],X=z,inference='auto')
    xx=np.asarray([[0.],[1.]])
    cats=[float(x) for x in est.effect(xx)]
    lo,hi=est.effect_interval(xx,alpha=.05)
    lo=[float(x) for x in lo];hi=[float(x) for x in hi]
    vals=[dw_est,*ci,*cats,*lo,*hi]
    if not all(math.isfinite(v) for v in vals) or not (ci[0]<=dw_est<=ci[1]) or any(not lo[i]<=cats[i]<=hi[i] for i in (0,1)):
        raise ValueError('INVALID_BACKEND_INTERVAL_RESULT')
    valid=scenario!='hidden_confounder'
    return {'oracle':oracle,'comparison_class':'ASSUMPTION_BREACH_DIAGNOSTIC_NOT_COVERAGE' if not valid else 'SYNTHETIC_CLEAN_ASSUMPTIONS',
            'dowhy':{'method':'backdoor.linear_regression_ols_ate','effect':dw_est,'ci95':[float(ci[0]),float(ci[1])],
                     'oracle_covered':bool(ci[0]<=oracle['oracle_ate']<=ci[1]),'coverage_eligible':valid},
            'econml':{'method':'LinearDML_cate_z0_z1','cate':cats,'ci95':list(zip(lo,hi)),
                      'oracle_cate_covered':[lo[i]<=oracle[f'oracle_cate_z{i}']<=hi[i] for i in (0,1)],
                      'coverage_eligible':valid},
            'warnings':['ASSUMED_GRAPH_NOT_VERIFIED','DIFFERENT_ESTIMANDS_ATE_VERSUS_CATE',
                        'SMALL_RUN_NOT_COVERAGE_CALIBRATION']}


def conduct(source_root,seeds=(101,202,303),sizes=(300,900)):
    if len(seeds)>5 or len(sizes)>2 or len(set(seeds))!=len(seeds) or len(set(sizes))!=len(sizes):
        raise ValueError('BOUND_GRID_REQUIRED')
    libs=g7.load_dependencies(source_root)
    runs=[run_one(s,seed,n,libs) for n in sizes for seed in seeds for s in SCENARIOS]
    summaries={}
    for s in SCENARIOS:
        r=[row for row in runs if row['oracle']['scenario']==s]
        summaries[s]={'cases':len(r),'valid_coverage_cases':sum(x['dowhy']['coverage_eligible'] for x in r),
                      'do_why_ate_covered_count_descriptive':sum(x['dowhy']['oracle_covered'] for x in r) if s!='hidden_confounder' else None,
                      'econml_cate_z0_covered_count_descriptive':sum(x['econml']['oracle_cate_covered'][0] for x in r) if s!='hidden_confounder' else None,
                      'econml_cate_z1_covered_count_descriptive':sum(x['econml']['oracle_cate_covered'][1] for x in r) if s!='hidden_confounder' else None}
    return {'phase':'C14 P4E G8 cross-library interval smoke','kind':'RESEARCH_ONLY',
            'source':{'dowhy_source_digest':libs['source_sha256'],'dowhy_tag_authenticated':False,
                      'econml_version':libs['econml_version']},
            'design':{'seeds':list(seeds),'sample_sizes':list(sizes),'scenarios':list(SCENARIOS)},
            'results':runs,'summaries':summaries,
            'limitations':['Different estimands; cannot rank methods using these intervals',
                           'Small study NOT valid interval coverage calibration',
                           'Unverified DoWhy main source and compiled EconML user-supplied source',
                           'Host authorization, Windows isolation and deployment lock not verified']}


def verify_report(report):
    # Provenance/digest and structural validation; no re-execution means no
    # independent numerical verification of external library computations.
    try:
        if report['phase']!='C14 P4E G8 cross-library interval smoke' or report['kind']!='RESEARCH_ONLY' or report['source']['dowhy_tag_authenticated']:return False
        d=report['design'];expected={(s,seed,n) for s in SCENARIOS for seed in d['seeds'] for n in d['sample_sizes']}
        got=set()
        for r in report['results']:
            f=r['oracle'];key=(f['scenario'],f['seed'],f['n'])
            if key in got or key not in expected:return False
            got.add(key)
            _,oracle=g7.make_fixture(*key)
            if f!=oracle:return False
            dw=r['dowhy'];e=r['econml']; valid=f['scenario']!='hidden_confounder'
            if bool(dw['coverage_eligible'])!=valid or bool(e['coverage_eligible'])!=valid:return False
            ci=dw['ci95'];values=[dw['effect'],*ci,*e['cate'],*(p for interval in e['ci95'] for p in interval)]
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):return False
            if not ci[0]<=dw['effect']<=ci[1]:return False
            if dw['oracle_covered']!=(ci[0]<=f['oracle_ate']<=ci[1]):return False
            for i in (0,1):
                if not e['ci95'][i][0]<=e['cate'][i]<=e['ci95'][i][1]:return False
                if e['oracle_cate_covered'][i]!=(e['ci95'][i][0]<=f[f'oracle_cate_z{i}']<=e['ci95'][i][1]):return False
        if got!=expected:return False
        for scenario in SCENARIOS:
            rows=[r for r in report['results'] if r['oracle']['scenario']==scenario]
            expected_summary={'cases':len(rows),'valid_coverage_cases':sum(x['dowhy']['coverage_eligible'] for x in rows),
              'do_why_ate_covered_count_descriptive':sum(x['dowhy']['oracle_covered'] for x in rows) if scenario!='hidden_confounder' else None,
              'econml_cate_z0_covered_count_descriptive':sum(x['econml']['oracle_cate_covered'][0] for x in rows) if scenario!='hidden_confounder' else None,
              'econml_cate_z1_covered_count_descriptive':sum(x['econml']['oracle_cate_covered'][1] for x in rows) if scenario!='hidden_confounder' else None}
            if report['summaries'][scenario]!=expected_summary:return False
        return True
    except (KeyError,TypeError,ValueError,IndexError):return False


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-root',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    args=p.parse_args()
    result=conduct(args.source_root)
    if not verify_report(result):raise RuntimeError('G8_CROSSLIBRARY_SHAPE_VERIFICATION_FAILED')
    result['shape_replay_verified']=True
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps(result['summaries'],indent=2))

if __name__=='__main__':main()
