"""C15 T2 P2C bounded competing structural explanations.

Posterior-like *relative weights* use a caller-specified discrete likelihood model.
They are NOT sensor-calibrated, physical truth probabilities, or an OWL reasoner.
Read-only proposals, with conservative functional constraints.
"""
from __future__ import annotations
import math
from cognitum.proto import structural_hypotheses_pb2 as pb

class StructuralHypothesesRejected(ValueError):
    pass

def _require(condition, reason):
    if not condition: raise StructuralHypothesesRejected(reason)

def _ident(s):
    return isinstance(s,str) and 0 < len(s) <= 128 and all(ch.isascii() and (ch.isalnum() or ch in '_-.:') for ch in s)

def _known(message):
    stripped=type(message)();stripped.CopyFrom(message);stripped.DiscardUnknownFields()
    return stripped==message

def analyze(req:pb.StructuralHypothesisRequest)->pb.StructuralHypothesisResult:
    _require(isinstance(req,pb.StructuralHypothesisRequest) and req.schema_version==1 and req.research_only and not req.grants_authority,'INVALID_CONTRACT')
    _require(_known(req),'UNKNOWN_PROTO_FIELDS')
    _require(_ident(req.graph_id) and _ident(req.conversation_id),'INVALID_SCOPE')
    _require(2<=len(req.hypotheses)<=16 and len(req.observations)<=128 and len(req.functions)<=64 and len(req.SerializeToString())<=120000,'RESOURCE_LIMIT')
    hypotheses={}; claims={}; conflicts={}
    for h in req.hypotheses:
        _require(_ident(h.hypothesis_id) and h.hypothesis_id not in hypotheses and math.isfinite(h.prior_weight) and h.prior_weight>0 and h.prior_weight<=1e9 and len(h.assertions)<=128,'INVALID_HYPOTHESIS')
        hypotheses[h.hypothesis_id]=h
        pos={}; bad=[]
        for a in h.assertions:
            _require(all(_ident(v) for v in (a.assembly_id,a.part_id,a.role)) and a.assembly_id!=a.part_id,'INVALID_ASSERTION')
            key=(a.assembly_id,a.part_id,a.role)
            if key in pos and pos[key]!=a.present:bad.append('PRESENCE_ABSENCE_CONFLICT')
            pos[key]=a.present
        # Part->assembly membership must not introduce cycles, even if graph is inferred.
        edges={}
        for (assembly,part,role),present in pos.items():
            if present:edges.setdefault(part,set()).add(assembly)
        def walk(node,stack,done):
            if node in stack:return True
            if node in done:return False
            stack.add(node)
            for parent in edges.get(node,()):
                if walk(parent,stack,done):return True
            stack.remove(node);done.add(node);return False
        done=set()
        if any(walk(n,set(),done) for n in edges):bad.append('PART_WHOLE_CYCLE')
        claims[h.hypothesis_id]=pos;conflicts[h.hypothesis_id]=sorted(set(bad))
    logweights={hid:math.log(h.prior_weight) for hid,h in hypotheses.items()}
    observed=set()
    for o in req.observations:
        key=(o.source_ref,o.tick)
        _require(_ident(o.source_ref) and o.tick>0 and key not in observed,'INVALID_OR_REPLAYED_EVIDENCE')
        observed.add(key)
        probs={}
        for score in o.likelihoods:
            _require(score.hypothesis_id in hypotheses and score.hypothesis_id not in probs and math.isfinite(score.likelihood) and 0<score.likelihood<=1,'INVALID_LIKELIHOOD')
            probs[score.hypothesis_id]=score.likelihood
        _require(probs.keys()==hypotheses.keys(),'INCOMPLETE_LIKELIHOOD_VECTOR')
        for hid,likelihood in probs.items():logweights[hid]+=math.log(likelihood)
    funcs={}
    for f in req.functions:
        key=(f.assembly_id,f.function_id)
        _require(_ident(f.assembly_id) and _ident(f.function_id) and key not in funcs and len(f.required_roles)+len(f.excluded_roles)>0 and len(f.required_roles)<=32 and len(f.excluded_roles)<=32 and all(_ident(r) for r in list(f.required_roles)+list(f.excluded_roles)) and not (set(f.required_roles)&set(f.excluded_roles)) and len(set(f.required_roles))==len(f.required_roles) and len(set(f.excluded_roles))==len(f.excluded_roles),'INVALID_FUNCTION_CONSTRAINT')
        funcs[key]=f
    valid=[hid for hid in hypotheses if not conflicts[hid]]
    _require(bool(valid),'NO_INTERNALLY_CONSISTENT_HYPOTHESIS')
    peak=max(logweights[hid] for hid in valid)
    total=sum(math.exp(logweights[hid]-peak) for hid in valid)
    result=pb.StructuralHypothesisResult(graph_id=req.graph_id,conversation_id=req.conversation_id,research_only=True,grants_authority=False)
    for hid in sorted(hypotheses,key=lambda n:(-logweights[n] if n in valid else float('inf'),n)):
        valid_h=not conflicts[hid]
        entry=result.ranked.add(hypothesis_id=hid,relative_weight=(math.exp(logweights[hid]-peak)/total if valid_h else 0),internally_consistent=valid_h,contradictions=conflicts[hid])
        assertions=claims[hid]
        for key,f in sorted(funcs.items()):
            roles={}
            for (assembly,part,role),present in assertions.items():
                if assembly==f.assembly_id:
                    roles.setdefault(role,[]).append(present)
            missing=[r for r in f.required_roles if True not in roles.get(r,[])]
            excluded=[r for r in f.excluded_roles if True in roles.get(r,[])]
            contradicted=[r for r in f.required_roles if r in roles and True not in roles[r] and False in roles[r]]
            status='CONTRADICTED' if excluded or contradicted else ('UNDETERMINED' if missing else 'STRUCTURAL_PRECONDITIONS_CLAIMED')
            assessment=entry.functions.add(function_id=f.function_id,status=status)
            if missing:assessment.reasons.append('REQUIRED_ROLES_UNESTABLISHED:'+','.join(sorted(missing)))
            if excluded:assessment.reasons.append('EXCLUDED_ROLES_PRESENT:'+','.join(sorted(excluded)))
            if contradicted:assessment.reasons.append('REQUIRED_ROLES_EXPLICITLY_ABSENT:'+','.join(sorted(contradicted)))
            assessment.reasons.append('NO_FUNCTION_PERFORMANCE_CERTIFICATION')
    ranked=[h.relative_weight for h in result.ranked if h.internally_consistent]
    result.ambiguous=len(ranked)>1 and (ranked[0]-ranked[1]<0.2 or ranked[0]<0.7)
    result.warnings.extend(['RELATIVE_WEIGHTS_CONDITIONAL_ON_CALLER_PRIORS_AND_LIKELIHOODS','DEPENDENT_EVIDENCE_CAN_BE_DOUBLE_COUNTED','SOURCE_REFS_NOT_AUTHENTICATED','CLAIMS_NOT_OBSERVED_FACTS','FUNCTIONAL_PRESENCE_NOT_FUNCTIONALITY','NO_ACTION_AUTHORITY'])
    return result
