"""Independent represented probe shapes, distinct from learned solutions."""
from itertools import product
from tools.cog04o.fixtures import checkpoint
from cognitum.mel import tensor_field as f

def probe(stage):
    x=(0,1,0,0);y=(0,0,1,0);t=(0,1,0,0)
    if stage=='J':
        return checkpoint(f.j,f.j.Problem(1,1,0,()),f.j.Model((),(),tuple(a*b for a,b in product(x,y))))
    if stage=='K':
        return checkpoint(f.k,f.k.Problem(1,0,(),(0,)),f.k.Model(f.j.Model((),(),tuple(a*b for a,b in product(x,t)))))
    if stage=='L':
        return checkpoint(f.l,f.l.Problem(1,1,0,(),()),f.l.Model(((),(),()),tuple(a*b*c for a,b,c in product(x,y,t))))
    raise ValueError('unknown probe stage')
