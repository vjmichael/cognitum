"""C13 P4 host-fenced rank R-hat, bulk/tail ESS, MCSE using real ArviZ.

Diagnostics describe *supplied* chains; no authenticity, correctness, mixing,
or convergence certification can be inferred from these numbers alone.
"""
from __future__ import annotations
import hashlib
import math
import time
from cognitum.planning import TRACE, NAME, _encode, _decode
from cognitum.proto import probability_diagnostics_pb2 as p

MAX_FRAME=500000
MAX_TIMEOUT=20000
MAX_PARAMETERS=8
MAX_CHAINS=8
MAX_DRAWS=2000


def _parse(raw):
    if len(raw)>MAX_FRAME:raise ValueError('DIAGNOSTICS_FRAME_TOO_LARGE')
    req=_decode(raw,p.DiagnosticsRequest)
    if (req.schema_version!=1 or not TRACE.fullmatch(req.trace_id) or
        not 1<=req.timeout_ms<=MAX_TIMEOUT or not 1<=len(req.parameters)<=MAX_PARAMETERS):
        raise ValueError('INVALID_DIAGNOSTICS_REQUEST')
    names=set()
    for variable in req.parameters:
        if not NAME.fullmatch(variable.parameter) or variable.parameter in names or not 2<=len(variable.chains)<=MAX_CHAINS:
            raise ValueError('INVALID_CHAIN_SHAPE')
        names.add(variable.parameter)
        count=len(variable.chains[0].values)
        if not 20<=count<=MAX_DRAWS or any(len(ch.values)!=count for ch in variable.chains):
            raise ValueError('INVALID_CHAIN_LENGTH')
        if any(not math.isfinite(v) or abs(v)>1e12 for ch in variable.chains for v in ch.values):
            raise ValueError('INVALID_DRAWS')
    return req


def _calculate(req):
    import numpy as np
    import arviz as az
    rows=[]
    for var in req.parameters:
        draws=np.asarray([list(ch.values) for ch in var.chains],dtype=float)
        # ArviZ computes rank-normalized split R-hat and robust bulk/tail ESS.
        fields=(float(az.rhat(draws,method='rank')),
                float(az.ess(draws,method='bulk')),
                float(az.ess(draws,method='tail',prob=(.05,.95))),
                float(az.mcse(draws,method='mean')))
        if any(not math.isfinite(v) or v<=0 for v in fields):
            raise ArithmeticError('UNDEFINED_CHAIN_DIAGNOSTICS')
        rows.append(dict(parameter=var.parameter,chains=len(var.chains),
                         draws_per_chain=len(var.chains[0].values),
                         rhat_rank=fields[0],ess_bulk=fields[1],ess_tail=fields[2],mcse_mean=fields[3]))
    return str(az.__version__),rows


def run_diagnostics_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    out=p.DiagnosticsResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),reason_code='INVALID_FRAME')
    try:
        req=_parse(raw);out.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('DIAGNOSTICS_DISABLED')
        version,rows=_calculate(req)
        out.backend_version='arviz-'+version
        for row in rows:out.parameters.add(**row)
        out.status=p.DIAGNOSTICS_SUCCESS;out.reason_code='OBSERVATIONAL_CHAIN_DIAGNOSTICS_ONLY'
        if time.monotonic_ns()-start>req.timeout_ms*1000000:
            out.Clear();out.schema_version=1;out.request_sha256=hashlib.sha256(raw).digest()
            out.status=p.DIAGNOSTICS_UNKNOWN;out.reason_code='TIME_LIMIT_EXCEEDED'
    except (ValueError,TypeError,OverflowError) as exc:
        out.status=p.DIAGNOSTICS_REJECTED;out.reason_code=str(exc)[:100]
    except (ArithmeticError,ImportError,RuntimeError) as exc:
        out.Clear();out.schema_version=1;out.request_sha256=hashlib.sha256(raw).digest()
        out.status=p.DIAGNOSTICS_UNKNOWN;out.reason_code='DIAGNOSTICS_UNAVAILABLE'
    out.wall_ns=time.monotonic_ns()-start
    return _encode(out)


def verify_diagnostics_receipt(raw,result_frame):
    receipt=p.DiagnosticsReceipt(request_sha256=hashlib.sha256(raw).digest(),
                                result_sha256=hashlib.sha256(result_frame).digest())
    try:
        req=_parse(raw);res=_decode(result_frame,p.DiagnosticsResult)
        if (res.schema_version!=1 or res.request_sha256!=receipt.request_sha256 or
            res.trace_id!=req.trace_id or res.status!=p.DIAGNOSTICS_SUCCESS or
            res.reason_code!='OBSERVATIONAL_CHAIN_DIAGNOSTICS_ONLY' or
            len(res.parameters)!=len(req.parameters)):return receipt
        version,rows=_calculate(req)
        if res.backend_version!='arviz-'+version:return receipt
        for given,expected in zip(res.parameters,rows):
            for key in ('parameter','chains','draws_per_chain'):
                if getattr(given,key)!=expected[key]:return receipt
            for key in ('rhat_rank','ess_bulk','ess_tail','mcse_mean'):
                val=getattr(given,key);ref=expected[key]
                if not math.isfinite(val) or abs(val-ref)>1e-7*max(1,abs(ref)):return receipt
        receipt.evidence_valid=True;receipt.assurance='ARVIZ_RECOMPUTED_NOT_CONVERGENCE_PROOF'
    except (ValueError,TypeError,OverflowError,ArithmeticError,ImportError,RuntimeError):pass
    return receipt


def make_diagnostics_audit(raw,result_frame,receipt=None):
    checked=verify_diagnostics_receipt(raw,result_frame)
    if receipt is not None and receipt!=checked:raise ValueError('FORGED_RECEIPT')
    res=_decode(result_frame,p.DiagnosticsResult)
    return p.DiagnosticsAudit(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
         result_sha256=hashlib.sha256(result_frame).digest(),trace_id=res.trace_id,
         status=res.status,backend_version=res.backend_version,parameter_count=len(res.parameters),
         verified=checked.evidence_valid,wall_ns=res.wall_ns,reason_code=res.reason_code)
