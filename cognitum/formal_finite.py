"""C10 P3: independent, bounded exhaustive verification for finite Bool/BV SMT.

No external solver, code execution, scientific semantics, or human formalization
is trusted. Returns UNKNOWN for unsupported or too-large finite domains.
Recomputing a finite certificate enumerates every value, not a solver claim.
"""
from __future__ import annotations
import hashlib
import itertools
from .formal_backend import compile_run, MAX_INPUT, MAX_OUTPUT
from .formal_solver import _decode, _encode
from .proto import formal_backend_pb2 as b
from .proto import formal_advanced_pb2 as a

MAX_CASES=4096

class NotFinite(ValueError):pass


def _eval(node, vals):
    kind=node[0]
    if kind=='var': return vals[node[1]]
    if kind=='bool': return node[1]
    if kind=='bv': return node[1]
    # By construction this checker does NOT implement nonfinite number theories.
    if kind!='app':raise NotFinite('UNSUPPORTED_PROOF_THEORY')
    _,op,children,sort=node
    v=[_eval(c,vals) for c in children]
    if op==b.AND:return all(v)
    if op==b.OR:return any(v)
    if op==b.NOT:return not v[0]
    if op==b.IMPLIES:return not v[0] or v[1]
    if op==b.XOR:return bool(v[0])!=bool(v[1])
    if op==b.EQ:return v[0]==v[1]
    if op==b.ITE:return v[1] if v[0] else v[2]
    width=sort[1];mask=(1<<width)-1 if width else None
    if op==b.BVAND:return v[0]&v[1]
    if op==b.BVOR:return v[0]|v[1]
    if op==b.BVNOT:return (~v[0])&mask
    if op==b.BVADD:return (v[0]+v[1])&mask
    if op==b.BVULT:return v[0]<v[1]
    raise NotFinite('UNSUPPORTED_PROOF_OPERATOR')


def _check_formula(run,limit=MAX_CASES):
    if run.schema_version!=1:raise ValueError('INVALID_RUN_VERSION')
    _,symbols,trees=compile_run(run)
    if any(t[0] not in (b.BOOL,b.BV) for t in symbols.values()):raise NotFinite('UNSUPPORTED_PROOF_THEORY')
    bits=sum(1 if t[0]==b.BOOL else t[1] for t in symbols.values())
    if bits>12 or 2**bits>limit:raise NotFinite('FINITE_PROOF_BUDGET')
    ranges=[(False,True) if t[0]==b.BOOL else range(1<<t[1]) for t in symbols.values()]
    digest=hashlib.sha256(b'C10-finite-exhaustive-v1\0'+run.SerializeToString(deterministic=True))
    total=0
    for row in itertools.product(*ranges):
        env=dict(zip(symbols,row))
        state=all(_eval(t,env) is True for t in trees)
        total+=1
        digest.update(b'1' if state else b'0')
        if state: return False,total,digest.digest()
    return True,total,digest.digest()


def prove_finite_frame(frame:bytes)->bytes:
    run=_decode(frame,b.BackendRun,MAX_INPUT)
    result=a.FiniteCertificate(schema_version=1,request_sha256=hashlib.sha256(frame).digest())
    try:
        verdict,count,digest=_check_formula(run)
        result.cases_checked=count;result.exhaustive_sha256=digest
        result.unsat_verified=verdict
        result.reason_code='FINITE_UNSAT_EXHAUSTIVELY_CHECKED' if verdict else 'FINITE_SAT_COUNTEREXAMPLE_EXISTS'
    except (ValueError,NotFinite) as e:
        result.reason_code=str(e)[:64]
    return _encode(result,MAX_OUTPUT)


def verify_finite_frame(frame:bytes,certificate_frame:bytes)->bool:
    try:
        run=_decode(frame,b.BackendRun,MAX_INPUT)
        result=_decode(certificate_frame,a.FiniteCertificate,MAX_OUTPUT)
        if result.schema_version!=1 or not result.unsat_verified or result.request_sha256!=hashlib.sha256(frame).digest():
            return False
        verdict,count,digest=_check_formula(run)
        return (verdict and result.cases_checked==count and result.exhaustive_sha256==digest and
                result.reason_code=='FINITE_UNSAT_EXHAUSTIVELY_CHECKED')
    except (ValueError,NotFinite):return False
