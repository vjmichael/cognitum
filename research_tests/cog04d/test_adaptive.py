import json, hashlib
from dataclasses import replace
from fractions import Fraction
import numpy as np
import pytest
from scipy.interpolate import BSpline
from cognitum.research.kan_trainable import Layer, Network, load_snapshot
from cognitum.research.kan_adaptive import refine, certify, prune, adaptive_fit, compose_fit
from cognitum.mel import polynomial_kan as p, model_reference as r, polynomial_model as pm, admission as a

def clamped(p=2, inputs=1, outputs=1, seed=3):
    grid=np.tile([-1.]*(p+1)+[0.]+[1.]*(p+1),(inputs,1)); co=np.random.default_rng(seed).uniform(-.35,.35,(outputs,inputs,p+2))
    return Network((Layer('spline_clamped',p,grid,co,np.ones((outputs,inputs)),np.zeros(outputs)),))

def cheb(co,mask=None,bias=None):
    co=np.asarray(co,float); o,i,_=co.shape
    return Network((Layer('chebyshev',co.shape[-1]-1,np.tile([-1.,1.],(i,1)),co,np.ones((o,i)) if mask is None else mask,np.zeros(o) if bias is None else bias),))

@pytest.mark.parametrize('degree',[1,2,3])
@pytest.mark.parametrize('knot',[-.71,.125,.83])
def test_transport(degree,knot):
    m=clamped(degree,2,2); n,c=refine(m,0,[knot,-knot]); assert max(c.output_error_upper)<1e-15
    assert m.research_snapshot()[1]==c.before_sha256 and n.research_snapshot()[1]==c.after_sha256
    x=np.linspace(-1,1,141);pts=np.column_stack((x,x[::-1]));l=m.layers[0];q=n.layers[0]
    for o in range(2):
        for i in range(2):
            old=BSpline(l.grid[i],l.coefficients[o,i],degree);new=old.insert_knot([knot,-knot][i]);
            assert np.allclose(q.coefficients[o,i],new.c,atol=2e-16,rtol=0)
            assert np.max(abs(old(x)-BSpline(q.grid[i],q.coefficients[o,i],degree)(x)))<1e-15
    assert np.max(abs(m.evaluate(pts)[0]-n.evaluate(pts)[0]))<1e-15
    for order in range(1,min(degree,2)+1):
        xx=np.array([[-.39,.41],[.61,-.29]])
        assert np.allclose(m.evaluate(xx,order)[-1],n.evaluate(xx,order)[-1],rtol=1e-11,atol=1e-13)

@pytest.mark.parametrize('knots',[[-1.],[1.],[0.],[.000001],[2.],[float('nan')],[],[.2,.3],[True]])
def test_bad_knots(knots):
    with pytest.raises(ValueError):refine(clamped(),0,knots)

def test_repeated_refinement_budget():
    m=clamped(3)
    for k in [.2,-.2,.4]:m,_=refine(m,0,[k])
    assert m.layers[0].grid.shape[1]==12
    with pytest.raises(ValueError):refine(m,0,[.6])

def test_transport_zero_budget_refusal():
    m=clamped(2);n,c=refine(m,0,[.37]);assert c.output_error_upper[0]>0
    with pytest.raises(ValueError):refine(m,0,[.37],0)

def test_prune_cumulative():
    m=cheb([[[0.,.3],[0.,.004],[0.,.005]]]);n,removed,c=prune(m,.006,3)
    assert removed==((0,0,1),) and .004<=c.output_error_upper[0]<=.006
    assert np.all(m.layers[0].mask==1) and not n.layers[0].mask[0,1]
    x=np.array([[0.,-1.,1.],[.5,1.,-1.]])
    assert np.max(abs(m.evaluate(x)[0]-n.evaluate(x)[0]))<=c.output_error_upper[0]+1e-15

def test_prune_masked_and_zero():
    m=cheb([[[0.,.5],[0.,0.],[0.,.9]]],mask=[[1,1,0]])
    n,gone,c=prune(m,0,16);assert gone==((0,0,1),) and c.output_error_upper==(0.,)
    assert np.array_equal(n.layers[0].mask,[[1,0,0]])

def test_prune_activation_propagation():
    feature=cheb([[[0.,.3],[0.,.01]]]);head=cheb([[[0.,0.,.4]]]);m=Network(feature.layers+head.layers)
    n,gone,c=prune(m,.033,1);assert gone==((0,0,1),);assert c.output_error_upper[0]>=.016
    pts=np.random.default_rng(1).uniform(-1,1,(200,2));assert np.max(abs(m.evaluate(pts)[0]-n.evaluate(pts)[0]))<=c.output_error_upper[0]+1e-15
    n,gone,c=prune(m,.005,1);assert not gone and c.output_error_upper==(0.,)

def test_refine_composed():
    m=Network(clamped(2).layers+cheb([[[0.,.2,.1]]]).layers);n,c=refine(m,0,[.37]);assert c.output_error_upper[0]<1e-14
    pts=np.linspace(-1,1,30)[:,None];assert np.max(abs(m.evaluate(pts)[0]-n.evaluate(pts)[0]))<1e-14

def test_domains_fail_closed():
    m=Network(cheb([[[0.,2.]]]).layers+cheb([[[0.,.5]]]).layers)
    with pytest.raises(ValueError,match='domain'):certify(m,m)
    with pytest.raises(ValueError):compose_fit(cheb([[[0.,2.]]]),cheb([[[0.,.1]]]),np.array([[0.],[.1]]),np.array([[0.],[.1]]))

@pytest.mark.parametrize('which',['shape','domain','layers','rbf'])
def test_incompatible(which):
    m=clamped(); l=m.layers[0]
    if which=='shape':n=clamped(inputs=2)
    elif which=='domain':n=Network((Layer(l.kind,l.degree,l.grid*2,l.coefficients,l.mask,l.bias),))
    elif which=='layers':n=Network(m.layers+m.layers)
    else:n=Network((Layer('rbf',0,[[-1,0,1]],[[[0,0,0]]],[[1]],[0]),))
    with pytest.raises(ValueError):certify(m,n)

def test_adaptive_learning():
    x=np.linspace(-1,1,101)[:,None];held=(x[:-1]+x[1:])/2;y=lambda x:np.exp(-30*(x-.38)**2)
    m=clamped(2);base=m.fit_linear(x,y(x));n,h=adaptive_fit(m,x,y(x),steps=4)
    assert len(h)>=2 and all(v['after_mse']<v['before_mse'] and max(v['transport_error_upper'])<1e-10 for v in h)
    assert np.mean((n.evaluate(held)[0]-y(held))**2)<np.mean((base.evaluate(held)[0]-y(held))**2)
    assert adaptive_fit(m,x,y(x),steps=0)[0].research_snapshot()==base.research_snapshot()

def test_compositional_learning_and_worker(tmp_path):
    # Independently learned feature from x^2; reuse frozen parameters on new task x^4.
    x=np.linspace(-1,1,81)[:,None];held=(x[:-1]+x[1:])/2
    feat=cheb([[[0,0,0]]]).fit_linear(x,x*x,ridge=0);head=cheb([[[0,0,0]]]);
    # Fit domain with margin around the true feature range; do not clip inputs.
    l=head.layers[0];head=Network((Layer(l.kind,l.degree,[[-1.1,1.1]],l.coefficients,l.mask,l.bias),))
    model=compose_fit(feat,head,x,x**4,ridge=0);assert model.layers[0] is feat.layers[0]
    rmse=float(np.sqrt(np.mean((model.evaluate(held)[0]-held**4)**2)));assert rmse<1e-12
    raw,h=model.research_snapshot();assert load_snapshot(raw,h).research_snapshot()==(raw,h)
    cp=p.export_checkpoint(model);app=p.Approval(cp,'local-reviewed-example');s=a.Scope('cog04d','lab','owner','turn');args={'points':[[.5],[-.25]],'order':2}
    with r.ReferenceTurn(s,r.Allowed((p.OP,),tolerance=1e-8,polynomial_approval=app)) as turn:
        out=turn.dispatch(r.canonical(dict(tool=pm.PUBLIC,arguments=args)));assert out['ok'],out
        v=out['result']['values'];expect=[.5**4,(-.25)**4,4*.5**3,4*(-.25)**3,12*.5**2,12*.25**2];assert np.allclose(v,expect,atol=1e-12,rtol=0)
        evidence={'checkpoint.pb':cp.wire,'request.pb':turn.last_call.wire,'result.pb':turn.last_receipt.result_frame,'snapshot.json':raw}
        for name,raw in evidence.items():(tmp_path/name).write_bytes(raw)
        (tmp_path/'composition.json').write_text(json.dumps(dict(rmse=rmse,values=v,expected=expect,feature_sha256=feat.research_snapshot()[1],checkpoint_sha256=cp.identity,sha256={k:hashlib.sha256(v).hexdigest() for k,v in evidence.items()}),indent=2))


def test_adapted_and_pruned_checkpoint_worker(tmp_path):
    # Learn a localized feature, retain a bounded pruned polynomial model;
    # test the reviewed runtime, not a standalone predictor substitute.
    x=np.linspace(-1,1,101)[:,None];held=(x[:-1]+x[1:])/2; target=lambda x:np.exp(-30*(x-.38)**2)
    original=clamped(2);base=original.fit_linear(x,target(x));adapt,h=adaptive_fit(original,x,target(x),steps=4)
    before=float(np.sqrt(np.mean((base.evaluate(held)[0]-target(held))**2)));after=float(np.sqrt(np.mean((adapt.evaluate(held)[0]-target(held))**2)))
    assert len(h)==4 and after<before*.1
    # separate two-edge control with a true nonzero weak edge
    m=cheb([[[0.,.3],[0.,.004]]]);pruned,gone,cert=prune(m,.005,1);assert gone==((0,0,1),)
    blobs={};rows=[]
    for label,model,pts,order in [('refined',adapt,[[.331],[.438]],2),('pruned',pruned,[[.2,.8]],1)]:
        cp=p.export_checkpoint(model);app=p.Approval(cp,'reviewed-local-'+label);s=a.Scope('cog04d','lab','owner','turn');args={'points':pts,'order':order}
        with r.ReferenceTurn(s,r.Allowed((p.OP,),tolerance=1e-8,polynomial_approval=app)) as t:
            out=t.dispatch(r.canonical(dict(tool=pm.PUBLIC,arguments=args)));assert out['ok'],out
            vals=out['result']['values'];expected=np.concatenate([v.ravel() for v in model.evaluate(pts,order)])
            assert np.allclose(vals,expected,atol=1e-10,rtol=0)
            blobs.update({label+'.checkpoint.pb':cp.wire,label+'.request.pb':t.last_call.wire,label+'.result.pb':t.last_receipt.result_frame,label+'.snapshot.json':model.research_snapshot()[0]})
            rows.append(dict(label=label,checkpoint_sha256=cp.identity,values=vals))
    for name,raw in blobs.items():(tmp_path/name).write_bytes(raw)
    (tmp_path/'adaptive.json').write_text(json.dumps(dict(training_points=101,heldout_points=100,baseline_rmse=before,adaptive_rmse=after,history=h,pruned_edges=gone,prune_error_upper=cert.output_error_upper,calls=len(rows),rows=rows,sha256={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()}),indent=2))


def test_certificate_binds_mask_and_bias():
    m=cheb([[[0.,.4]]]);l=m.layers[0];n=Network((Layer(l.kind,l.degree,l.grid,l.coefficients,[[0]],[.125]),));c=certify(m,n)
    assert c.before_sha256!=c.after_sha256 and c.output_error_upper[0]>=.525
    # A new independently replayed certificate is not equal to the old one.
    assert certify(m,m)!=c and certify(m,n)==c


def test_exact_dyadic_transport():
    m=Network((Layer('spline_clamped',1,[[-1,-1,0,1,1]],[[[-.5,0.,.5]]],[[1]],[0.]),));n,c=refine(m,0,[.5],max_error=0.)
    assert c.output_error_upper==(0.,) and n.layers[0].coefficients[0,0].tolist()==[-.5,0,.25,.5]
