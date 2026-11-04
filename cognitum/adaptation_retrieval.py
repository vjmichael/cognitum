"""C18 opt-in retrieval score tuning on numeric document features only.

No text ingestion, embeddings, fetches, arbitrary model execution or Lu
retrieval index mutations. Features such as normalized BM25/recency are
supplied by an authorized host; model never opens or searches documents.
"""
from dataclasses import dataclass,replace
from hashlib import sha256
from math import exp,isfinite
import json

MAX_CANDIDATES=512
MAX_DIMENSIONS=8

@dataclass(frozen=True)
class RetrievalExample:
    query_id:str
    document_id:str
    occurred_ms:int
    features:tuple[float,...]
    relevant:bool
    source_digest:str
    consent_receipt:str

@dataclass(frozen=True)
class RetrievalArtifact:
    version:int
    workspace_id:str
    source_digest:str
    consent_receipt:str
    train_cutoff_ms:int
    feature_count:int
    weights:tuple[float,...]
    intercept:float
    center:tuple[float,...]
    scale:tuple[float,...]
    train_digest:str
    status:str # candidate | approved | revoked
    digest:str

@dataclass(frozen=True)
class RetrievalMetrics:
    queries:int
    hit_at_one:float
    mean_reciprocal_rank:float
    limitations:tuple[str,...]=(
        "judgments_supplied_by_caller_not_authenticated",
        "numeric_features_only_no_raw_documents",
        "evaluation_not_a_Lu_user_task_success_measure",
    )

def _id(x):
    return type(x) is str and x.isascii() and x.isidentifier() and 1<=len(x)<=64

def _digest(x):
    return type(x) is str and len(x)==64 and all(c in "0123456789abcdef" for c in x)

def _canonical(x):
    return json.dumps(x,separators=(",",":"),sort_keys=True,allow_nan=False).encode()

def _seal(a):
    data={k:getattr(a,k) for k in RetrievalArtifact.__dataclass_fields__ if k!="digest"}
    return replace(a,digest=sha256(_canonical(data)).hexdigest())

def verify(a:RetrievalArtifact):
    if (type(a) is not RetrievalArtifact or a.version!=1
            or not _id(a.workspace_id) or not _id(a.consent_receipt)
            or not _digest(a.source_digest) or not _digest(a.train_digest)
            or not _digest(a.digest)
            or a.status not in ("candidate","approved","revoked")
            or type(a.train_cutoff_ms) is not int or a.train_cutoff_ms<=0
            or not 1<=a.feature_count<=MAX_DIMENSIONS
            or any(len(v)!=a.feature_count for v in (a.weights,a.center,a.scale))
            or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>1e6
                   for v in a.weights+a.center+a.scale+(a.intercept,))
            or any(x<=0 for x in a.scale)
            or _seal(a).digest!=a.digest):
        raise ValueError("corrupt retrieval ranking checkpoint")
    return a

def validate(examples,*,cutoff_ms,now_ms,consent_receipt,source_digest):
    if (type(examples) is not tuple or not 24<=len(examples)<=MAX_CANDIDATES
            or type(cutoff_ms) is not int or type(now_ms) is not int
            or not 0<cutoff_ms<=now_ms
            or not _id(consent_receipt) or not _digest(source_digest)):
        raise ValueError("invalid bounded retrieval evaluation input")
    if type(examples[0]) is not RetrievalExample:\n        raise ValueError("invalid retrieval example shape")\n    count=len(examples[0].features)
    if not 1<=count<=MAX_DIMENSIONS:
        raise ValueError("invalid retrieval feature count")
    seen=set();query_times={};query_splits={};last=-1
    for item in examples:
        if (type(item) is not RetrievalExample or not _id(item.query_id)
                or not _id(item.document_id)
                or type(item.occurred_ms) is not int
                or not last<=item.occurred_ms<=now_ms
                or type(item.relevant) is not bool
                or type(item.features) is not tuple or len(item.features)!=count
                or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>1e5
                       for v in item.features)
                or item.consent_receipt!=consent_receipt
                or item.source_digest!=source_digest
                or (item.query_id,item.document_id) in seen):
            raise ValueError("duplicate/untrusted/invalid retrieval evidence")
        seen.add((item.query_id,item.document_id))
        if item.query_id in query_times and query_times[item.query_id]!=item.occurred_ms:
            raise ValueError("one query has inconsistent observation time")
        query_times[item.query_id]=item.occurred_ms
        split=item.occurred_ms<cutoff_ms
        if item.query_id in query_splits and query_splits[item.query_id]!=split:
            raise ValueError("query leaked across training/holdout")
        query_splits[item.query_id]=split
        last=item.occurred_ms
    train=tuple(x for x in examples if x.occurred_ms<cutoff_ms)
    hold=tuple(x for x in examples if x.occurred_ms>=cutoff_ms)
    if (len(train)<16 or len(hold)<8
            or len({x.query_id for x in train})<4
            or len({x.query_id for x in hold})<2
            or len({x.relevant for x in train})<2):
        raise ValueError("insufficient retrieval train/heldout relevance")
    return train,hold

def train(examples,*,workspace_id,source_digest,consent_receipt,
          cutoff_ms,now_ms,host_authorized=False):
    if host_authorized is not True:
        raise PermissionError("independent consented retrieval training required")
    if not _id(workspace_id):
        raise ValueError("workspace scope missing")
    training,hold=validate(examples,cutoff_ms=cutoff_ms,now_ms=now_ms,
                           consent_receipt=consent_receipt,
                           source_digest=source_digest)
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise RuntimeError("scikit_learn_ranker_backend_unavailable") from exc
    X=np.asarray([x.features for x in training],dtype=float)
    y=np.asarray([x.relevant for x in training],dtype=int)
    center=X.mean(axis=0);scale=np.maximum(X.std(axis=0),1e-8)
    model=LogisticRegression(C=1.,max_iter=250,solver="lbfgs",random_state=0)
    model.fit((X-center)/scale,y)
    payload=[(x.query_id,x.document_id,x.occurred_ms,x.features,x.relevant,
              x.source_digest) for x in training]
    a=RetrievalArtifact(1,workspace_id,source_digest,consent_receipt,cutoff_ms,
        len(center),tuple(float(v) for v in model.coef_[0]),
        float(model.intercept_[0]),tuple(float(v) for v in center),
        tuple(float(v) for v in scale),
        sha256(_canonical(payload)).hexdigest(),"candidate","")
    return verify(_seal(a)),hold

def predict(a:RetrievalArtifact,item:RetrievalExample):
    verify(a)
    if (type(item) is not RetrievalExample
            or len(item.features)!=a.feature_count
            or item.consent_receipt!=a.consent_receipt
            or item.source_digest!=a.source_digest):
        raise ValueError("candidate observation source mismatch")
    z=a.intercept+sum(w*(x-m)/s for w,x,m,s in
                      zip(a.weights,item.features,a.center,a.scale))
    if not isfinite(z):raise ValueError("nonfinite retrieval score")
    return 1/(1+exp(-max(-700,min(700,z))))

def evaluate(examples,*,model=None,baseline_feature=0):
    if not examples or type(examples) is not tuple:
        raise ValueError("empty retrieval evaluation")
    if model is not None:verify(model)
    by_query={}
    for row in examples:
        if not isinstance(row,RetrievalExample):
            raise ValueError("malformed evaluation candidate")
        by_query.setdefault(row.query_id,[]).append(row)
    hits=rr=0.
    for query,items in by_query.items():
        if not any(x.relevant for x in items):
            raise ValueError("a heldout query needs at least one judged relevant item")
        if model is None:
            if any(baseline_feature>=len(x.features) or baseline_feature<0
                   for x in items):
                raise ValueError("invalid baseline feature")
            ranked=sorted(items,key=lambda r:(-r.features[baseline_feature],r.document_id))
        else:
            ranked=sorted(items,key=lambda r:(-predict(model,r),r.document_id))
        rank=next((i for i,x in enumerate(ranked,1) if x.relevant),None)
        hits+=rank==1
        rr+=1/rank
    return RetrievalMetrics(len(by_query),hits/len(by_query),rr/len(by_query))
