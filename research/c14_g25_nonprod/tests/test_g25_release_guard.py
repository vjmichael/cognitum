import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'baseline'))
import numpy as np
import pytest
from scipy.stats import beta
from statsmodels.stats.proportion import proportion_confint
from g25i_core import exact_binomial
from g25_release_guard import report, strict_counts, replay_audit, _canonical

SAFE = {
  "sampling_iid_supported": True,
  "consistency_supported": True,
  "measurement_validity_supported": True,
  "gamma_justification": "Predeclared sensitivity risk-difference bound; not verified from data",
  "exchangeability_justification": "External design documentation asserting all measured confounders",
}
COUNTS = np.array([[[67, 35], [45, 31]], [[75, 30], [48, 39]]], dtype=int)

def test_sensitivity_output_is_always_noncertifying():
    for g in [0, .1, .25, .5, 1]:
        r = report(COUNTS, g, SAFE)
        assert r['status'] == 'conditional_sensitivity_report_only'
        assert r['automatic_causal_certification'] is False
        assert r['unmeasured_confounding_excluded'] is False
        assert r['production_estimator_promotion'] is False
        assert r['identified_set_outer95_conditional'][0] <= r['identified_set_plugin'][0]
        assert r['identified_set_outer95_conditional'][1] >= r['identified_set_plugin'][1]
        assert replay_audit(r, COUNTS, g, SAFE)

@pytest.mark.parametrize('invalid', [
    [[[1., 2.], [3., 4.]], [[5.,6.],[7.,8.]]],
    [[[True, 2], [3,4]], [[5,6], [7,8]]],
    [[[-1, 2], [3,4]], [[5,6], [7,8]]],
    [[1,2], [3,4]],
    np.zeros((2,2,2), dtype=int),
    [[[2**53,2],[3,4]], [[5,6],[7,8]]],
])
def test_invalid_counts_fail_closed(invalid):
    with pytest.raises(ValueError):strict_counts(invalid)

@pytest.mark.parametrize('g',[None, -0.1, 1.01, float('nan'), float('inf'), True, '0.25'])
def test_invalid_gamma_fail_closed(g):
    with pytest.raises(ValueError):report(COUNTS,g,SAFE)

def test_missing_arm_refused():
    z=COUNTS.copy();z[0,1]=0
    r=report(z,.25,SAFE)
    assert r['status']=='blocked_missing_observed_arm'
    assert r['identified_set_outer95_conditional'] is None

def test_sparse_arm_refused():
    z=COUNTS.copy();z[0,1]=[3,4]
    assert report(z,.25,SAFE)['status']=='blocked_sparse_observed_arm'

def test_assumption_evidence_fail_closed():
    for e in [None, {}, {**SAFE,'sampling_iid_supported': False},
              {**SAFE,'measurement_validity_supported': False},
              {**SAFE,'gamma_justification': 'unknown'}]:
        r=report(COUNTS,.25,e)
        assert r['status']=='blocked_missing_assumption_evidence'
        assert r['identified_set_outer95_conditional'] is None
    e=SAFE.copy();e.pop('exchangeability_justification')
    assert report(COUNTS,0,e)['status']=='blocked_missing_assumption_evidence'

def test_gamma_monotone_and_bounded():
    out=[report(COUNTS,g,SAFE)['identified_set_outer95_conditional'] for g in [0,.25,.5,1]]
    for a,b in zip(out,out[1:]):
        assert a[0] >= b[0]-1e-12 and a[1] <= b[1]+1e-12
    assert all(-1<=v<=1 for ab in out for v in ab)

def test_tamper_and_rehashed_forgery_refused():
    r=report(COUNTS,.25,SAFE)
    for field,new in [('status','conditional_causal_certified'),('automatic_causal_certification',True),
                      ('gamma_analyst_supplied',0.0),('sample_size',999),
                      ('identified_set_outer95_conditional',[-.001,.001])]:
        u=r.copy();u[field]=new
        assert not replay_audit(u,COUNTS,.25,SAFE)
        # A malicious party may recompute the public SHA; numerical replay still fails.
        import hashlib
        q={k:v for k,v in u.items() if k!='receipt_sha256'}
        u['receipt_sha256']=hashlib.sha256(_canonical(q).encode()).hexdigest()
        assert not replay_audit(u,COUNTS,.25,SAFE)

def test_bonferroni_cp_matches_independent_statsmodels_beta():
    rng=np.random.default_rng(20261101)
    for n in [1,2,5,20,200,900]:
        for k in sorted(set([0,1,n//2,max(0,n-1),n] + rng.integers(0,n+1,20).tolist())):
            a=exact_binomial(k,n,alpha=.05/7)
            b=proportion_confint(k,n,alpha=.05/7,method='beta')
            assert a == pytest.approx(b,abs=4e-13)

def test_rng_synthetic_cases_and_refusal_accounting():
    rng=np.random.default_rng(980005)
    statuses={}
    for _ in range(300):
        z=rng.multinomial(900,np.full(8,1/8)).reshape(2,2,2)
        r=report(z,.25,SAFE)
        statuses[r['status']]=statuses.get(r['status'],0)+1
        assert replay_audit(r,z,.25,SAFE)
    assert statuses == {'conditional_sensitivity_report_only': 300}

def test_plugin_identified_set_matches_independent_counterfactual_lp():
    """Independent LP over the two unobserved counterfactual means in each W stratum."""
    from scipy.optimize import linprog
    rng=np.random.default_rng(71057)
    from g25i_core import from_counts
    for _ in range(120):
        z=rng.multinomial(700,np.full(8,1/8)).reshape(2,2,2)
        gamma=float(rng.choice([0., .1, .25, .7, 1.]))
        ref=from_counts(z,gamma)['identified']
        strata=[]
        for w in range(2):
            a=z[w].sum(axis=1)
            e=a[1]/a.sum()
            m0=z[w,0,1]/a[0]
            m1=z[w,1,1]/a[1]
            # E[Y(1)-Y(0)|W] = e*m1 + (1-e)*u1 -(1-e)*m0-e*u0.
            c=np.array([1-e,-e])
            baseline=e*m1-(1-e)*m0
            bounds=[(max(0,m1-gamma),min(1,m1+gamma)),
                    (max(0,m0-gamma),min(1,m0+gamma))]
            v=linprog(c,bounds=bounds,method='highs')
            u=linprog(-c,bounds=bounds,method='highs')
            assert v.success and u.success
            strata.append((baseline+v.fun,baseline-u.fun))
        p0=z[0].sum()/z.sum()
        lo=p0*strata[0][0]+(1-p0)*strata[1][0]
        hi=p0*strata[0][1]+(1-p0)*strata[1][1]
        assert ref == pytest.approx([lo,hi],abs=1e-12)
