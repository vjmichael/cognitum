"""G12: new synthetic mechanisms (not the G7/G9/G11 generator).

Generates sufficient 2x2x2 contingency tables for *observed* covariate,
assignment and outcome. Latent variables and selection mechanisms are known
only to this generator. Synthetic source is not evidence of a real-world model.
"""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PHASE = 'C14 P4E G12'
SEEDS = tuple(range(73001, 73081))
SIZES = (300, 900)
SCENARIOS = ('CLEAN_INTERACTION', 'HIDDEN_COMMON_CAUSE', 'MISMEASURED_CONFOUNDER',
             'SELECTION_COLLIDER', 'TRANSPORT_SHIFT', 'NEGATIVE_CONTROL')
ORACLES = {'CLEAN_INTERACTION': .23, 'HIDDEN_COMMON_CAUSE': .02,
           'MISMEASURED_CONFOUNDER': .05, 'SELECTION_COLLIDER': .15,
           'TRANSPORT_SHIFT': .39, 'NEGATIVE_CONTROL': 0.0}


def generate(scenario, seed, n):
    if scenario not in SCENARIOS or seed not in SEEDS or n not in SIZES:
        raise ValueError('NONREGISTERED_G12_FIXTURE')
    rng = np.random.default_rng(seed + SCENARIOS.index(scenario) * 1000000 + n)
    size = n * 4 if scenario == 'SELECTION_COLLIDER' else n
    u = rng.binomial(1, .5, size)
    pz = .85 if scenario == 'TRANSPORT_SHIFT' else .5
    z = rng.binomial(1, pz, size)
    w = z.copy()
    if scenario == 'MISMEASURED_CONFOUNDER':
        w = np.bitwise_xor(z, rng.binomial(1, .30, size))
        pt = .12 + .76 * z
        py0 = .07 + .48 * z
        tau = np.full(size, .05)
    elif scenario == 'HIDDEN_COMMON_CAUSE':
        pt = .10 + .75 * u
        py0 = .12 + .50 * u
        tau = np.full(size, .02)
    elif scenario == 'CLEAN_INTERACTION':
        pt = .15 + .55 * z
        py0 = .05 + .20 * z + .10 * u
        tau = .08 + .30 * z
    elif scenario == 'SELECTION_COLLIDER':
        pt = np.full(size, .5)
        py0 = .25 + .10 * z
        tau = np.full(size, .15)
    elif scenario == 'TRANSPORT_SHIFT':
        pt = .20 + .45 * z
        py0 = .10 + .10 * z
        tau = .05 + .40 * z
    else:
        pt = np.full(size, .5)
        py0 = .14 + .40 * z
        tau = np.zeros(size)
    t = rng.binomial(1, pt)
    y = rng.binomial(1, py0 + tau * t)
    if scenario == 'SELECTION_COLLIDER':
        # Outcome-dependent selection; conditioning on S=1 creates bias.
        selected = rng.random(size) < np.where(t == y, .90, .15)
        rows = np.column_stack((w[selected], t[selected], y[selected]))
        if len(rows) < n:
            raise RuntimeError('G12_SELECTION_SAMPLE_CAP_UNEXPECTED')
        rows = rows[:n]
    else:
        rows = np.column_stack((w, t, y))
    counts = [int(np.sum((rows[:, 0] == z0) & (rows[:, 1] == t0) & (rows[:, 2] == y0)))
              for z0 in (0,1) for t0 in (0,1) for y0 in (0,1)]
    return counts


def score(counts):
    """Generator-side vectorized diagnostic; separate verifier uses scalar math."""
    c=np.asarray(counts,dtype=np.int64).reshape(2,2,2)
    n=int(c.sum())
    n0=int(c[:,0,:].sum()); n1=int(c[:,1,:].sum())
    if not n0 or not n1:return None,None
    naive=float(c[:,1,1].sum()/n1-c[:,0,1].sum()/n0)
    strata=[]
    for z in range(2):
        a=int(c[z,1,:].sum());b=int(c[z,0,:].sum())
        if not a or not b:return naive,None
        strata.append((a+b)/n*(c[z,1,1]/a-c[z,0,1]/b))
    return naive,float(sum(strata))


def conduct(seeds=SEEDS):
    if not seeds or any(s not in SEEDS for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('G12_SEED_PARTITION_VIOLATION')
    records=[]
    for scenario in SCENARIOS:
        for n in SIZES:
            for seed in seeds:
                counts=generate(scenario,seed,n)
                naive,adjusted=score(counts)
                records.append({'scenario':scenario,'sample_size':n,'seed':seed,
                    'counts_z_t_y':counts,'oracle_ate':ORACLES[scenario],
                    'naive_risk_difference':naive,'stratified_risk_difference':adjusted,
                    'observed_selection_only':scenario=='SELECTION_COLLIDER',
                    'observed_variable_is_mismeasured':scenario=='MISMEASURED_CONFOUNDER'})
    summary={}
    for scenario in SCENARIOS:
        for n in SIZES:
            matches=[x for x in records if x['scenario']==scenario and x['sample_size']==n]
            summary[f'{scenario}@{n}']={
                'attempts':len(matches),
                'adjusted_computed':sum(x['stratified_risk_difference'] is not None for x in matches),
                'mean_absolute_naive_error':float(np.mean([abs(x['naive_risk_difference']-x['oracle_ate']) for x in matches])),
                'mean_absolute_stratified_error':float(np.mean([abs(x['stratified_risk_difference']-x['oracle_ate']) for x in matches if x['stratified_risk_difference'] is not None])),
                'causal_interpretation_eligible':scenario in ('CLEAN_INTERACTION','NEGATIVE_CONTROL'),
                'outside_G9_G11_calibration_domain':True}
    return {'phase':PHASE,'status':'OFFLINE_ADVERSARIAL_SYNTHETIC_RESEARCH_ONLY',
      'design':{'seeds':list(seeds),'sample_sizes':list(SIZES),'scenarios':list(SCENARIOS),
        'oracle_ates':ORACLES,'source_model':'NEW_G12_NOT_G7_G9_G11',
        'predeclared_no_method_retuning':True},
      'records':records,'summary':summary,'dataset_count':len(records),
      'claims':{'causal_identification_proven':False,'model_domain_authenticated':False,
          'real_world_causal_claim_authorized':False,'intervention_authorized':False,
          'windows_confinement_verified':False,'lu_host_authenticated':False},
      'limitations':['Different synthetic mechanisms, but still developer-designed simulators',
        'Sufficient counts permit independent arithmetic replay, not independent proof that the generator reflects reality',
        'Selection-on-outcome, latent confounding and mismeasurement deliberately violate conventional identification assumptions',
        'Coverage was NOT evaluated in G12; this is an adversarial point-estimation and assurance stress test',
        'Reported mean errors do not support universal ranking or causal discovery accuracy']}


def write_report(path=None):
    path=Path(path or ROOT/'docs/components/causal/P4E-G12-adversarial-mechanisms-evidence.json')
    obj=conduct();path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return obj

if __name__=='__main__':
    x=write_report();print(json.dumps({'cases':x['dataset_count'],'summary':x['summary']},indent=2))
