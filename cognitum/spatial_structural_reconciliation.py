"""C15 T2 P2O: audited revisions of competing structural *claims*.

Research-only. Claim retirement and source references are unauthenticated input,
not host permission, sensor truth, canonical belief mutation or physical geometry.
No Bayesian ranking or implicit conflict resolution. Each candidate is isolated.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib

from cognitum import spatial_ontology_subset as ontology
from cognitum.proto import spatial_structural_reconciliation_pb2 as pb

MAX_CANDIDATES = 8
MAX_EVENTS = 128
MAX_PER_CANDIDATE = 64
MAX_ACTIVE = 128
MAX_BYTES = 160_000


class ReconciliationRejected(ValueError):
    pass


def _check(condition, message):
    if not condition:
        raise ReconciliationRejected(message)


def _digest(msg):
    return hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()


def _hash_parts(*values):
    h = hashlib.sha256()
    for v in values:
        h.update(len(v).to_bytes(8, 'big'))
        h.update(v)
    return h.digest()


def _conflicts(audit):
    return {f'{item.node_id}|{key}' for item in audit.findings for key in item.disjoint_conflicts}


def _source_refs(audit):
    return sorted({src for finding in audit.findings for entailment in finding.entailed_types
                   for src in entailment.support_sources})


def _snapshot(template, claims):
    # A new protobuf snapshot, never a mutation to the caller's template.
    r = type(template)()
    r.CopyFrom(template)
    for key in sorted(claims):
        kind, claim = claims[key]
        if kind == 'type':
            r.assertions.add().CopyFrom(claim)
        else:
            r.graph.edges.add().CopyFrom(claim)
    return r


def _preflight(req):
    _check(isinstance(req, pb.T2ReconciliationRequest) and
           ontology._known(req) and req.schema_version == 1 and
           req.research_only and not req.grants_authority and
           ontology._id(req.conversation_id) and
           req.HasField('ontology_template') and
           req.ByteSize() <= MAX_BYTES, 'INVALID_P2O_REQUEST')
    t = req.ontology_template
    _check(t.schema_version == 1 and t.conversation_id == req.conversation_id and
           t.research_only and not t.grants_authority and
           not t.assertions and not t.graph.edges,
           'TEMPLATE_MUST_HAVE_NO_DYNAMIC_CLAIMS')
    try:
        ontology.audit(t)
    except ontology.OntologyRejected as exc:
        raise ReconciliationRejected('INVALID_ONTOLOGY_TEMPLATE:' + str(exc)) from exc
    _check(1 <= len(req.candidates) <= MAX_CANDIDATES and
           1 <= len(req.events) <= MAX_EVENTS, 'P2O_CAPACITY')
    candidates = {}
    for c in req.candidates:
        _check(ontology._id(c.candidate_id) and c.candidate_id not in candidates and
               0 < len(c.explanation) <= 240, 'INVALID_CANDIDATE')
        candidates[c.candidate_id] = c
    events = defaultdict(list)
    used_events = set()
    for e in req.events:
        _check(ontology._id(e.event_id) and e.event_id not in used_events and
               e.candidate_id in candidates and e.sequence == len(events[e.candidate_id]) + 1 and
               e.sequence <= MAX_PER_CANDIDATE and ontology._id(e.source_ref) and
               0 < len(e.rationale) <= 240 and
               e.WhichOneof('change') in ('add_type', 'add_edge', 'retract'),
               'INVALID_EVENT_SEQUENCE_OR_SCOPE')
        used_events.add(e.event_id)
        if e.WhichOneof('change') == 'add_type':
            _check(ontology._id(e.add_type.claim_id) and e.add_type.HasField('claim'),
                   'INVALID_TYPE_EVENT')
        elif e.WhichOneof('change') == 'add_edge':
            _check(ontology._id(e.add_edge.claim_id) and e.add_edge.HasField('edge'),
                   'INVALID_EDGE_EVENT')
        else:
            _check(ontology._id(e.retract.claim_id), 'INVALID_RETRACTION_EVENT')
        events[e.candidate_id].append(e)
    return candidates, events


def reconcile(req: pb.T2ReconciliationRequest) -> pb.T2ReconciliationResult:
    candidates, events = _preflight(req)
    t = req.ontology_template
    out = pb.T2ReconciliationResult(schema_version=1, conversation_id=req.conversation_id,
                                    request_sha256=_digest(req), research_only=True)
    for candidate_id in sorted(candidates):
        claims = {}                  # candidate-local active assertions/edges
        retired = set()              # claim IDs cannot be reused even after retirement
        preceding = _hash_parts(_digest(t), candidate_id.encode('utf-8'), b'P2O-v1')
        previous_audit = ontology.audit(t)
        previous_conflicts = _conflicts(previous_audit)
        for e in events[candidate_id]:
            operation = e.WhichOneof('change')
            if operation == 'retract':
                key = e.retract.claim_id
                _check(key in claims, 'RETRACTION_OF_INACTIVE_OR_UNKNOWN_CLAIM')
                claims.pop(key)
            else:
                key = e.add_type.claim_id if operation == 'add_type' else e.add_edge.claim_id
                _check(key not in claims and key not in retired, 'DUPLICATE_OR_REUSED_CLAIM_ID')
                claim = e.add_type.claim if operation == 'add_type' else e.add_edge.edge
                claims[key] = ('type' if operation == 'add_type' else 'edge', claim)
                _check(len(claims) <= MAX_ACTIVE, 'ACTIVE_CLAIM_CAPACITY')
            retired.add(key)
            snapshot = _snapshot(t, claims)
            try:
                audit = ontology.audit(snapshot)  # validate every intermediate state
            except ontology.OntologyRejected as exc:
                raise ReconciliationRejected('INVALID_REVISED_ONTOLOGY:' + str(exc)) from exc
            conflicts = _conflicts(audit)
            snapshot_sha = _digest(snapshot)
            receipt = _hash_parts(preceding, _digest(e), snapshot_sha, _digest(audit))
            row = out.revisions.add(
                event_id=e.event_id, candidate_id=candidate_id, sequence=e.sequence,
                decision='CLAIMS_CONFLICTED' if conflicts else 'CLAIMS_CONSISTENT',
                introduced_conflicts=sorted(conflicts - previous_conflicts),
                resolved_conflicts=sorted(previous_conflicts - conflicts),
                active_claim_ids=sorted(claims),
                ontology_result_sha256=_digest(audit), snapshot_sha256=snapshot_sha,
                journal_receipt_sha256=receipt, change_source_ref=e.source_ref,
                rationale=e.rationale, supporting_sources=_source_refs(audit))
            previous_conflicts, previous_audit, preceding = conflicts, audit, receipt
        final = out.candidates.add(
            candidate_id=candidate_id,
            final_decision='CLAIMS_CONFLICTED' if previous_conflicts else
                           ('CLAIMS_CONSISTENT' if claims else 'NO_ACTIVE_CLAIMS'),
            total_revisions=len(events[candidate_id]),
            active_claim_ids=sorted(claims),
            unresolved_conflicts=sorted(previous_conflicts),
            final_receipt_sha256=preceding,
            final_ontology_result_sha256=_digest(previous_audit))
        for f in previous_audit.findings:
            for entailed in f.entailed_types:
                final.final_supported_types.append(
                    f'{f.node_id}|{entailed.class_id}|{str(entailed.hypothetical).lower()}')
        if previous_conflicts:
            out.any_conflicts = True
    out.warnings.extend([
        'CALLER_CLAIM_RETRACTIONS_DO_NOT_AUTHENTICATE_SOURCE_OR_DELETE_CANONICAL_FACTS',
        'CONSISTENCY_IS_NOT_CORRECTNESS_OR_PROBABILISTIC_HYPOTHESIS_SELECTION',
        'HYPOTHETICAL_EVIDENCE_NOT_PROMOTED_BY_DEFAULT',
        'OPEN_WORLD_ABSENCE_IS_NOT_NEGATION',
        'JOURNAL_SHA256_IS_NOT_A_SIGNATURE_OR_AUTHORIZATION',
        'READ_ONLY_NO_T3_GEOMETRY_OR_SCENE_MUTATION',
    ])
    return out
