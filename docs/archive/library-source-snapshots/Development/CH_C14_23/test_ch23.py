import json
from pathlib import Path
import numpy as np
import pytest
from scipy.special import expit
import run,independent_audit,bounded_global
D=Path(__file__).resolve().parent
P=json.loads((D/'frozen_protocol.json').read_text())

def test_frozen_reference_pin():
    import hashlib
    assert hashlib.sha256((D/'ch22_pinned.py').read_bytes()).hexdigest()==P['pinned_CH22_source_sha256']
def test_unchanged_generator():
    x,y=run.generator('zero_balanced',80,3);a,b=independent_audit.independent_generator('zero_balanced',80,3)
    assert np.array_equal(x,a) and np.array_equal(y,b)
def test_gradient_matches_fd():
    x,y=run.generator('rare_1pct',80,4);beta=np.array([-3.1,.2,-.1]);_,g=run.val_score(beta,x,y)
    from scipy.optimize._numdiff import approx_derivative
    fd=approx_derivative(lambda t:run.val_score(t,x,y)[0],beta,method='3-point',abs_step=1e-5)
    assert np.max(np.abs(g-fd))<1e-6
def test_upper_bound_encloses_grid_points():
    x,y=run.generator('zero_balanced',80,10); box=np.array([[-10,1],[-5,5],[-5,5]])
    u=bounded_global.objective_upper(box,x,y)
    for x0 in [-9,-4,0]:
        for x1 in [-4,0,4]:
            assert run.val_score(np.array([x0,x1,0]),x,y)[0]<=u+1e-8
def test_subdivision_bound_monotonic():
    x,y=run.generator('rare_5pct',80,10);box=np.array([[-10,1],[-5,5],[-5,5]],float)
    parent=bounded_global.objective_upper(box,x,y)
    left=box.copy();left[0,1]=-4
    right=box.copy();right[0,0]=-4
    assert bounded_global.objective_upper(left,x,y)<=parent+1e-9
    assert bounded_global.objective_upper(right,x,y)<=parent+1e-9
def test_refuse_ambiguous():
    r=[json.loads(x) for x in (D/'results.jsonl').read_text().splitlines()]
    for x in r:
        assert x['decision'].startswith('REFUSED') if x['ambiguous'] else not x['production_accepted']
def test_all_receipts():
    assert independent_audit.audit()['audit']=='PASS'
def test_all_optimization_attempts():
    r=[json.loads(x) for x in (D/'results.jsonl').read_text().splitlines()]
    assert len(r)==192 and sum(x['attempts'] for x in r)==2304
def test_no_global_claims():
    for x in json.loads((D/'bounded_results.json').read_text()):
        assert not x['machine_certified'] and x['upper_minus_incumbent']>=0
def test_heldout_seeds_different_from_ch22():
    assert P['seed_namespace'] != 2026110222