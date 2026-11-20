"""Fresh J/K/L fits, two actual reference Runtime plugins, independent numerical oracle."""
from fractions import Fraction as Q
from math import prod
from pathlib import Path
from dataclasses import asdict
import json,time
import numpy as np
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import tensor_field as f,tensor_field_pb2 as pb,tensor_cooperation as n
from cognitum.research import kan_elliptic_learning as jl,kan_transient_learning as kl,kan_spacetime_learning as ll
from tools.cog04j.benchmark import cases as jc
from tools.cog04k.benchmark import cases as kc
from tools.cog04l.benchmark import cases as lc

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
    for stage,learning,cases,i in [('J',jl,jc,1),('K',kl,kc,3),('L',ll,lc,3)]:
        name,p,tol=cases()[i];fit=learning.fit(p,tol);f.need(fit.converged,'fit failed');cp=f.export(p,fit.model,fit.certificate)
        mod,_,_,cert=f.restore(cp);orders,weights=n._stencil(mod,p);rank=len(orders[0]);point=(.375,)*rank
        reg=Registry();rt=Runtime(reg)
        for op,plugin in n.FACTORIES.items():
            m=reg.install(plugin,enabled=True);reg.nominate(op,m.name)
        scope=n.Scope('session-'+stage,'scientific','reviewed','turn-'+stage);a=n.Admission(rt,scope.session,enabled=True,reviewed=n.selection());pin=a.approve(scope,n.Approval(cp,'review-'+stage));token=a.issue(scope,pin,n.Limits(timeout_ms=10000),cooperative=True)
        time0=time.perf_counter();r=a.residual(scope,token,point,request_id='residual-'+stage);f.need(n.replay_residual(cp,r,scope),'cooperation verification')
        # Separate numerical engine: SciPy spline evaluation, direct monomial forcing.
        ev=lambda d:float((learning.evaluate(fit.model,np.array([point]),d) if stage=='J' else learning.evaluate(p,fit.model,np.array([point]),d))[0])
        ref=sum(float(w)*ev(d) for w,d in zip(weights,orders))-sum(float(v[-1])*prod(x**k for x,k in zip(point,v[:-1])) for v in p.forcing)
        error=abs(ref-float(Q(r.exact_residual)));f.need(error<=1e-10,'independent numerical residual mismatch')
        q=f.make_request(cp,pb.BOX_INTEGRAL,(0,)*rank,upper=(1,)*rank,request_id='integral-'+stage,correlation_id=scope.turn)
        receipt=a.call(scope,token,q);f.need(n.replay_receipt(cp,q,receipt,scope),'integral verification')
        f.need(len(rt.trace.events)==len(orders)+2 and all(e['execution_status']=='completed' for e in rt.trace.events),'missing actual worker trace')
        (out/f'{stage}.checkpoint.pb').write_bytes(cp);(out/f'{stage}.integral.request.pb').write_bytes(q);(out/f'{stage}.integral.result.pb').write_bytes(receipt.result)
        for idx,(req,w) in enumerate(zip(r.requests,r.field_receipts)):
            (out/f'{stage}-{idx}.request.pb').write_bytes(req);(out/f'{stage}-{idx}.result.pb').write_bytes(w.result)
        (out/f'{stage}.symbolic.request.json').write_text(r.symbolic_request,encoding='utf8');(out/f'{stage}.symbolic.result.json').write_bytes(r.symbolic_receipt.result)
        meta=lambda rec:{**{k:v for k,v in asdict(rec).items() if k!='result'},'receipt_sha256':rec.identity,'result_sha256':rec.result_sha256}
        (out/f'{stage}.receipts.json').write_text(json.dumps(dict(scope=asdict(scope),plan_id=r.plan_id,point=point,checkpoint_sha256=pin,exact_residual=r.exact_residual,residual_upper=r.certified_residual_upper,field=[meta(w) for w in r.field_receipts],symbolic=meta(r.symbolic_receipt),integral=meta(receipt),trace=rt.trace.events),indent=2)+'\n',encoding='utf8')
        rows.append(dict(stage=stage,case=name,rank=rank,worker_calls=len(rt.trace.events),tensor_calls=len(orders)+1,symbolic_calls=1,receipt_replay=True,exact_residual=float(Q(r.exact_residual)),oracle_difference=error,certificate_residual_upper=float(cert.residual_upper),solution_error_upper=float(cert.solution_error_upper),seconds=time.perf_counter()-time0));a.close()
    (out/'benchmark.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8');return rows

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);print(run(p.parse_args().out))
