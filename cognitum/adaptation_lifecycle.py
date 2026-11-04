"""C18 inert, auditable adaptation lifecycle and independent promotion gates.

Approval decisions and deletion receipts are *model-side records only*.
A Lu host must enforce actual revocation, durable storage, worker killing,
resource limits, permission scopes and deletion of its own raw sources.
"""
from dataclasses import dataclass,replace
from hashlib import sha256
from math import isfinite
import json

from .adaptation_policy import (
    AdaptationProposal,RoutingPolicy,Evaluation,Trace,ROUTES,
    _canonical,_digest,_id,seal,verify_policy,score,
)

@dataclass(frozen=True)
class Gate:
    minimum_accuracy_gain:float=.01
    maximum_log_loss_regression:float=.02
    maximum_worst_family_drop:float=.05
    minimum_heldout_rows:int=12
    minimum_baseline_accuracy:float=0.
    max_ood_abstention:float=.6

@dataclass(frozen=True)
class Promotion:
    status:str                  # REJECTED | READY_FOR_HOST_APPROVAL
    candidate_digest:str
    incumbent_digest:str
    candidate:Evaluation
    incumbent:Evaluation
    reasons:tuple[str,...]
    holdout_digest:str
    limitations:tuple[str,...]=(
        "statistical_evaluation_not_host_or_user_authorization",
        "frozen_holdout_not_independent_replication",
        "promotion_record_does_not_activate_Lu_tools_or_model",
    )

@dataclass(frozen=True)
class Lifecycle:
    workspace_id:str
    current_policy_digest:str
    fallback_policy_digest:str
    proposal_id:str
    status:str                  # prepared | active | paused | revoked | rolled_back
    revision:int
    seen_mutations:tuple[str,...]
    receipt_digest:str

def _digest_lifecycle(x):
    fields={name:getattr(x,name) for name in Lifecycle.__dataclass_fields__
            if name!="receipt_digest"}
    return sha256(_canonical(fields)).hexdigest()

def _seal(x):
    return replace(x,receipt_digest=_digest_lifecycle(x))

def verify_lifecycle(x):
    if (type(x) is not Lifecycle or not _id(x.workspace_id)
            or not _id(x.proposal_id)
            or x.status not in ("prepared","active","paused","revoked","rolled_back")
            or type(x.revision) is not int or x.revision<0
            or not _digest(x.current_policy_digest)
            or not _digest(x.fallback_policy_digest)
            or type(x.seen_mutations) is not tuple
            or len(x.seen_mutations)>256
            or len(set(x.seen_mutations))!=len(x.seen_mutations)
            or any(not _id(y) for y in x.seen_mutations)
            or not _digest(x.receipt_digest)
            or _digest_lifecycle(x)!=x.receipt_digest):
        raise ValueError("invalid or corrupted adaptation lifecycle receipt")
    return x

def evaluate_promotion(proposal:AdaptationProposal,candidate:RoutingPolicy,
                       incumbent:RoutingPolicy,holdout:tuple[Trace,...],*,
                       gate:Gate=Gate())->Promotion:
    verify_policy(candidate);verify_policy(incumbent)
    if (type(gate) is not Gate
            or any(type(x) not in (int,float) or not isfinite(x) for x in
                   (gate.minimum_accuracy_gain,gate.maximum_log_loss_regression,
                    gate.maximum_worst_family_drop,gate.minimum_baseline_accuracy,
                    gate.max_ood_abstention))
            or not 0<=gate.minimum_accuracy_gain<=1
            or not 0<=gate.maximum_log_loss_regression<=5
            or not 0<=gate.maximum_worst_family_drop<=1
            or not 0<=gate.minimum_baseline_accuracy<=1
            or not 0<=gate.max_ood_abstention<=1
            or type(gate.minimum_heldout_rows) is not int
            or not 4<=gate.minimum_heldout_rows<=512):
        raise ValueError("invalid or nonfinite evaluation gate")
    if (candidate.status!="candidate" or incumbent.status!="approved"
            or candidate.workspace_id!=proposal.workspace_id
            or incumbent.workspace_id!=proposal.workspace_id
            or candidate.target!=proposal.target or incumbent.target!=proposal.target
            or candidate.proposal_id!=proposal.proposal_id
            or candidate.base_policy_digest!=incumbent.digest
            or proposal.base_policy_digest!=incumbent.digest
            or proposal.rollback_policy_digest!=incumbent.digest
            or candidate.allowed_families!=incumbent.allowed_families
            or candidate.policy_version<=incumbent.policy_version
            or not 4<=len(holdout)<=512
            or type(gate) is not Gate):
        raise ValueError("incompatible candidate, baseline or evaluation gate")
    if (type(holdout) is not tuple
            or len({x.event_id for x in holdout if type(x) is Trace})!=len(holdout)
            or any(type(x) is not Trace
                   or not _id(x.event_id)
                   or type(x.occurred_ms) is not int
                   or x.occurred_ms<proposal.holdout_from_ms
                   or x.occurred_ms>=proposal.retention_until_ms
                   or x.consent_receipt!=proposal.consent_receipt
                   or x.source_digest!=proposal.source_digest
                   or x.privacy_class!=proposal.privacy_class
                   or x.task_family not in proposal.allowed_families
                   or type(x.features) is not tuple
                   for x in holdout)
            or any(b.occurred_ms<=a.occurred_ms
                   for a,b in zip(holdout,holdout[1:]))):
        raise ValueError("untrusted, duplicated or training-overlapping holdout")
    test=score(candidate,holdout)
    baseline=score(incumbent,holdout)
    reasons=[]
    if test.count<gate.minimum_heldout_rows:
        reasons.append("insufficient_future_holdout")
    if baseline.accuracy<gate.minimum_baseline_accuracy:
        reasons.append("unsupported_baseline_quality")
    if test.accuracy-baseline.accuracy<gate.minimum_accuracy_gain:
        reasons.append("no_accuracy_improvement")
    if test.log_loss-baseline.log_loss>gate.maximum_log_loss_regression:
        reasons.append("calibration_regression")
    if baseline.worst_family_accuracy-test.worst_family_accuracy>gate.maximum_worst_family_drop:
        reasons.append("negative_transfer_by_family")
    if test.abstention_rate>gate.max_ood_abstention:
        reasons.append("excessive_abstention")
    holdout_hash=sha256(_canonical([
        (x.event_id,x.occurred_ms,x.features,x.expected_route,
         x.task_family,x.source_digest,x.consent_receipt,x.privacy_class)
        for x in holdout])).hexdigest()
    return Promotion("REJECTED" if reasons else "READY_FOR_HOST_APPROVAL",
                     candidate.digest,incumbent.digest,test,baseline,
                     tuple(reasons),holdout_hash)

def prepare(proposal:AdaptationProposal,incumbent:RoutingPolicy)->Lifecycle:
    verify_policy(incumbent)
    if (incumbent.status!="approved" or incumbent.workspace_id!=proposal.workspace_id
            or incumbent.target!=proposal.target
            or incumbent.digest!=proposal.base_policy_digest
            or incumbent.digest!=proposal.rollback_policy_digest):
        raise ValueError("invalid frozen rollback anchor")
    return _seal(Lifecycle(proposal.workspace_id,incumbent.digest,
                           incumbent.digest,proposal.proposal_id,
                           "prepared",0,(),""))

def transition(lifecycle:Lifecycle,*,mutation_id:str,expected_revision:int,
               decision:str,host_authorized:bool=False,
               candidate:RoutingPolicy|None=None,
               promotion:Promotion|None=None,
               proposal:AdaptationProposal|None=None,
               incumbent:RoutingPolicy|None=None,
               holdout:tuple[Trace,...]|None=None)->Lifecycle:
    verify_lifecycle(lifecycle)
    if (host_authorized is not True or not _id(mutation_id)
            or mutation_id in lifecycle.seen_mutations
            or type(expected_revision) is not int
            or expected_revision!=lifecycle.revision):
        raise PermissionError("missing host authorization or stale lifecycle CAS")
    status=lifecycle.status
    if decision=="approve":
        if (status!="prepared" or candidate is None or promotion is None
                or proposal is None or incumbent is None or holdout is None
                or candidate.status!="candidate"
                or candidate.workspace_id!=lifecycle.workspace_id
                or incumbent.digest!=lifecycle.fallback_policy_digest
                or proposal.proposal_id!=lifecycle.proposal_id):
            raise ValueError("candidate lacks independent promotion inputs")
        recalculated=evaluate_promotion(proposal,candidate,incumbent,holdout)
        if (recalculated.status!="READY_FOR_HOST_APPROVAL"
                or recalculated!=promotion
                or promotion.candidate_digest!=candidate.digest
                or promotion.incumbent_digest!=lifecycle.fallback_policy_digest):
            raise ValueError("forged, stale or failed independent promotion")
        target=replace(lifecycle,current_policy_digest=candidate.digest,status="active")
    elif decision=="pause" and status=="active":
        target=replace(lifecycle,status="paused")
    elif decision=="resume" and status=="paused":
        target=replace(lifecycle,status="active")
    elif decision=="rollback" and status in ("active","paused"):
        target=replace(lifecycle,current_policy_digest=lifecycle.fallback_policy_digest,
                       status="rolled_back")
    elif decision=="revoke" and status in ("prepared","active","paused","rolled_back"):
        target=replace(lifecycle,current_policy_digest=lifecycle.fallback_policy_digest,
                       status="revoked")
    else:
        raise ValueError("invalid lifecycle transition")
    return _seal(replace(target,revision=target.revision+1,
                         seen_mutations=target.seen_mutations+(mutation_id,)))

def active_policy(lifecycle:Lifecycle,*,candidate:RoutingPolicy,
                  incumbent:RoutingPolicy)->RoutingPolicy:
    verify_lifecycle(lifecycle)
    verify_policy(incumbent)
    if (incumbent.digest!=lifecycle.fallback_policy_digest
            or incumbent.workspace_id!=lifecycle.workspace_id):
        raise ValueError("fallback policy corruption")
    if lifecycle.status!="active":
        return incumbent
    verify_policy(candidate)
    if candidate.digest!=lifecycle.current_policy_digest:
        raise ValueError("active candidate digest mismatch")
    return seal(replace(candidate,status="approved"))
