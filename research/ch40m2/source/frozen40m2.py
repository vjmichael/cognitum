"""CH40-M.2 immutable CH23 case loader and standard numerical objective.
Only the independent CH40 rational_kernel40d evaluator may assert a verified bound.
"""
from __future__ import annotations
import hashlib, json, math, sys
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.special import expit, log_expit

@dataclass(frozen=True)
class Case:
    name: str
    source_sha256: str
    certificate: dict
    x: np.ndarray
    n: np.ndarray
    s: np.ndarray
    bounds: np.ndarray
    incumbent: np.ndarray


def load_cases(traces:Path,pins:Path) -> list[Case]:
    anchors=json.loads(pins.read_text())['cases']
    trusted={v['case']:v['trace_sha256'] for v in anchors}
    if len(trusted)!=15 or len(anchors)!=15:raise ValueError('Expected exactly 15 unique immutable SHA-256 pins')
    paths=sorted(traces.glob('*_127_original_mpfr_trace.json'))
    if len(paths)!=15:raise ValueError(f'Expected 15 frozen traces, got {len(paths)}')
    result=[]
    for p in paths:
        name=p.name.removesuffix('_127_original_mpfr_trace.json')
        data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
        if trusted.get(name)!=digest:raise ValueError(f'Frozen source hash mismatch: {name}')
        cert=json.loads(data)['certificate']
        rows=cert['model']['rows'];d=cert['model']['d']
        x=np.array([[float(t) for t in r['x']] for r in rows],float)
        n=np.array([float(r['n']) for r in rows]);s=np.array([float(r['s']) for r in rows]);
        bounds=np.array([[float(v) for v in pair] for pair in cert['root_box']],float)
        inc=np.array([float(v) for v in cert['incumbent']],float)
        if d!=3 or x.shape!=(len(rows),3) or len(rows) not in (80,160):raise ValueError('Unexpected original model')
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(bounds)) or not np.all(np.isfinite(inc)):raise ValueError('Nonfinite source')
        if (bounds[:,0]>inc).any() or (bounds[:,1]<inc).any():raise ValueError('Original point outside root')
        if any((r['n']<=0 or r['s']<0 or r['s']>r['n']) for r in rows):raise ValueError('Invalid count')
        result.append(Case(name,digest,cert,x,n,s,bounds,inc))
    if set(c.name for c in result)!=set(trusted):raise ValueError('Original case identity mismatch')
    return result


def float_objective(case:Case,b):
    b=np.asarray(b,float)
    if b.shape!=(3,) or not np.isfinite(b).all() or (b<case.bounds[:,0]).any() or (b>case.bounds[:,1]).any():return float('-inf')
    z=case.x@b;p=expit(z);w=case.n*p*(1-p)
    info=case.x.T@(case.x*w[:,None]);sign,logdet=np.linalg.slogdet(info)
    if sign<=0 or not math.isfinite(logdet):return float('-inf')
    return float(np.dot(case.s,log_expit(z))+np.dot(case.n-case.s,log_expit(-z))+0.5*logdet)


def validated_candidate(case:Case,b):
    b=np.asarray(b,float)
    return bool(b.shape==(3,) and np.isfinite(b).all() and (b>=case.bounds[:,0]).all() and (b<=case.bounds[:,1]).all() and math.isfinite(float_objective(case,b)))


def point_lower(case:Case,b,reference_dir:Path):
    if not validated_candidate(case,b):raise ArithmeticError('Candidate is not a finite feasible point')
    sys.path.insert(0,str(reference_dir))
    from rational_kernel40d import point_objective
    point=[F(str(float(t))) for t in b]
    return point_objective(case.certificate,point)

