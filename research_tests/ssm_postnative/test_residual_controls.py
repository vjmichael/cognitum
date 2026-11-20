"""POST-NATIVE-01 independent residual tests; reference is accepted 391-case source.

No source mutation, no network, no external control authority.
"""
import itertools
import numpy as np
import pytest
from cognitum.research import ssm_interop as s
from cognitum.research import ssm_research_validation as v


def model():
    return s.model([[.75, .125], [0, .6]], [[1.], [.3]], [[1., 0.]], .1,
                   ['m', 'm'], ['N'], ['m'], 'a' * 64)


def data(seed=123, n=144, *, shift=False, future=False):
    rng = np.random.default_rng(seed)
    u = rng.normal(size=n)
    x = np.empty(n)
    x[0] = .4
    for t in range(1,n):
        x[t] = .7*x[t-1] + .6*u[t-1] + rng.normal(scale=.015)
        if shift and t >= 99:
            x[t] = x[98]
    if future:
        x[110:] += np.linspace(0, 20, n-110)
    return ('time_seconds,observation,control\n' + ''.join(
        f'{t/10:.8f},{x[t]:.12f},{u[t]:.12f}\n' for t in range(n))).encode()


def evaluated(raw):
    m=v.manifest(raw, source='synthetic', declared_license='CC0-1.0',
                 time_unit='s', observation_unit='m', control_unit='N', origin='known-synthetic')
    p=v.protocol(m, train_end=64, val_end=96, seed=91,
                 ridge_candidates=(0., .001, .01), improvement_ratio=.95)
    return v.evaluate(raw,m,p,expected_protocol_sha256=s.digest(p)),m,p


def test_ds66_exhaustive_all_1024_positive_chunk_partitions():
    """Every composition of 11 time steps: 2^(11-1) partitions, not a spot check."""
    m=model()
    start=s.state(m,[.125,-.25],step=23,stream='frozen-scientific-stream')
    u=np.random.default_rng(125).normal(size=(11,1))
    direct=s.advance(m,start,u,s.digest(start),23)
    reference=s.read(direct['trajectory'])
    for mask in range(1<<10):
        cuts=[0]+[i for i in range(1,len(u)) if mask&(1<<(i-1))]+[len(u)]
        state=start
        trajectory=[]
        for a,b in zip(cuts,cuts[1:]):
            z=s.advance(m,state,u[a:b],s.digest(state),23+a)
            tr=s.read(z['trajectory'])
            assert tr['start_state_sha256']==s.digest(state)
            assert tr['end_state_sha256']==s.digest(z['state'])
            trajectory.extend(tr['outputs'])
            state=z['state']
        assert state==direct['state']
        assert trajectory==reference['outputs']


@pytest.mark.parametrize('seed',[3,17,81])
def test_ds66_reset_and_prefix_independence(seed):
    m=model();u=np.random.default_rng(seed).normal(size=(36,1));x=s.state(m,[.1,-.2],step=0,stream=f'seed-{seed}')
    q=s.advance(m,x,u[:18],s.digest(x),0)
    tail=s.advance(m,q['state'],u[18:],s.digest(q['state']),18)
    full=s.advance(m,x,u,s.digest(x),0)
    assert tail['state']==full['state']
    changed=np.array(u,copy=True);changed[18:]+=25
    new=s.advance(m,x,changed[:18],s.digest(x),0)
    assert new['state']==q['state'] and new['trajectory']==q['trajectory']
    other=s.state(m,[.1,-.2],step=0,stream='other-stream')
    assert s.digest(other)!=s.digest(x)
    with pytest.raises(ValueError,match='stale'):
        s.advance(m,other,u,s.digest(x),0)


def test_ds70_shift_is_falsified_against_persistence():
    z,m,p=evaluated(data(55,shift=True))
    assert z['falsified']
    assert z['test_rmse']>z['persistence_rmse']
    assert z['model_selection_validation_only'] and z['test_not_used_for_fitting']
    assert z['test_count']>=20
    assert s.read(m)['license_verified'] is False


def test_ds70_future_data_cannot_change_fitted_coefficients():
    a,m,p=evaluated(data(7));b,M,P=evaluated(data(7,future=True))
    np.testing.assert_array_equal(a['coefficients'],b['coefficients'])
    assert a['selected_ridge']==b['selected_ridge']
    assert a['validation_rmse']==b['validation_rmse']
    assert a['test_rmse']!=b['test_rmse']
    assert a['protocol_sha256']!=b['protocol_sha256']
    with pytest.raises(ValueError,match='protocol pin'):
        v.evaluate(data(7,future=True),M,P,expected_protocol_sha256=s.digest(p))


def test_ds70_license_metadata_is_not_a_license_verification():
    raw=data();_,m,_=evaluated(raw);o=s.read(m)
    assert o['declared_license']=='CC0-1.0' and o['license_verified'] is False
    with pytest.raises(ValueError):
        v.validate_data(raw,s.wire(dict(o,license_verified=True)))
    with pytest.raises(ValueError):
        v.validate_data(raw.replace(b'0.00000000',b'0.00100000',1),m)


@pytest.mark.parametrize('kind',s.KINDS)
def test_ds69_classification_is_not_validation_or_actuation(kind):
    a=s.evidence(kind,'a'*64,['bounded-domain','reference-only'],'b'*64,'abs_error=0')
    z=s.read(a)
    assert z['classification']==kind and z['verified'] is False
    assert z['execution_authorized'] is False
    assert z['artifact_sha256']=='b'*64  # It is a claim, not verified byte provenance.
    with pytest.raises(ValueError):
        s.evidence(kind,'a'*64,['bounded-domain'],'invalid-hash','abs_error=0')
    with pytest.raises(ValueError):
        s.evidence('formal-proof','a'*64,['bounded-domain'],'b'*64,'abs_error=0')


def test_ds65_ds72_control_proposal_never_becomes_an_action():
    m=model();x=s.state(m,[.1,-.2],step=10)
    proposed=s.read(s.control_proposal(m,x,[[.2],[-.3]]))
    assert not proposed['execution_authorized']
    assert proposed['model_sha256']==s.digest(m)
    assert proposed['state_sha256']==s.digest(x)
    assert proposed['first_step']==10
    assert set(proposed)=={'version','kind','model_sha256','state_sha256','first_step','inputs','execution_authorized'}


def test_ds71_longer_256_step_replay_is_measured_not_benchmarked():
    m=model();x=s.state(m,[.1,-.2]);u=np.random.default_rng(31).normal(size=(256,1))
    z=v.machine_profile(m,x,u,repeats=3,max_wall_ms=60000,max_peak_bytes=8_000_000)
    assert z['repeats']==3 and len(z['peak_python_bytes'])==3
    assert z['output_state_sha256']==s.digest(s.advance(m,x,u,s.digest(x),0)['state'])
    assert all(t>=0 for t in z['cpu_ms']) and all(t>=0 for t in z['repeats_ms'])
    assert 'no RSS/GPU/energy' in z['measurement_scope'] and not z['performance_baseline']

@pytest.mark.parametrize('risk',[.01,.025,.1])
def test_ds45_chance_bound_has_independent_gaussian_tail_reference(risk):
    """Known covariance, fixed deterministic x0, independent exact marginal tails."""
    from scipy.stats import norm
    from cognitum.research import ssm_control_extended as c
    A=.75; sigma=.2; nsteps=5; x0=.1
    z=c.uncertain_plan([[A]],[[1]],[[.2]],[[1]],[[.5]],
                       [x0],nsteps,[2],[2],noise_cov=[[sigma*sigma]],risk=risk)
    assert not z['recursive_feasibility_established']
    for j in range(nsteps):
        variance=sigma**2*sum(A**(2*t) for t in range(j+1))
        q=norm.isf(risk/(2*nsteps))
        assert z['tightening'][j,0]==pytest.approx(q*np.sqrt(variance),rel=1e-12)
        mean=z['states'][j+1,0]
        actual_tail=norm.cdf((-2-mean)/np.sqrt(variance))+norm.sf((2-mean)/np.sqrt(variance))
        assert actual_tail<=risk/nsteps+1e-12


def test_ds45_heavy_tail_invalidates_gaussian_probability_interpretation():
    """A precise counterexample to extrapolating Gaussian guarantees to a t distribution."""
    from scipy.stats import norm, t
    from cognitum.research import ssm_control_extended as c
    risk=.01;sigma=.1;q=norm.isf(risk/2)
    xb=(q+1e-3)*sigma
    z=c.uncertain_plan([[0]],[[1]],[[0]],[[1]],[[0]],
                       [0],1,[xb],[1],noise_cov=[[sigma*sigma]],risk=risk)
    assert z['inputs'][0,0]==pytest.approx(0)
    # This t_3 variable has the *same variance* sigma^2 as the Gaussian model.
    # Its true two-sided tail exceeds the requested nominal risk.
    actual=2*t.sf((xb/sigma)*np.sqrt(3),df=3)
    assert actual>risk*1.5
    assert z['joint_risk_bound']==risk
    assert not z['recursive_feasibility_established']


def test_ds48_exact_scalar_filter_feasibility_and_nearest_projection():
    """Exhaustive small rational profiles, independently check every feasible result."""
    from fractions import Fraction as F
    from cognitum.research import ssm_control_extended as c
    checked=0;refused=0
    for a,b,x,u,w in itertools.product((F(-1),F(0),F(1),F(2)),
                                        (F(-2),F(-1),F(0),F(1),F(2)),
                                        (F(-1,2),F(0),F(1,2)),
                                        (F(-2),F(0),F(2)),(F(0),F(1,4))):
        # Derive feasible interval from raw inequalities, independent of chosen u.
        feasible=[]
        for candidate in (F(-2),F(-1),F(-1,2),F(0),F(1,2),F(1),F(2)):
            if abs(a*x+b*candidate)+w<=1:feasible.append(candidate)
        try: result=c.scalar_safety(str(a),str(b),str(x),str(u),'1','2',str(w))
        except ValueError:
            assert not feasible;refused+=1;continue
        v=F(result['input']);assert abs(v)<=2
        assert abs(a*x+b*v)+w<=1
        assert F(result['state_margin'])==1-abs(a*x+b*v)-w
        assert all(abs(v-u)<=abs(candidate-u) for candidate in feasible)
        assert result['execution_authorized'] is False
        checked+=1
    assert checked>300 and refused>=6


def test_ds44_receding_horizon_is_not_certified_recursive_feasibility():
    from cognitum.research import ssm_control_extended as c
    z=c.receding([[.8]],[[1]],[[.2]],[[1]],[[.5]],
                [.15],3,[1],[1],[[.03],[-.02],[.01],[-.01]],[.05])
    assert len(z['states'])==5 and not z['recursive_feasibility_established']
    assert np.max(abs(z['states']))<=1
