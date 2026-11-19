"""Deterministic independent scalar oracle, not a certified or speed benchmark."""
import math
import numpy as np
from cognitum.mel.objects import gaussian,points,MathObject
from cognitum.mel.vfa import VFAPlugin,request_payload


def run():
    rows=[];plugin=VFAPlugin()
    for d in (1,2,4,8):
        for t in (1,8,32):
            for n in (1,8,32):
                rng=np.random.default_rng(d*100000+t*100+n)
                c=rng.uniform(-1,1,(t,d));w=rng.uniform(-.8,.8,t);s=rng.uniform(.3,1.8,(t,d));x=rng.uniform(-2,2,(n,d));a=.125
                f=gaussian(c.tolist(),s.tolist(),w.tolist(),constant=a,axes=[(f'x{i}','1') for i in range(d)],domain=[(-2,2)]*d,output_unit='1');p=points(f,x.tolist());req=request_payload(f,p)
                outputs={op:MathObject(plugin.handle(op,req)['object']) for op in ('vfa.evaluate','vfa.gradient')}
                ref=[];grad=[]
                for q in x:
                    terms=[float(w[i])*math.exp(-.5*math.fsum(((float(q[j])-float(c[i,j]))/float(s[i,j]))**2 for j in range(d))) for i in range(t)]
                    ref.append(math.fsum([a]+terms))
                    grad.extend(math.fsum(-terms[i]*(float(q[j])-float(c[i,j]))/float(s[i,j])**2 for i in range(t)) for j in range(d))
                e=float(np.max(np.abs(np.array(outputs['vfa.evaluate'].values)-ref)));g=float(np.max(np.abs(np.array(outputs['vfa.gradient'].values)-grad)))
                if e>5e-13 or g>5e-13:raise AssertionError('scalar oracle mismatch')
                rows.append(dict(dimension=d,terms=t,points=n,value_max_abs_error=e,gradient_max_abs_error=g,function_wire_bytes=len(f.wire),coordinates_wire_bytes=len(p.wire),gradient_wire_bytes=len(outputs['vfa.gradient'].wire)))
    return rows
