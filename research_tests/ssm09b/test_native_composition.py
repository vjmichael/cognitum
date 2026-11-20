"""Requires genuine repository HDC and MEL/KAN checkpoint runtimes; no mock imports."""
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from tools.cog04o.fixtures import elliptic
from cognitum.research import ssm_scientist_bridge as s
from cognitum.research import ssm_interop as w
from cognitum.research import ssm_research_validation as v
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_associative import Cleanup


def fixture():
    raw=('time_seconds,observation,control\n'+''.join(f'{i/10:.6f},{.1+i/2000:.8f},{.5+i/3000:.8f}\n' for i in range(100))).encode()
    manifest=v.manifest(raw,source='synthetic',declared_license='CC0-1.0',time_unit='s',observation_unit='unitless',control_unit='unitless',origin='analytic-elliptic')
    C=[elliptic(),elliptic(scale=.5)];Y=elliptic()
    m=s.scientific_model(C,Y,step_seconds=.025,state_units=['unitless','unitless'],dataset_manifest_sha256=w.digest(manifest),source_sha256=w.digest(raw))
    z=s.scientific_state(m,[.1,.2],2,'experiment-1')
    rng=np.random.default_rng(17);a=rng.choice([-1,1],32).astype(np.int8);b=-a;other=np.tile([1,-1],16).astype(np.int8)
    if np.array_equal(a,other) or np.array_equal(a,-other):other=np.roll(other,1)
    records=[(s.scientific_state(m,[.15,.2],0,'experiment-1'),b,'wrong'),(s.scientific_state(m,[.1,.2],1,'experiment-1'),a,'matched'),(s.scientific_state(m,[.2,.3],3,'experiment-1'),a,'future')]
    return raw,manifest,C,Y,m,z,a,records


def test_real_hdc_backend_candidate_and_abstention():
    raw,manifest,C,Y,m,z,q,records=fixture();assert isinstance(Cleanup(Spec('MAP',32),np.stack((q,-q)).astype(np.float32)),Cleanup)
    a=s.hdc_candidates(m,records,q,not_after_step=2);assert a['candidate']['regime']=='matched' and a['candidate']['cosine_similarity']==pytest.approx(1) and a['candidate_only']
    t=s.hdc_candidates(m,records,q,not_after_step=0);assert t['abstained'] and t['candidate'] is None
    r=s.hdc_candidates(m,records,np.roll(q,1),not_after_step=2,minimum=.99);assert r['abstained']
    with pytest.raises(ValueError):s.hdc_candidates(m,records+records[:1],q,not_after_step=2)


def test_real_kan_gradient_integrator_and_observer():
    raw,manifest,C,Y,m,z,q,records=fixture();x,y=.25,.5;field=w.kan_eval(C[0],[x,y]);assert field['value']==pytest.approx(9*x*(1-x)*y*(1-y));np.testing.assert_allclose(field['gradient'],[9*(1-2*x)*y*(1-y),9*x*(1-x)*(1-2*y)],atol=1e-12)
    path=w.kan_evolve(C,[.1,.2],.025,8)
    ref=solve_ivp(lambda t,x:9*x[0]*(1-x[0])*x[1]*(1-x[1])*np.array([1,.5]),(0,.2),[.1,.2],t_eval=np.linspace(0,.2,9),rtol=1e-12,atol=1e-13).y.T
    np.testing.assert_allclose(path['states'],ref,atol=1e-7)
    value=w.kan_eval(Y,path['states'][-1])['value'];p=w.kan_observe(Y,path['states'][-1],np.eye(2)*.001,value+.01,.02,.001);assert np.isfinite(p['nis'])


def test_real_composition_reproducibility():
    raw,manifest,C,Y,m,z,q,records=fixture();x=np.array([.1,.2]);traj=w.kan_evolve(C,x,.025,4);value=w.kan_eval(Y,traj['states'][-1])['value'];args=dict(expected_state_sha256=w.digest(z),not_after_step=2,steps=4,heldout_observation=value+.01,measurement_variance=.02,model_variance=.001,dataset_raw=raw,manifest_raw=manifest,prior_covariance=np.eye(2)*.001)
    a=s.investigate(m,z,C,Y,records,q,**args);b=s.investigate(m,z,C,Y,records,q,**args)
    assert a['next_state']==b['next_state'] and a['trace']==b['trace'] and a['evidence']==b['evidence'];assert a['hdc']['candidate']['regime']=='matched'
    trace=w.read(a['trace']);assert trace['absolute_error']==pytest.approx(.01) and trace['unverified'] and not trace['execution_authorized'];assert trace['dataset_sha256']==w.digest(raw)
    ev=w.read(a['evidence']);assert ev['classification']=='numerical-residual' and ev['artifact_sha256']==w.digest(a['trace']) and not ev['verified']
    assert not a['verified_scientific_claim'] and w.read(a['next_state'])['step']==6


def test_real_composition_tamper_and_future():
    raw,manifest,C,Y,m,z,q,records=fixture();traj=w.kan_evolve(C,[.1,.2],.025,2);value=w.kan_eval(Y,traj['states'][-1])['value'];args=dict(expected_state_sha256=w.digest(z),not_after_step=2,steps=2,heldout_observation=value,measurement_variance=.02,model_variance=.001,dataset_raw=raw,manifest_raw=manifest,prior_covariance=np.eye(2)*.001)
    with pytest.raises(ValueError,match='checkpoint mismatch'):s.investigate(m,z,[C[1],C[0]],Y,records,q,**args)
    with pytest.raises(ValueError,match='stale'):s.investigate(m,z,C,Y,records,q,**dict(args,expected_state_sha256='f'*64))
    with pytest.raises(ValueError,match='tamper|provenance'):s.investigate(m,z,C,Y,records,q,**dict(args,dataset_raw=raw.replace(b'0.100000',b'0.110000',1)))
    a=s.investigate(m,z,C,Y,records,q,**args);assert a['hdc']['candidate']['regime']!='future'
