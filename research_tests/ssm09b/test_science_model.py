import numpy as np
import pytest
from cognitum.research import ssm_scientist_bridge as s
from cognitum.research import ssm_interop as w


def model():return s.scientific_model([b'first',b'second'],b'sensor',step_seconds=.05,state_units=['m','m'],dataset_manifest_sha256='a'*64,source_sha256='b'*64)


def test_canonical_science_state():
    m=model();z=s.scientific_state(m,[.2,.3],3,'science-1');assert s.load_scientific_state(m,z)==w.read(z);assert w.read(m)['domain']=='normalized-unit-square'
    assert w.read(m)['dynamics_sha256']==[w.digest(b'first'),w.digest(b'second')]


@pytest.mark.parametrize('variant',['wrong-model','wrong-state','domain','unknown-field','forged-action'])
def test_science_refusal(variant):
    m=model();z=s.scientific_state(m,[.2,.3])
    if variant=='wrong-model':m=s.scientific_model([b'other',b'second'],b'sensor',step_seconds=.05,state_units=['m','m'],dataset_manifest_sha256='a'*64,source_sha256='b'*64)
    if variant=='wrong-state':d=w.read(z);d['model_sha256']='c'*64;z=w.wire(d)
    if variant=='domain':z=s.scientific_state(m,[.2,.3]);d=w.read(z);d['values']=[1.1,.2];z=w.wire(d)
    if variant=='unknown-field':d=w.read(z);d['extra']='yes';z=w.wire(d)
    if variant=='forged-action':d=w.read(z);d['execution_authorized']=True;z=w.wire(d)
    with pytest.raises(ValueError):s.load_scientific_state(m,z)


def test_reject_malformed_model():
    d=w.read(model());d['execution_authorized']=True
    with pytest.raises(ValueError):s.load_scientific_model(w.wire(d))
    d=w.read(model());d['step_seconds']=0
    with pytest.raises(ValueError):s.load_scientific_model(w.wire(d))


def test_science_resets():
    m=model();p=s.scientific_state(m,[.2,.3],7,'stream-a');q=s.scientific_state(m,[.2,.3],7,'stream-b')
    assert w.digest(p)!=w.digest(q) and s.load_scientific_state(m,p)['stream']=='stream-a'
