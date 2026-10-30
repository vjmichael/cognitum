"""C14 P3F: bounded enumeration of DAG orientation and Markov equivalence hypotheses.

For an undirected skeleton, acyclic orientations partition into Markov
classes by unshielded collider signatures. This is a *mathematical* property
under causal sufficiency and Markov+faithfulness, not a data-driven proof of
causation, orientation, CPDAG, or latent-confounder completeness.
"""
from __future__ import annotations
from itertools import combinations
import hashlib
import time
from cognitum.causal_discovery import _parse as parse_discovery, verify_discovery_result
from cognitum.causal_estimation import _decode
from cognitum.proto import causal_ambiguity_pb2 as a, causal_discovery_pb2 as d

MAX_FRAME=185000
MAX_CAPTURE=32768
LIMITS=('FINITE_DAG_ORIENTATIONS_ONLY;OBSERVATIONAL_MEC_BY_SKELETON_AND_V_STRUCTURES;'
        'CAUSAL_SUFFICIENCY_MARKOV_FAITHFULNESS_ARE_ASSUMPTIONS;'
        'UNOBSERVED_CONFOUNDERS_SELECTION_BIAS_NOT_EXCLUDED;'
        'DECLARED_COLLIDER_SIGNATURE_NOT_INDEPENDENTLY_VERIFIED;NOT_A_PAG_OR_FCI')


def _parse(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_AMBIGUITY_FRAME')
    req=_decode(raw,a.AmbiguityRequest)
    if (req.schema_version!=1 or not req.HasField('source_request') or
        req.trace_id!=req.source_request.trace_id or not req.trace_id or
        req.source_request.method!=d.REFERENCE_PC_STABLE_SKELETON or
        not req.source_result or len(req.source_result)>MAX_CAPTURE or
        not 1<=req.max_orientations<=512 or not 1<=req.timeout_ms<=10000):
        raise ValueError('INVALID_AMBIGUITY_REQUEST')
    parse_discovery(req.source_request.SerializeToString(deterministic=True))
    reply=_decode(req.source_result,d.DiscoveryResult)
    if reply.status!=d.CANDIDATE_SKELETON_COMPUTED or reply.orientations_inferred:
        raise ValueError('INVALID_SOURCE_SKELETON')
    n=len(req.source_request.variable_ids)
    edges=[(x.first,x.second) for x in reply.undirected_edges]
    if (not 2<=n<=6 or len(edges)>9 or
        edges != sorted(set(edges)) or any(not 0<=u<v<n for u,v in edges)):
        raise ValueError('SKELETON_OUTSIDE_ENUMERATION_BOUND')
    if 2**len(edges)>req.max_orientations:
        raise ValueError('ORIENTATION_CAP_TOO_SMALL')
    skeleton=set(edges)
    signature=[]
    for c in req.declared_colliders:
        triple=(c.first,c.middle,c.last)
        if (not req.select_declared_collider_signature or
            not 0<=c.first<c.last<n or not 0<=c.middle<n or
            c.middle in (c.first,c.last) or
            (min(c.first,c.middle),max(c.first,c.middle)) not in skeleton or
            (min(c.last,c.middle),max(c.last,c.middle)) not in skeleton or
            (c.first,c.last) in skeleton):
            raise ValueError('INVALID_DECLARED_COLLIDER')
        signature.append(triple)
    if signature!=sorted(set(signature)):
        raise ValueError('DUPLICATE_OR_NONCANONICAL_COLLIDERS')
    return req,reply,edges,tuple(signature)


def _acyclic(n,directed):
    children=[[] for _ in range(n)]
    indegree=[0]*n
    for u,v in directed:
        children[u].append(v);indegree[v]+=1
    queue=[i for i,degree in enumerate(indegree) if degree==0]
    seen=0
    while queue:
        u=queue.pop()
        seen+=1
        for v in children[u]:
            indegree[v]-=1
            if indegree[v]==0:queue.append(v)
    return seen==n


def _signature(n,directed,skeleton):
    parents=[set() for _ in range(n)]
    for u,v in directed:parents[v].add(u)
    colliders=[]
    for middle in range(n):
        for u,v in combinations(sorted(parents[middle]),2):
            if (u,v) not in skeleton:
                colliders.append((u,middle,v))
    return tuple(sorted(colliders))


def _compute(req,reply,edges,expected,*,clock=time.monotonic):
    n=len(req.source_request.variable_ids)
    skeleton=set(edges)
    start=clock()
    groups={}
    acyclic=0
    out=a.AmbiguityResult(schema_version=1,trace_id=req.trace_id,
        status=a.AMBIGUITY_INCONCLUSIVE,reason_code='NOT_COMPUTED',
        source_skeleton_replayed=True,assumptions_and_limits=LIMITS)
    for mask in range(1<<len(edges)):
        if (clock()-start)*1000>=req.timeout_ms:
            out.status=a.AMBIGUITY_RESOURCE_LIMIT
            out.reason_code='TIME_BUDGET_EXHAUSTED'
            return out
        directed=tuple((v,u) if mask & (1<<i) else (u,v)
                       for i,(u,v) in enumerate(edges))
        if not _acyclic(n,directed):continue
        acyclic+=1
        signature=_signature(n,directed,skeleton)
        if req.select_declared_collider_signature and signature!=expected:
            continue
        group=groups.setdefault(signature,[])
        group.append(set(directed))
    if not groups:
        out.reason_code='DECLARED_SIGNATURE_HAS_NO_COMPATIBLE_DAGS'
        return out
    out.orientations_considered=1<<len(edges)
    out.acyclic_orientations=acyclic
    for signature, members in sorted(groups.items()):
        g=out.classes.add(dag_count=len(members))
        for u,m,v in signature:g.unshielded_colliders.add(first=u,middle=m,last=v)
        common=set.intersection(*members)
        for u,v in sorted(common):g.compelled_arrows_within_class.add(source=u,target=v)
    out.status=a.AMBIGUITY_COMPUTED
    out.reason_code=('ASSUMPTION_FILTERED_MARKOV_CLASSES' if req.select_declared_collider_signature
                     else 'ALL_MARKOV_CLASSES_FOR_SUPPLIED_SKELETON')
    return out


def run_ambiguity_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    out=a.AmbiguityResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=a.AMBIGUITY_REJECTED,reason_code='INVALID_AMBIGUITY_FRAME',
        assumptions_and_limits=LIMITS)
    try:
        req,source,edges,expected=_parse(raw)
        out.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('AMBIGUITY_DISABLED')
        source_raw=req.source_request.SerializeToString(deterministic=True)
        if not verify_discovery_result(source_raw,req.source_result):
            out.status=a.AMBIGUITY_INCONCLUSIVE
            out.reason_code='SOURCE_REPLAY_FAILED'
        else:
            out=_compute(req,source,edges,expected)
            out.request_sha256=hashlib.sha256(raw).digest()
    except (ValueError,TypeError) as exc:
        reason=str(exc)
        out.reason_code=reason if reason.isupper() and len(reason)<100 else 'INVALID_AMBIGUITY_REQUEST'
    except Exception:
        out.status=a.AMBIGUITY_INCONCLUSIVE
        out.reason_code='AMBIGUITY_RUNTIME_FAILURE'
    if out.status!=a.AMBIGUITY_COMPUTED:
        del out.classes[:]
        out.orientations_considered=0
        out.acyclic_orientations=0
        out.source_skeleton_replayed=False
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def ambiguity_receipt(raw,reply):
    receipt=a.AmbiguityReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req,source,edges,expected=_parse(raw)
        got=_decode(reply,a.AmbiguityResult)
        if got.status!=a.AMBIGUITY_COMPUTED or got.request_sha256!=receipt.request_sha256:
            return receipt
        if not verify_discovery_result(req.source_request.SerializeToString(deterministic=True),req.source_result):
            return receipt
        model=_compute(req,source,edges,expected)
        model.request_sha256=receipt.request_sha256
        model.wall_ns=got.wall_ns
        if model.status==a.AMBIGUITY_COMPUTED and model.SerializeToString(deterministic=True)==got.SerializeToString(deterministic=True):
            receipt.enumeration_replay=True
            receipt.reason_code='ASSUMED_DAG_CLASS_ENUMERATION_REPLAY_ONLY'
    except Exception:
        pass
    return receipt
