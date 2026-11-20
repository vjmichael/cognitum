"""Analytic represented tensor field fixtures, not learned-target evidence."""
from itertools import product
from cognitum.mel import tensor_field as f


def checkpoint(mod,p,m):
    return f.export(p,m,mod.assess(p,m))


def elliptic(*,refined=False,scale=1):
    x=(0,.5,1,.5,0) if refined else (0,1,1,0);y=(0,1,1,0)
    p=f.j.Problem(1,1,0,())
    m=f.j.Model((.5,) if refined else (),(),tuple(scale*a*b for a,b in product(x,y)))
    return checkpoint(f.j,p,m)


def transient(*,correction=False):
    p=f.k.Problem(1,0,(),(0,3,-3))
    coeff=tuple(a*b*int(correction) for a,b in product((0,1,1,0),(0,1,2,3)))
    return checkpoint(f.k,p,f.k.Model(f.j.Model((),(),coeff)))


def spacetime(*,correction=False):
    initial=((1,1,9),(1,2,-9),(2,1,-9),(2,2,9))
    p=f.l.Problem(1,1,0,(),initial)
    coeff=tuple(a*b*c*int(correction) for a,b,c in product((0,1,1,0),(0,1,1,0),(0,1,2,3)))
    return checkpoint(f.l,p,f.l.Model(((),(),()),coeff))


def baseline(raw):
    mod,p,m,cert=f.restore(raw)
    if mod is f.j:new=mod.Model((),(),(0,)*16)
    elif mod is f.k:new=mod.Model(f.j.Model((),(),(0,)*16))
    else:new=mod.Model(((),(),()),(0,)*64)
    return checkpoint(mod,p,new)
