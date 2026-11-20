"""Independent continuum reference checks; never a source of rigorous enclosure status."""
from fractions import Fraction as Q
from math import pi
import json
import numpy as np
from tools.cog04r.oracle import reference
from cognitum.research import kan_certified_spectrum as u

def verify(problem,cuts,raw,certificate,ref):
    u.need(u.replay(problem,cuts,certificate),'rational replay')
    baseline=u.r.assemble(problem,cuts)
    u.need(raw==baseline,'optimized assembly byte equivalence')
    d=json.loads(certificate);rows=d['rows']
    values=ref['values'];bounds=[]
    for v,row in zip(values,rows):
        lo,hi,x,err=map(Q,(row['lower'],row['upper'],row['approximation'],row['absolute_error_upper']))
        u.need(err==max(abs(x-lo),abs(x-hi)) and lo<=hi,'exact error bound identity')
        # Shooting is numerical. Only a consistency check, with tolerance, not the proof.
        tol=2e-8*max(1.,abs(v))
        u.need(float(lo)-tol<=v<=float(hi)+tol,'independent shooting reference consistency')
        bounds.append(dict(lower=float(lo),upper=float(hi),width=float(hi-lo),
            absolute_error_bound=float(err),shooting_value=v))
    return bounds
