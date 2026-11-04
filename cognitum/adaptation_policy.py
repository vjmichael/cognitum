"""C18 bounded, consent-scoped adaptation for *routing only*.

No prompts or trace text, file access, tool execution, base-LLM changes, or
automatic adoption. A caller must supply sanitized numeric feature vectors
and explicitly source-authorized labels. This module is not a Lu host grant.
"""
from dataclasses import dataclass,replace
from hashlib import sha256
from math import isfinite,log,exp
import json

MAX_ROWS=512
MAX_FEATURES=8
ROUTES=("direct","specialist","abstain")
PRIVACY=("public_synthetic","consented_aggregate")
TARGETS=("tool_router","retrieval_ranker")

@dataclass(frozen=True)
class Trace:
    event_id:str
    occurred_ms:int
    features:tuple[float,...]
    expected_route:str
    source_digest:str
    consent_receipt:str
    retention_until_ms:int
    privacy_class:str
    task_family:str

@dataclass(frozen=True)
class AdaptationProposal:
    proposal_id:str
    workspace_id:str
    target:str
    policy_version:int
    source_digest:str
    consent_receipt:str
    privacy_class:str
    allowed_families:tuple[str,...]
    retention_until_ms:int
    train_before_ms:int
    holdout_from_ms:int
    base_policy_digest:str
    maximum_training_rows:int
    maximum_cpu_ms:int
    rollback_policy_digest:str

@dataclass(frozen=True)
class RoutingPolicy:
    policy_version:int
    workspace_id:str
    target:str
    allowed_families:tuple[str,...]
    feature_count:int
    coefficients:tuple[tuple[float,...],...]
    intercepts:tuple[float,...]
    center:tuple[float,...]
    scale:tuple[float,...]
    training_digest:str
    proposal_id:str
    base_policy_digest:str
    status:str                   # candidate | approved | revoked
    digest:str

@dataclass(frozen=True)
class Evaluation:
    status:str
    count:int
    accuracy:float
    log_loss:float
    worst_family_accuracy:float
    abstention_rate:float
    elapsed_ms:float=0.
    limitations:tuple[str,...]=(
        "sanitized_feature_labels_not_authenticity_proof",
        "prediction_accuracy_not_Lu_task_success",
        "holdout_requires_independently_provisioned_future_labels",
    )

def _id(v):
    return type(v) is str and v.isascii() and v.isidentifier() and 1<=len(v)<=64

def _digest(v):
    return type(v) is str and len(v)==64 and all(c in "0123456789abcdef" for c in v)

def _canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def _body(p):
    return {k:getattr(p,k) for k in RoutingPolicy.__dataclass_fields__ if k!="digest"}

def seal(p):
    return replace(p,digest=sha256(_canonical(_body(p))).hexdigest())

def verify_policy(p):
    if (type(p) is not RoutingPolicy or p.policy_version<1
            or not _id(p.workspace_id) or p.target not in TARGETS
            or not 1<=p.feature_count<=MAX_FEATURES
            or type(p.allowed_families) is not tuple
            or not 1<=len(p.allowed_families)<=8
            or any(not _id(x) for x in p.allowed_families)
            or p.status not in ("candidate","approved","revoked")
            or not _id(p.proposal_id)
            or not _digest(p.training_digest)
            or not _digest(p.base_policy_digest)
            or not _digest(p.digest)
            or len(p.coefficients)!=len(ROUTES)
            or any(len(x)!=p.feature_count for x in p.coefficients)
            or len(p.intercepts)!=len(ROUTES)
            or len(p.center)!=p.feature_count
            or len(p.scale)!=p.feature_count
            or any(x<=0 for x in p.scale)
            or any(type(x) not in (int,float) or not isfinite(x) or abs(x)>1e6
                   for row in p.coefficients for x in row)
            or any(type(x) not in (int,float) or not isfinite(x) or abs(x)>1e6
                   for x in p.center+p.scale+p.intercepts)
            or seal(p).digest!=p.digest):
        raise ValueError("corrupt or unsupported routing checkpoint")
    return p

def validate_proposal(p,rows,*,now_ms):
    if (type(p) is not AdaptationProposal or type(rows) is not tuple
            or type(now_ms) is not int or now_ms<0
            or not _id(p.proposal_id) or not _id(p.workspace_id)
            or p.target not in TARGETS or p.policy_version<1
            or not _digest(p.source_digest) or not _digest(p.base_policy_digest)
            or not _digest(p.rollback_policy_digest)
            or not _id(p.consent_receipt)
            or p.privacy_class not in PRIVACY
            or type(p.allowed_families) is not tuple
            or not 1<=len(p.allowed_families)<=8
            or len(set(p.allowed_families))!=len(p.allowed_families)
            or any(not _id(x) for x in p.allowed_families)
            or not 16<=len(rows)<=MAX_ROWS
            or not 16<=p.maximum_training_rows<=MAX_ROWS
            or not 1<=p.maximum_cpu_ms<=120000
            or not now_ms<p.train_before_ms<p.holdout_from_ms<=p.retention_until_ms
            or p.rollback_policy_digest!=p.base_policy_digest):
        raise ValueError("invalid or unbounded adaptation proposal")
    dim=len(rows[0].features)
    if not 1<=dim<=MAX_FEATURES:raise ValueError("invalid feature dimension")
    last=-1
    ids=set()
    for row in rows:
        if (type(row) is not Trace or not _id(row.event_id)
                or row.event_id in ids
                or type(row.occurred_ms) is not int or not last<row.occurred_ms
                or not now_ms<=row.retention_until_ms
                or row.retention_until_ms>p.retention_until_ms
                or row.source_digest!=p.source_digest
                or row.consent_receipt!=p.consent_receipt
                or row.privacy_class!=p.privacy_class
                or row.task_family not in p.allowed_families
                or row.expected_route not in ROUTES
                or type(row.features) is not tuple or len(row.features)!=dim
                or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>1e5
                       for v in row.features)):
            raise ValueError("untrusted, duplicate, expired or malformed trace")
        last=row.occurred_ms
        ids.add(row.event_id)
    training=tuple(x for x in rows if x.occurred_ms<p.train_before_ms)
    holdout=tuple(x for x in rows if x.occurred_ms>=p.holdout_from_ms)
    if (len(training)<12 or len(training)>p.maximum_training_rows
            or len(holdout)<4 or len(training)+len(holdout)!=len(rows)
            or {x.task_family for x in holdout}-{x.task_family for x in training}):
        raise ValueError("split leakage, gap contamination or missing supported family")
    return training,holdout

def _predict(p,features):
    verify_policy(p)
    if (type(features) is not tuple or len(features)!=p.feature_count
            or any(type(x) not in (int,float) or not isfinite(x) or abs(x)>1e5
                   for x in features)):
        raise ValueError("unsupported router features")
    z=[(x-m)/s for x,m,s in zip(features,p.center,p.scale)]
    logits=[b+sum(w*v for w,v in zip(row,z))
            for b,row in zip(p.intercepts,p.coefficients)]
    pivot=max(logits)
    weights=[exp(max(-700,min(700,a-pivot))) for a in logits]
    total=sum(weights)
    return tuple(v/total for v in weights)

def route(p,features,*,workspace_id,task_family,minimum_confidence=.65):
    verify_policy(p)
    if (p.status!="approved" or workspace_id!=p.workspace_id
            or task_family not in p.allowed_families
            or type(minimum_confidence) not in (float,int)
            or not isfinite(minimum_confidence) or not .5<=minimum_confidence<=.99):
        return "abstain",None
    probabilities=_predict(p,features)
    best=max(range(len(ROUTES)),key=lambda i:probabilities[i])
    return (ROUTES[best] if probabilities[best]>=minimum_confidence else "abstain",
            probabilities)

def score(p,rows):
    verify_policy(p)
    if not rows:raise ValueError("empty evaluation")
    if any(type(r) is not Trace or r.task_family not in p.allowed_families
           or r.expected_route not in ROUTES for r in rows):
        raise ValueError("unsupported evaluation labels")
    correct=0;loss=0.;abstain=0;groups={}
    for r in rows:
        # Evaluate the frozen candidate without activating production routing.
        prob=_predict(p,r.features)
        prediction=ROUTES[max(range(3),key=lambda j:prob[j])]
        target=ROUTES.index(r.expected_route)
        correct+=prediction==r.expected_route
        abstain+=prediction=="abstain"
        loss-=log(max(1e-12,prob[target]))
        g=groups.setdefault(r.task_family,[0,0])
        g[0]+=prediction==r.expected_route;g[1]+=1
    return Evaluation("EVALUATED",len(rows),correct/len(rows),loss/len(rows),
                      min(a/b for a,b in groups.values()),abstain/len(rows))

def train(p,rows,*,now_ms,host_authorized=False):
    if host_authorized is not True:
        raise PermissionError("training requires independent host consent")
    training,holdout=validate_proposal(p,rows,now_ms=now_ms)
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise RuntimeError("scikit_learn_adaptation_backend_unavailable") from exc
    from time import perf_counter
    started=perf_counter()
    X=np.asarray([x.features for x in training],dtype=float)
    y=np.asarray([ROUTES.index(x.expected_route) for x in training])
    if len(set(y))<3:
        raise ValueError("learned routing needs examples of all three route classes")
    center=X.mean(axis=0)
    scale=np.maximum(X.std(axis=0),1e-8)
    normalized=(X-center)/scale
    classifier=LogisticRegression(C=1.0,max_iter=250,solver="lbfgs",
                                   class_weight="balanced",random_state=0)
    classifier.fit(normalized,y)
    if (perf_counter()-started)*1000>p.maximum_cpu_ms:
        raise RuntimeError("training_cpu_wall_budget_exceeded")
    if tuple(int(x) for x in classifier.classes_)!=(0,1,2):
        raise ValueError("unrecognized router class weights")
    digest=sha256(_canonical([
        (x.event_id,x.occurred_ms,x.features,x.expected_route,
         x.source_digest,x.consent_receipt) for x in training])).hexdigest()
    model=RoutingPolicy(p.policy_version,p.workspace_id,p.target,p.allowed_families,
        X.shape[1],tuple(tuple(float(y) for y in x) for x in classifier.coef_),
        tuple(float(x) for x in classifier.intercept_),
        tuple(float(x) for x in center),tuple(float(x) for x in scale),
        digest,p.proposal_id,p.base_policy_digest,"candidate","")
    return seal(model),holdout
