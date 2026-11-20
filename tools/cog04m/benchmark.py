"""Fresh fitted J/K/L checkpoints across an actual isolated subprocess boundary."""
from fractions import Fraction as Q
from pathlib import Path
import subprocess,sys,time,json,os
import numpy as np
from cognitum.mel import tensor_field as f,tensor_field_pb2 as pb
from cognitum.research import kan_elliptic_learning as jl,kan_transient_learning as kl,kan_spacetime_learning as ll
from tools.cog04j.benchmark import cases as jc
from tools.cog04k.benchmark import cases as kc
from tools.cog04l.benchmark import cases as lc

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
    for stage,learning,cases,i in [('J',jl,jc,1),('K',kl,kc,3),('L',ll,lc,3)]:
        name,p,tol=cases()[i];model=learning.fit(p,tol);f.need(model.converged,'fit failed');cp=f.export(p,model.model,model.certificate)
        rank=3 if stage=='L' else 2;point=(.375,)*rank;d=(0,)*rank
        reqs=[f.make_request(cp,pb.POINT,point,derivative=d,request_id=stage+'-value'),f.make_request(cp,pb.POINT,point,derivative=(1,)+(0,)*(rank-1),request_id=stage+'-dx'),f.make_request(cp,pb.BOX_INTEGRAL,(0,)*rank,upper=(1,)*rank,request_id=stage+'-integral')]
        values=[];start=time.perf_counter()
        for ix,req in enumerate(reqs):
            data=f.canonical(dict(checkpoint=f.carrier(cp),request=f.carrier(req)))
            result=subprocess.run([sys.executable,'-m','tools.cog04m.worker'],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40,check=True).stdout
            f.need(f.replay(cp,req,result),'independent result replay')
            r=pb.Result.FromString(result);values.append(float(Q(r.exact_value)))
            (out/f'{stage}-{ix}.request.pb').write_bytes(req);(out/f'{stage}-{ix}.result.pb').write_bytes(result)
        # Independent numerical evaluation uses SciPy fitting/evaluation; integration
        # oracle uses Gauss nodes per cell, exactly integrating piecewise cubics.
        evaluate=lambda pts,der:learning.evaluate(model.model,pts,der) if stage=='J' else learning.evaluate(p,model.model,pts,der)
        refs=[float(evaluate(np.array([point]),d)[0]),float(evaluate(np.array([point]),(1,)+(0,)*(rank-1))[0])]
        mod,_,m,_=f.restore(cp);cuts,_,_=f._tensor(mod,m)
        from itertools import product
        nodes,weights=np.polynomial.legendre.leggauss(3);axes=[]
        for c in cuts:
            edges=(0,*c,1);axes.append([(float((a+b)/2+(b-a)*x/2),float((b-a)*w/2)) for a,b in zip(edges,edges[1:]) for x,w in zip(nodes,weights)])
        grid=list(product(*axes));pts=np.array([[x for x,w in row] for row in grid]);ws=np.array([np.prod([w for x,w in row]) for row in grid]);refs.append(float(np.dot(evaluate(pts,d),ws)))
        error=max(abs(x-y) for x,y in zip(values,refs));f.need(error<=1e-11,'numerical independent oracle mismatch')
        (out/f'{stage}.checkpoint.pb').write_bytes(cp)
        rows.append(dict(stage=stage,case=name,shape=list(f._tensor(mod,m)[1]),checkpoint_bytes=len(cp),reference_worker_roundtrips=3,independent_replay=True,represented_oracle_max_difference=error,certified_pde_error_upper=float(model.certificate.solution_error_upper),seconds=time.perf_counter()-start))
    (out/'benchmark.json').write_text(json.dumps(rows,indent=2)+'\n');return rows
