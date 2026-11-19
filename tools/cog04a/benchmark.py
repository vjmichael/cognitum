"""Reproducible COG-04A diagnostic, not an efficacy/scaling claim."""
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
from cognitum.research.kan_trainable import Layer, Network, load_candidate, load_snapshot
from cognitum.mel import model_engines as me, model_reference as r, admission as a, function_verification as c
from cognitum.mel import cooperation as g, verified_graph as vg, uncertainty_pb2 as pb
from dataclasses import replace
from research_tests.mel04b.test_cooperation import fixture_plan, setup
from research_tests.mel05b.test_graph_acceptance import TOL


def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest_arrays(*arrays):
    return sha(b''.join(np.asarray(x,dtype='<f8').tobytes() for x in arrays))
def rmse(x,y):return float(np.sqrt(np.mean((x-y)**2)))
def make_layer(kind,degree,ins=1,outs=1,seed=3):
    knots=(np.r_[np.repeat(-1.,degree+1),[-.5,0.,.5],np.repeat(1.,degree+1)] if kind=='spline_clamped' else
           np.linspace(-1,1,2 if kind=='chebyshev' else 9))
    n=degree+1 if kind=='chebyshev' else len(knots) if kind=='rbf' else len(knots)-degree-1
    return Layer(kind,degree,np.tile(knots,(ins,1)),np.random.default_rng(seed).normal(0,.1,(outs,ins,n)),np.ones((outs,ins)),np.zeros(outs))


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    x=np.linspace(-.73,.73,81)[:,None];h=(x[:-1]+x[1:])/2
    f=lambda t:.4*np.sin(2*t)+.1*t*t
    train,test=f(x),f(h);rows=[];models={}
    np.savez(out/'diagnostic_split.npz',train_x=x,train_y=train,holdout_x=h,holdout_y=test)
    for kind,degree in [('rbf',0),('spline',3),('spline_clamped',3),('chebyshev',5)]:
        m=Network((make_layer(kind,degree),));fit=m.fit_linear(x,train,1e-8);models[kind]=fit
        raw,pin=fit.research_snapshot();(out/(kind+'.json')).write_bytes(raw)
        assert load_snapshot(raw,pin).research_snapshot()==(raw,pin)
        pcount=fit.layers[0].coefficients.size+fit.layers[0].bias.size
        poly=np.polynomial.Chebyshev.fit(x[:,0],train[:,0],pcount-1,domain=[-1,1]);baseline=rmse(poly(h[:,0]),test[:,0])
        row=dict(basis=kind,degree=degree,parameters=pcount,train_rmse=rmse(fit.evaluate(x)[0],train),holdout_rmse=rmse(fit.evaluate(h)[0],test),matched_parameter_chebyshev_polynomial_rmse=baseline,snapshot_sha256=pin)
        if kind in ('rbf','spline'):
            blob,d=fit.checkpoint_candidate();(out/(kind+'.pb')).write_bytes(blob)
            row['portable_checkpoint_sha256']=d;row['represented_binary32_holdout_rmse']=rmse(load_candidate(blob,d).evaluate(h)[0],test)
        rows.append(row)
    two=[]
    f2=lambda t:.2*t+.1*t*t
    for kind,degree in [('rbf',0),('spline',3),('spline_clamped',3),('chebyshev',3)]:
        m=Network((make_layer(kind,degree,1,2),make_layer(kind,degree,2,1,4)))
        fit,history=m.fit(x,f2(x),steps=300,rate=.35,ridge=1e-5)
        raw,pin=fit.research_snapshot();(out/(kind+'-two-layer.json')).write_bytes(raw)
        two.append(dict(basis=kind,updates=len(history)-1,initial_loss=history[0],final_loss=history[-1],holdout_rmse=rmse(fit.evaluate(h)[0],f2(h)),snapshot_sha256=pin,loss_history=list(history)))
    worker=[]
    for k in ('rbf','spline'):
        raw,d=models[k].checkpoint_candidate();approval=me.Approval(me.Checkpoint(raw),'local-benchmark-review');scope=a.Scope('cog04a','bench','cpu',k)
        raw_request=json.dumps(dict(tool='mel_kan_evaluate',arguments=dict(points=[[.125],[.432]])))
        with r.ReferenceTurn(scope,r.Allowed(('kan.evaluate',),approval)) as turn:
            feedback=turn.dispatch(raw_request);assert feedback['ok'],feedback
            worker.append(dict(basis=k,feedback=feedback,audit=turn.audit,admitted=len(turn.host._seen)))
        with r.ReferenceTurn(scope,r.Allowed(())) as turn:
            assert not turn.dispatch(raw_request)['ok'] and not turn.host._seen
            worker[-1]['unapproved_refused']=True
    raw,d=models['rbf'].checkpoint_candidate();app=me.Approval(me.Checkpoint(raw),'local-benchmark-review');scope=a.Scope('cog04a','bench','cpu','vfa')
    f0=c.KanFunction(app,'x');target=c.propose_vfa(f0);box=((-1.,1.),);tol=(1e-10,1e-10)
    cert=c.certify(scope,f0,target,box,tol);assert c.replay(scope,f0,cert,box,target=target,absolute_tolerance=tol)=='within'
    (out/'conversion-certificate.pb').write_bytes(cert.wire)
    train_x=np.linspace(-1,1,81)[:,None];fit=Network((make_layer('rbf',0),)).fit_linear(train_x,.1*train_x**2,1e-6)
    raw,d=fit.checkpoint_candidate();(out/'graph-checkpoint.pb').write_bytes(raw);app=me.Approval(me.Checkpoint(raw),'local-benchmark-review')
    plan=fixture_plan('trained-bench');plan=replace(plan,nodes=tuple(replace(z,approval=app) if type(z) is g.Kan else replace(z,at_least=.95) if type(z) is g.Threshold else z for z in plan.nodes))
    host,tokens=setup(plan)
    try:
        v=vg.execute_verified(host,plan,tokens,TOL);assert v.status=='verified' and v.reserved_calls==4,v.status
        w=pb.GraphWitness.FromString(v.witness);nodes={z.node_id:z for z in w.nodes};q=nodes['query']
        assert list(q.hamming_distance)==[2,0,0] and list(q.best_index)==[1,2]
        replay=vg.replay(plan,v.outcome,TOL,v.witness);(out/'three-engine-witness.pb').write_bytes(v.witness)
        graph=dict(status=v.status,worker_calls=v.reserved_calls,checkpoint_sha256=d,plan_sha256=plan.identity,witness_sha256=replay,hamming_distance=list(q.hamming_distance),best_index=list(q.best_index),receipts=[dict(id=z.node_id,operation=z.operation,request_sha256=z.worker.request_sha256,result_sha256=z.worker.result_sha256,result_hex=z.worker.result_frame.hex()) for z in v.outcome.nodes if z.worker])
    finally:host.close()
    # Deliberately mismatched threshold metadata is not a valid shared binary encoding.
    bad=replace(plan,id='bad-encoding',nodes=tuple(replace(z,at_least=.9) if type(z) is g.Threshold and z.id=='candidate' else z for z in plan.nodes))
    host,tokens=setup(bad)
    try:
        refused=vg.execute_verified(host,bad,tokens,TOL)
        assert refused.status=='invalid_exchange' and not refused.outcome and refused.reserved_calls==3
        graph['incompatible_encoding_refused']=True;graph['incompatible_encoding_worker_calls']=refused.reserved_calls
    finally:host.close()
    summary=dict(platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,train_rows=len(x),holdout_rows=len(h),train_sha256=digest_arrays(x,train),holdout_sha256=digest_arrays(h,test),disjoint=bool(set(x[:,0]).isdisjoint(h[:,0])),single_layer=rows,two_layer=two,worker_examples=worker,vfa_conversion=dict(verdict='within',tolerances=tol,certificate_sha256=sha(cert.wire)),three_engine=graph,production_enabled=False,native_lu_accepted=False,limitations=['synthetic interpolating held-out points only','parameter counts not matched across different KAN families','regularization differs from conventional polynomial fit','no efficacy or scaling claim','represented-function certificate not learned target error'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(json.dumps(dict(single_layer=rows,two_layer=[{k:v for k,v in z.items() if k!='loss_history'} for z in two],graph={k:v for k,v in graph.items() if k!='receipts'}),indent=2))
    return summary

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
