"""Reproducible G9 AIPW nuisance misspecification stress check, synthetic only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from statistics import mean
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g9_interval_comparison as g9
SPECS=(('stratified','stratified'),('stratified','pooled'),('pooled','stratified'),('pooled','pooled'))
SCENARIOS=('observed_homogeneous','observed_heterogeneous','hidden_confounder')


def run(seeds=tuple(range(1001,1201)),sizes=(300,900)):
    if not 1<=len(seeds)<=200 or len(set(seeds))!=len(seeds) or not 1<=len(sizes)<=3 or len(set(sizes))!=len(sizes):
        raise ValueError('INVALID_GRID')
    cases=[]
    for scenario in SCENARIOS:
        for n in sizes:
            for seed in seeds:
                data,fx=g7.make_fixture(scenario,seed,n)
                for p,m in SPECS:
                    out=g9.aipw_crossfit(data,seed=seed^0xC2B2AE35,propensity_spec=p,outcome_spec=m)
                    cases.append({'scenario':scenario,'n':n,'seed':seed,
                         'propensity_spec':p,'outcome_spec':m,'oracle_ate':fx['oracle_ate'],
                         'status':out['status'],
                         'estimate':out['estimate'] if out['status']=='COMPUTED' else None})
    return {'phase':'C14 P4E G9 nuisance stress','kind':'SYNTHETIC_ONLY_NO_CAUSAL_ASSUMPTION_PROOF',
            'seeds':list(seeds),'sizes':list(sizes),'cases':cases,
            'summary':summarize(cases),'causal_identification_proven':False}


def summarize(cases):
    out={}
    for scenario in SCENARIOS:
        for n in sorted({r['n'] for r in cases}):
            for p,m in SPECS:
                subset=[r for r in cases if (r['scenario'],r['n'],r['propensity_spec'],r['outcome_spec'])==(scenario,n,p,m)]
                accepted=[r for r in subset if r['status']=='COMPUTED']
                out[f'{scenario}@{n}/{p}+{m}']={'attempted':len(subset),'computed':len(accepted),
                    'mean_point_bias_descriptive':mean([r['estimate']-r['oracle_ate'] for r in accepted]) if accepted else None,
                    'causal_assumptions_supported_by_generator':scenario!='hidden_confounder'}
    return out


def verify(report):
    try:
        if report.get('causal_identification_proven') is not False:return False
        return report==run(tuple(report['seeds']),tuple(report['sizes']))
    except (ValueError,KeyError,TypeError,IndexError):return False


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seeds',type=int,default=200)
    args=p.parse_args()
    r=run(seeds=tuple(range(1001,1001+args.seeds)))
    if not verify(r):raise RuntimeError('NUISANCE_REPLAY_FAILED')
    r['numerical_replay_verified']=True
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(r['summary'],indent=2))

if __name__=='__main__':main()
