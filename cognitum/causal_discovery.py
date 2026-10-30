"""C14 P3B: bounded PC-stable undirected Gaussian CI *candidate skeleton*.

This reference deliberately implements NO edge orientations. Conditional
independence tests are statistical screening under linear-Gaussian,
causal-Markov/faithfulness assumptions, not proof of causation. A separately
isolated causal-learn runtime is the mature research candidate, unavailable here.
"""
from __future__ import annotations
from itertools import combinations
import hashlib
import math
import re
import time
from cognitum.causal_estimation import _decode
from cognitum.planning import TRACE,_encode
from cognitum.proto import causal_discovery_pb2 as d

BACKEND='c14-pc-stable-gaussian-undirected-reference'
VERSION='C14-P3B-1'
MAX_FRAME=131072
ASSUMPTIONS=('GAUSSIAN_LINEAR_MARKOV_FAITHFULNESS_UNTESTED;UNDIRECTED_SKELETON_ONLY;'
             'UNOBSERVED_CONFOUNDERS_AND_SELECTION_BIAS_NOT_RESOLVED')
ID=re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z')


def _parse(raw):
    req=_decode(raw,d.DiscoveryRequest)
    n=len(req.variable_ids)
    if (req.schema_version!=1 or not TRACE.fullmatch(req.trace_id) or
        req.method not in (d.REFERENCE_PC_STABLE_SKELETON,d.CAUSAL_LEARN_PC_OPTIONAL) or
        not 2<=n<=8 or any(not ID.fullmatch(x) for x in req.variable_ids) or
        len(set(req.variable_ids))!=n or not 60<=len(req.observations)<=400 or
        not 0.001<=req.alpha<=0.2 or not 0<=req.max_conditioning<=2 or
        not 1<=req.max_tests<=250 or not 1<=req.timeout_ms<=5000):
        raise ValueError('INVALID_DISCOVERY_REQUEST')
    if any(len(row.values)!=n or any(not math.isfinite(v) for v in row.values)
           for row in req.observations):
        raise ValueError('INVALID_NUMERIC_OBSERVATIONS')
    return req


def _fisher_p(data,i,j,cond):
    import numpy as np
    n=len(data)
    if not cond:
        r=float(np.corrcoef(data[:,i],data[:,j])[0,1])
    else:
        rhs=np.column_stack((np.ones(n),data[:,list(cond)]))
        if np.linalg.matrix_rank(rhs)!=rhs.shape[1]:
            raise ValueError('COLLINEAR_CONDITIONING_SET')
        x=data[:,i]-rhs@np.linalg.lstsq(rhs,data[:,i],rcond=None)[0]
        y=data[:,j]-rhs@np.linalg.lstsq(rhs,data[:,j],rcond=None)[0]
        r=float(np.corrcoef(x,y)[0,1])
    if not math.isfinite(r): raise ValueError('DEGENERATE_COVARIANCE')
    z=math.atanh(max(-1+1e-12,min(1-1e-12,r)))*math.sqrt(n-len(cond)-3)
    return math.erfc(abs(z)/math.sqrt(2))


def _compute(req,raw):
    output=d.DiscoveryResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
        trace_id=req.trace_id,backend_id=BACKEND,backend_version=VERSION,
        status=d.DISCOVERY_INCONCLUSIVE,reason_code='NOT_COMPUTED',assumptions=ASSUMPTIONS)
    if req.method==d.CAUSAL_LEARN_PC_OPTIONAL:
        output.status=d.DISCOVERY_BACKEND_UNAVAILABLE
        output.reason_code='CAUSAL_LEARN_RUNTIME_NOT_ATTESTED'
        return output
    import numpy as np
    data=np.asarray([row.values for row in req.observations],dtype=np.float64)
    if (np.any(np.std(data,axis=0)<1e-10) or
        not np.all(np.isfinite(data))):
        output.reason_code='DEGENERATE_VARIABLE'
        return output
    # The stable variant freezes the adjacency at every conditioning depth.
    # All pairs and separating sets are lexicographically enumerated.
    neighbors={i:set(range(len(req.variable_ids)))-{i} for i in range(len(req.variable_ids))}
    deadline=time.monotonic()+req.timeout_ms/1000
    tests=0
    for k in range(req.max_conditioning+1):
        frozen={i:set(adj) for i,adj in neighbors.items()}
        removals=[]
        for i in range(len(frozen)):
            for j in sorted(x for x in frozen[i] if x>i):
                candidates=set(combinations(sorted(frozen[i]-{j}),k))
                candidates.update(combinations(sorted(frozen[j]-{i}),k))
                for condition in sorted(candidates):
                    if time.monotonic()>deadline or tests>=req.max_tests:
                        output.status=d.DISCOVERY_RESOURCE_LIMIT
                        output.reason_code='TIME_OR_CONDITIONAL_TEST_LIMIT'
                        output.tests_executed=tests
                        return output # never publish truncated candidate graph
                    pval=_fisher_p(data,i,j,condition)
                    tests+=1
                    if pval>req.alpha:
                        removals.append((i,j,condition,pval))
                        break
        for i,j,condition,pval in removals:
            neighbors[i].discard(j); neighbors[j].discard(i)
            output.separations.add(first=i,second=j,conditioned_on=condition,
                                   independence_p_value=format(pval,'.12g'))
    for i in range(len(neighbors)):
        for j in sorted(x for x in neighbors[i] if x>i):
            output.undirected_edges.add(first=i,second=j)
    output.tests_executed=tests
    output.orientations_inferred=False
    output.status=d.CANDIDATE_SKELETON_COMPUTED
    output.reason_code='UNDIRECTED_CI_SKELETON_HYPOTHESIS_ONLY'
    return output


def run_discovery_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    result=d.DiscoveryResult(schema_version=1,request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=d.DISCOVERY_REJECTED,reason_code='INVALID_FRAME',backend_id=BACKEND,backend_version=VERSION)
    try:
        if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
            raise ValueError('INVALID_FRAME')
        req=_parse(raw)
        result.trace_id=req.trace_id
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('DISCOVERY_DISABLED')
        result=_compute(req,raw)
    except (ValueError,TypeError) as e:
        result.reason_code=str(e) if str(e).isupper() and len(str(e))<90 else 'INVALID_OR_FAILED'
        result.status=d.DISCOVERY_INCONCLUSIVE if result.reason_code in ('DEGENERATE_VARIABLE','COLLINEAR_CONDITIONING_SET','DEGENERATE_COVARIANCE') else d.DISCOVERY_REJECTED
    except (ImportError,ModuleNotFoundError):
        result.status=d.DISCOVERY_BACKEND_UNAVAILABLE
        result.reason_code='NUMPY_RUNTIME_UNAVAILABLE'
    except Exception:
        result.status=d.DISCOVERY_INCONCLUSIVE
        result.reason_code='DISCOVERY_RUNTIME_FAILURE'
    result.wall_ns=time.monotonic_ns()-start
    return _encode(result)


def verify_discovery_result(raw,reply):
    """Bound request-bound replay, NOT independent causal-structure verification."""
    try:
        req=_parse(raw)
        got=_decode(reply,d.DiscoveryResult)
        if got.status!=d.CANDIDATE_SKELETON_COMPUTED:return False
        expected=_compute(req,raw)
        if expected.status!=d.CANDIDATE_SKELETON_COMPUTED:return False
        got.wall_ns=expected.wall_ns=0
        return got.SerializeToString(deterministic=True)==expected.SerializeToString(deterministic=True)
    except Exception:
        return False


def discovery_receipt(raw,reply):
    ok=verify_discovery_result(raw,reply)
    return d.DiscoveryReceipt(request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(reply).digest(),deterministic_replay_verified=ok,
        causal_structure_verified=False,
        reason_code='STATISTICAL_SKELETON_REPLAY_VERIFIED' if ok else 'UNVERIFIED_OR_NONRESULT')


def discovery_audit(raw,reply):
    result=_decode(reply,d.DiscoveryResult)
    return d.DiscoveryAudit(request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(reply).digest(),trace_id=result.trace_id,
        status=result.status,backend_id=result.backend_id,reason_code=result.reason_code,
        wall_ns=result.wall_ns)
