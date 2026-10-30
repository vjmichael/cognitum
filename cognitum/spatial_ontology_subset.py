"""C15 T2 P2N: bounded subclass/disjoint-type entailment with evidence separation.

A research-only finite taxonomy subset, NOT an OWL 2 RL implementation. Open-world:
absent type assertions never imply their negation. Caller-supplied "observed"
labels and schema sources are never authenticated. No canonical scene mutation.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
from cognitum.proto import spatial_composition_pb2 as sg
from cognitum.proto import spatial_ontology_subset_pb2 as pb
from cognitum import spatial_composition

MAX_CLASSES = 128
MAX_ASSERTIONS = 512
MAX_DISJOINT = 256
MAX_RELATION_RULES = 64
MAX_REQUEST_BYTES = 140_000

class OntologyRejected(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise OntologyRejected(reason)


def _id(s):
    return isinstance(s, str) and 0 < len(s) <= 128 and all(
        ch.isascii() and (ch.isalnum() or ch in '_-.:') for ch in s)


def _known(msg):
    clean = type(msg)()
    clean.CopyFrom(msg)
    clean.DiscardUnknownFields()
    return clean == msg


def _hash(msg):
    return hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()


def _read_schema(req):
    """Validate the complete ontology before any inference or output allocation."""
    _require(isinstance(req, pb.OntologyAuditRequest) and _known(req) and
             req.schema_version == 1 and req.research_only and not req.grants_authority and
             _id(req.conversation_id) and req.HasField('graph') and
             req.conversation_id == req.graph.conversation_id and
             req.ByteSize() <= MAX_REQUEST_BYTES, 'INVALID_ONTOLOGY_REQUEST')
    try:
        nodes, _, _, _ = spatial_composition.validate(req.graph)
    except spatial_composition.StructureRejected as exc:
        raise OntologyRejected('INVALID_STRUCTURE_GRAPH:' + str(exc)) from exc
    _require(1 <= len(req.classes) <= MAX_CLASSES and
             len(req.assertions) <= MAX_ASSERTIONS and
             len(req.disjoints) <= MAX_DISJOINT and
             len(req.relation_rules) <= MAX_RELATION_RULES, 'ONTOLOGY_CAPACITY_LIMIT')
    classes = {}
    for cls in req.classes:
        _require(_id(cls.class_id) and _id(cls.source_ref) and
                 cls.class_id not in classes and len(cls.parent_class_ids) <= 24 and
                 len(set(cls.parent_class_ids)) == len(cls.parent_class_ids), 'INVALID_ONTOLOGY_CLASS')
        classes[cls.class_id] = tuple(cls.parent_class_ids)
    for name, parents in classes.items():
        _require(all(p in classes and p != name for p in parents), 'UNKNOWN_OR_SELF_PARENT')
    # Strict hierarchy is a documented restriction of this finite subset.
    state = {}
    def check_cycle(name):
        if state.get(name) == 1:
            raise OntologyRejected('TAXONOMY_CYCLE')
        if state.get(name) == 2:
            return
        state[name] = 1
        for parent in classes[name]:
            check_cycle(parent)
        state[name] = 2
    for name in classes:
        check_cycle(name)
    seen = set()
    disjoints = {}
    for d in req.disjoints:
        _require(d.first_class_id in classes and d.second_class_id in classes and
                 d.first_class_id != d.second_class_id and _id(d.source_ref), 'INVALID_DISJOINT_AXIOM')
        key = tuple(sorted((d.first_class_id, d.second_class_id)))
        _require(key not in seen, 'DUPLICATE_DISJOINT_AXIOM')
        seen.add(key)
        disjoints[key] = d.source_ref
    relation_rules = {}
    for rule in req.relation_rules:
        _require(rule.relation in (sg.STRUCTURE_PART_OF, sg.STRUCTURE_CONTAINS,
                  sg.STRUCTURE_CONNECTED_TO) and
                 rule.from_class_id in classes and rule.to_class_id in classes and
                 _id(rule.source_ref) and
                 (rule.relation != sg.STRUCTURE_CONNECTED_TO or
                  rule.from_class_id == rule.to_class_id), 'INVALID_RELATION_TYPE_RULE')
        key = (rule.relation, rule.from_class_id, rule.to_class_id)
        _require(key not in relation_rules, 'DUPLICATE_RELATION_TYPE_RULE')
        relation_rules[key] = rule.source_ref
    claims = defaultdict(list)
    seen_claims = set()
    for a in req.assertions:
        _require(a.node_id in nodes and a.class_id in classes and _id(a.source_ref) and
                 a.evidence in (sg.EVIDENCE_OBSERVED, sg.EVIDENCE_INFERRED, sg.EVIDENCE_HYPOTHETICAL),
                 'INVALID_TYPE_ASSERTION')
        # Do not let a hypothetical scene object provide an "observed" type fact.
        _require(not (nodes[a.node_id].evidence == sg.EVIDENCE_HYPOTHETICAL and
                       a.evidence == sg.EVIDENCE_OBSERVED), 'OBSERVATION_HYPOTHESIS_CONFLATION')
        key = (a.node_id, a.class_id, a.source_ref, a.evidence)
        _require(key not in seen_claims, 'DUPLICATE_TYPE_ASSERTION')
        seen_claims.add(key)
        claims[a.node_id].append(a)
    return nodes, classes, disjoints, claims, relation_rules


def audit(req: pb.OntologyAuditRequest) -> pb.OntologyAuditResult:
    nodes, classes, disjoints, claims, relation_rules = _read_schema(req)
    ancestors_cache = {}
    def ancestors(name):
        if name not in ancestors_cache:
            covered = {name}
            for parent in classes[name]:
                covered.update(ancestors(parent))
            ancestors_cache[name] = frozenset(covered)
        return ancestors_cache[name]
    for name in classes:
        ancestors(name)
    # Explicit domain/range-like signatures add types, not physical geometry.
    # An edge's source kind is caller-supplied: even an OBSERVED edge is not
    # authenticated, and hypothetical edges cannot leak into default results.
    edge_types = defaultdict(list)
    for edge in req.graph.edges:
        for (relation, from_class, to_class), signature_source in relation_rules.items():
            if edge.relation != relation:
                continue
            hypothetical = (edge.evidence == sg.EVIDENCE_HYPOTHETICAL or
                nodes[edge.from_id].evidence == sg.EVIDENCE_HYPOTHETICAL or
                nodes[edge.to_id].evidence == sg.EVIDENCE_HYPOTHETICAL)
            if hypothetical and not req.include_hypotheses:
                continue
            # Undirected CONNECTED_TO uses deterministic endpoint ordering. This
            # narrower subset refuses asymmetric domain/range for connections.
            edge_types[edge.from_id].append((from_class, (edge.source_ref,signature_source), hypothetical))
            edge_types[edge.to_id].append((to_class, (edge.source_ref,signature_source), hypothetical))
    result = pb.OntologyAuditResult(schema_version=1, conversation_id=req.conversation_id,
        graph_id=req.graph.graph_id, graph_sha256=_hash(req.graph),
        request_sha256=_hash(req), research_only=True,
        grants_authority=False, consistent_with_claimed_evidence=True)
    for node_id, node in sorted(nodes.items()):
        # Per class retain support refs and the strongest *admitted* epistemic status.
        support = defaultdict(set)
        nonhypothetical = set()
        for assertion in claims[node_id]:
            hypothetical = (node.evidence == sg.EVIDENCE_HYPOTHETICAL or
                            assertion.evidence == sg.EVIDENCE_HYPOTHETICAL)
            if hypothetical and not req.include_hypotheses:
                continue
            for entailed in ancestors(assertion.class_id):
                support[entailed].add(assertion.source_ref)
                if not hypothetical:
                    nonhypothetical.add(entailed)
        for class_id, origins, hypothetical in edge_types[node_id]:
            for entailed in ancestors(class_id):
                support[entailed].update(origins)
                if not hypothetical:
                    nonhypothetical.add(entailed)
        finding = result.findings.add(node_id=node_id,
            hypothetical=node.evidence == sg.EVIDENCE_HYPOTHETICAL)
        for class_id in sorted(support):
            finding.entailed_types.add(class_id=class_id,
                support_sources=sorted(support[class_id]),
                hypothetical=class_id not in nonhypothetical)
        for (a,b),source_ref in sorted(disjoints.items()):
            if a in support and b in support:
                finding.disjoint_conflicts.append(f'{a}|{b}|{source_ref}')
        finding.conflicted = bool(finding.disjoint_conflicts)
        if finding.conflicted:
            result.consistent_with_claimed_evidence = False
    result.warnings.extend([
        'FINITE_SUBCLASS_DISJOINT_SUBSET_NOT_COMPLETE_OWL2_REASONING',
        'OPEN_WORLD_ABSENCE_IS_NOT_NEGATION',
        'SCHEMA_AND_ASSERTION_PROVENANCE_NOT_AUTHENTICATED',
        'INFERRED_TYPES_ARE_CLAIMS_NOT_SENSOR_FACTS',
        'RELATION_SIGNATURES_ARE_CALLER_DECLARED_NOT_PHYSICAL_CONSTRAINTS',
        'NO_CANONICAL_SCENE_OR_T3_GEOMETRY_MUTATION',
        'NO_ACTION_AUTHORITY',
    ])
    if req.include_hypotheses:
        result.warnings.append('HYPOTHETICAL_RESULTS_INCLUDED_BY_EXPLICIT_REQUEST')
    return result


def audit_p2m_handoff(feature_request, feature_response, handoff):
    """Cross-component integration: revalidate the P2M handoff before reasoning.

    Only explicit image-space *hypotheses* can enter this taxonomy; any attempt
    to present derived 3D geometry or observed structural edges is rejected.
    """
    from cognitum import spatial_p2m_pipeline as p2m
    from cognitum import spatial_p2l_appearance as p2l
    _require(handoff.schema_version == 1 and handoff.research_only and
             not handoff.grants_authority and handoff.t2_structure_candidate_only and
             handoff.t3_projection_blocked_without_calibration and
             handoff.canonical_scene_mutation_blocked, 'INVALID_P2M_HANDOFF')
    p2m.check_response(feature_request, feature_response)
    frames, _, _ = p2m._validate_request(feature_request)
    candidate_to_box = {
        p2l.observation_id(feature_request.sequence_id, d, index): (frame, index)
        for frame, dets in frames.items() for index, d in enumerate(dets)
    }
    _require(len(handoff.candidates) == len(candidate_to_box), 'INCOMPLETE_P2M_CANDIDATES')
    labels = {}
    for c in handoff.candidates:
        _require(c.detection_id in candidate_to_box and
                 c.tracker_id > 0 and c.tracker_id <= 1_000_000, 'INVALID_P2M_CANDIDATE')
        key = candidate_to_box[c.detection_id]
        _require(key not in labels, 'DUPLICATE_P2M_CANDIDATE')
        labels[key] = c.tracker_id
    expected = p2m.integration_handoff(feature_request, feature_response, labels)
    _require(expected.SerializeToString(deterministic=True) ==
             handoff.SerializeToString(deterministic=True), 'P2M_HANDOFF_MISMATCH')
    graph = handoff.t2_hypothetical_graph
    _require(all(n.evidence == sg.EVIDENCE_HYPOTHETICAL and
                 n.kind == '2d_identity_hypothesis' for n in graph.nodes) and
             len(graph.edges) == 0, 'UNSAFE_P2M_STRUCTURE_CLAIM')
    req = pb.OntologyAuditRequest(schema_version=1, conversation_id=graph.conversation_id,
         research_only=True, include_hypotheses=True)
    req.graph.CopyFrom(graph)
    req.classes.add(class_id='2d_evidence_candidate',source_ref='p2m.contract')
    req.classes.add(class_id='2d_identity_hypothesis',
       parent_class_ids=['2d_evidence_candidate'],source_ref='p2m.contract')
    for node in graph.nodes:
        req.assertions.add(node_id=node.node_id,class_id='2d_identity_hypothesis',
            evidence=sg.EVIDENCE_HYPOTHETICAL, source_ref=node.source_ref)
    return audit(req)
