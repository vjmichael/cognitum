"""Requires the complete MEL/KAN/HDC repository runtime: native-only tests."""
import hashlib
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from tools.cog04o.fixtures import elliptic
from cognitum.research import ssm_external_qualification as q
from cognitum.research import ssm_scientist_bridge as bridge
from cognitum.research.ssm_interop import digest


def vector_fields(sign):
    # Two genuinely distinct represented KAN vector fields, not a renamed test.
    return (elliptic(),elliptic(scale=sign*.5))


def independent_reference(sign,initial,dt,steps):
    def f(t,x):
        v=9*x[0]*(1-x[0])*x[1]*(1-x[1]);return [v,sign*.5*v]
    return solve_ivp(f,(0,dt*steps),initial,rtol=1e-12,atol=1e-13).y[:,-1]


@pytest.mark.parametrize('sign',[1,-1])
@pytest.mark.parametrize('initial',[(.2,.3),(.35,.65)])
def test_two_distinct_checkpoint_dynamical_families_against_independent_ivp(sign,initial):
    truth=vector_fields(sign);false=vector_fields(-sign);ref=independent_reference(sign,initial,.025,10)
    z=q.kan_hypotheses(truth,false,initial,ref,.025,10,tolerance=2e-6,
          expected_true_hashes=tuple(map(digest,truth)),expected_wrong_hashes=tuple(map(digest,false)))
    assert z['true_error']<2e-6 and not z['true_rejected']
    assert z['alternative_error']>1e-3 and z['alternative_rejected']
    assert z['checkpoint_source_only'] and not z['autonomous_discovery_claim']
    assert not z['execution_authorized']


def test_checkpoint_digest_negative_control_rejected():
    t=vector_fields(1);f=vector_fields(-1)
    with pytest.raises(ValueError,match='checkpoint pin'):
        q.kan_hypotheses(t,f,[.2,.3],[.2,.3],.025,4,tolerance=.01,
            expected_true_hashes=('a'*64,digest(t[1])),expected_wrong_hashes=tuple(map(digest,f)))


def test_genuine_hdc_cleanup_candidate_and_abstention_are_not_facts():
    t=vector_fields(1);o=elliptic();m=bridge.scientific_model(t,o,step_seconds=.025,
        state_units=['normalized','normalized'],dataset_manifest_sha256='a'*64,source_sha256='b'*64)
    q1=np.ones(64,dtype=np.int8);q2=-q1
    records=[(bridge.scientific_state(m,[.25,.25],1),q1,'cooperative'),
             (bridge.scientific_state(m,[.4,.4],0),q2,'antagonistic'),
             (bridge.scientific_state(m,[.5,.5],10),q1,'future')]
    z=bridge.hdc_candidates(m,records,q1,not_after_step=1)
    assert z['candidate']['regime']=='cooperative' and z['candidate']['step']==1
    assert z['candidate_only'] and z['matched_engine']=='hdc_associative.Cleanup'
    ambiguous=np.tile(np.array([1,-1],np.int8),32)
    a=bridge.hdc_candidates(m,records,ambiguous,not_after_step=1)
    assert a['abstained'] and a['candidate'] is None and a['candidate_only']
