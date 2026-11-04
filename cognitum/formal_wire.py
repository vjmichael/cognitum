"""C10 typed Protobuf adapter. Inert reference; no Lu host registration.

Status and request hash are correlation-only and never imply host authorization.
Only constrained canonical binary frames are admitted.
"""
from hashlib import sha256
from google.protobuf.message import DecodeError

from .proto import formal_pb2 as pb
from .formal_smt import (
    IntVar, LinearAtom, SMTProblem, validate, solve, satisfies
)

MAX_REQUEST=16384
MAX_RESULT=4096


def _read(data, cls, limit):
    if type(data) is not bytes or not 0<len(data)<=limit:
        raise ValueError("invalid formal Protobuf size")
    obj=cls()
    try:
        obj.ParseFromString(data)
    except DecodeError as exc:
        raise ValueError("invalid formal Protobuf encoding") from exc
    known=cls()
    known.CopyFrom(obj)
    known.DiscardUnknownFields()
    if obj!=known or obj.SerializeToString(deterministic=True)!=data:
        raise ValueError("noncanonical/unknown/duplicate formal Protobuf")
    return obj


def _write(obj, limit):
    data=obj.SerializeToString(deterministic=True)
    if not 0<len(data)<=limit:
        raise ValueError("oversized formal Protobuf")
    return data


def to_problem(req):
    if req.schema_version!=1 or req.backend not in ("z3","cvc5","exhaustive"):
        raise ValueError("invalid formal schema/backend")
    variables=tuple(IntVar(v.name,v.lower,v.upper) for v in req.variables)
    atoms=tuple(LinearAtom(tuple((t.name,t.coefficient) for t in atom.terms),
                           atom.relation,atom.rhs) for atom in req.constraints)
    return validate(SMTProblem(variables,atoms))


def execute(request: bytes) -> bytes:
    req=_read(request,pb.VerifyRequest,MAX_REQUEST)
    problem=to_problem(req)
    if not 1<=req.timeout_ms<=10000:
        raise ValueError("formal time budget missing/out of bounds")
    result=solve(problem,backend=req.backend,timeout_ms=req.timeout_ms)
    if req.proof_required and result.status=="UNSAT_UNVERIFIED":
        # The optional Carcara certificate route is a separate trusted-host
        # admission step. This ordinary wire endpoint cannot claim its result.
        from .formal_smt import SMTResult
        result=SMTResult("UNKNOWN",backend=req.backend,
                         limitation="proof_required_but_not_certified")
    if result.status=="SAT" and not satisfies(problem,result.witness):
        raise ValueError("invalid solver witness")
    if result.status not in ("SAT","UNSAT_EXHAUSTIVE","UNSAT_UNVERIFIED",
                             "UNKNOWN","UNSUPPORTED"):
        raise ValueError("unsupported formal result status")
    if result.status!="SAT" and result.witness:
        raise ValueError("forbidden non-SAT witness")
    reply=pb.VerifyResult(
        schema_version=1,status=result.status,witness=result.witness,
        backend=result.backend,assurance=result.assurance,
        limitation=result.limitation,
        request_sha256=sha256(request).hexdigest(),
    )
    return _write(reply,MAX_RESULT)


def decode_result(frame: bytes, request: bytes):
    req=_read(request,pb.VerifyRequest,MAX_REQUEST)
    problem=to_problem(req)
    result=_read(frame,pb.VerifyResult,MAX_RESULT)
    if (result.schema_version!=1
            or result.request_sha256!=sha256(request).hexdigest()
            or result.backend!=req.backend
            or result.status not in ("SAT","UNSAT_EXHAUSTIVE","UNSAT_UNVERIFIED",
                                     "UNKNOWN","UNSUPPORTED")):
        raise ValueError("formal result mismatch")
    if result.assurance not in ("solver_reported","witness_rechecked",
                                "independent_exhaustion"):
        raise ValueError("unknown formal result assurance")
    if result.status=="SAT":
        if (result.assurance!="witness_rechecked"
                or not satisfies(problem,tuple(result.witness))):
            raise ValueError("invalid formal SAT witness")
    elif result.witness:
        raise ValueError("non-SAT result contains witness")
    if result.status=="UNSAT_EXHAUSTIVE" and result.assurance!="independent_exhaustion":
        raise ValueError("exhaustion result lacks correct assurance")
    if result.status=="UNSAT_UNVERIFIED" and result.assurance!="solver_reported":
        raise ValueError("unverified UNSAT cannot claim proof assurance")
    if result.status=="UNSAT_EXHAUSTIVE":
        from .formal_smt import exhaustive
        if exhaustive(problem)!=():
            raise ValueError("UNSAT claim lacks independent exhaustive proof")
    # Cannot independently certify solver-reported UNSAT, UNKNOWN or missing backend.
    return result
