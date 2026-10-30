"""C10 P1: bounded, exact, offline Boolean SAT + integer difference logic.

Host-inert reference. No formula parsing from model text, no authority, no code
execution, no implicit proof that a natural-language question was formalized
correctly. UNSAT requires a full Boolean enumeration certificate; SAT requires
an independently verifiable exact integer model. No external SMT dependency.
"""
from __future__ import annotations
import hashlib
import re

from google.protobuf.message import DecodeError
from .proto import formal_pb2 as pb

MAX_REQUEST = 8192
MAX_RESULT = 131072
MAX_ATOMS = 10
MAX_INTS = 8
MAX_CLAUSES = 48
MAX_LITERALS = 8
MAX_ASSIGNMENTS = 1024
MAX_BOUND = 1_000_000
ZERO = "$ZERO"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z", re.ASCII)


def _decode(data: bytes, cls, limit: int):
    if type(data) is not bytes or not (0 < len(data) <= limit):
        raise ValueError("invalid or oversized Protobuf frame")
    obj = cls()
    try:
        obj.ParseFromString(data)
    except DecodeError as exc:
        raise ValueError("invalid Protobuf wire") from exc
    clean = cls()
    clean.CopyFrom(obj)
    clean.DiscardUnknownFields()
    if clean != obj or obj.SerializeToString(deterministic=True) != data:
        raise ValueError("unknown, duplicate or noncanonical Protobuf field")
    return obj


def _encode(obj, limit=MAX_RESULT):
    data = obj.SerializeToString(deterministic=True)
    if not 0 < len(data) <= limit:
        raise ValueError("Protobuf output exceeds size limit")
    return data


def _valid_name(name: str):
    return bool(NAME.fullmatch(name))


def validate_request(request: pb.SolveRequest):
    if request.schema_version != 1:
        raise ValueError("unsupported formal contract version")
    if len(request.atoms) > MAX_ATOMS or len(request.integer_variables) > MAX_INTS:
        raise ValueError("bounded formula variables exceeded")
    if len(request.clauses) > MAX_CLAUSES or request.max_assignments > MAX_ASSIGNMENTS:
        raise ValueError("bounded solve budget exceeded")
    ints = list(request.integer_variables)
    bools = list(request.boolean_variables)
    if (len(set(ints)) != len(ints) or len(set(bools)) != len(bools) or
        any(not _valid_name(x) for x in ints + bools) or set(ints).intersection(bools) or
        len(bools) > MAX_ATOMS):
        raise ValueError("invalid, overlapping or duplicate variable identifiers")
    seen_bools = set()
    for atom in request.atoms:
        kind = atom.WhichOneof('predicate')
        if kind == 'boolean_name':
            if atom.boolean_name not in bools or atom.boolean_name in seen_bools:
                raise ValueError("undefined or duplicated Boolean atom")
            seen_bools.add(atom.boolean_name)
        elif kind == 'difference':
            d = atom.difference
            if (d.left not in ints + [ZERO] or d.right not in ints + [ZERO] or
                    not -MAX_BOUND <= d.bound <= MAX_BOUND):
                raise ValueError("undefined integer variable or unbounded difference")
        else:
            raise ValueError("missing atom predicate")
    if seen_bools != set(bools):
        raise ValueError("every declared Boolean must have one atom")
    for clause in request.clauses:
        if len(clause.literals) > MAX_LITERALS:
            raise ValueError("clause literal cap exceeded")
        if any(abs(x) < 1 or abs(x) > len(request.atoms) for x in clause.literals):
            raise ValueError("invalid 1-based clause atom reference")


def _literal_true(literal: int, mask: int):
    yes = bool(mask & (1 << (abs(literal)-1)))
    return yes if literal > 0 else not yes


def _first_false_clause(request, mask):
    for j, clause in enumerate(request.clauses, 1):
        if not any(_literal_true(lit, mask) for lit in clause.literals):
            return j
    return 0


def _edges(request, mask):
    indices = {ZERO: 0, **{name: i+1 for i, name in enumerate(request.integer_variables)}}
    edges = []  # (source, destination, weight, 1-based atom index)
    for index, atom in enumerate(request.atoms, 1):
        if atom.WhichOneof('predicate') != 'difference':
            continue
        d = atom.difference
        if mask & (1 << (index-1)):
            # left - right <= bound  ==>  right -> left (bound)
            edges.append((indices[d.right], indices[d.left], int(d.bound), index))
        else:
            # Integers: not (left-right <= bound) ==> right-left <= -bound-1.
            edges.append((indices[d.left], indices[d.right], -int(d.bound)-1, index))
    return edges


def _difference_model_or_cycle(request, mask):
    """Exact Bellman-Ford potential or a directed negative cycle certificate."""
    vertices = len(request.integer_variables) + 1
    distances = [0] * vertices
    predecessor = [None] * vertices
    edges = _edges(request, mask)
    changed = None
    for _ in range(vertices):
        changed = None
        for u, v, weight, atom_index in edges:
            if distances[v] > distances[u] + weight:
                distances[v] = distances[u] + weight
                predecessor[v] = (u, atom_index)
                changed = v
        if changed is None:
            break
    if changed is None:
        # Normalize the distinguished ZERO constant to exactly integer zero.
        return ([x - distances[0] for x in distances], None)
    node = changed
    for _ in range(vertices):
        node = predecessor[node][0]
    start = node
    backwards = []
    while True:
        parent, atom_index = predecessor[node]
        backwards.append(atom_index)
        node = parent
        if node == start:
            break
        if len(backwards) > vertices:
            raise AssertionError("cycle extraction violated Bellman-Ford invariant")
    cycle = list(reversed(backwards))
    if not _check_cycle(request, mask, cycle):
        raise AssertionError("invalid internal negative-cycle witness")
    return None, cycle


def _check_cycle(request, mask, cycle):
    if not cycle or len(cycle) > len(request.integer_variables) + 1:
        return False
    edges = {idx: (u, v, cost) for u, v, cost, idx in _edges(request, mask)}
    if len(set(cycle)) != len(cycle) or any(x not in edges for x in cycle):
        return False
    total = 0
    first = None
    end = None
    for idx in cycle:
        u, v, cost = edges[idx]
        if first is None:
            first = u
        elif u != end:
            return False
        end = v
        total += cost
    return end == first and total < 0


def solve_frame(request_frame: bytes) -> bytes:
    request = _decode(request_frame, pb.SolveRequest, MAX_REQUEST)
    validate_request(request)
    digest = hashlib.sha256(request_frame).digest()
    reply = pb.SolveResult(schema_version=1, status=pb.UNKNOWN,
                           reason_code='ASSIGNMENT_BUDGET_EXCEEDED',
                           request_sha256=digest)
    limit = request.max_assignments or MAX_ASSIGNMENTS
    total = 1 << len(request.atoms)
    for mask in range(min(total, limit)):
        reply.assignments_checked += 1
        wrong = _first_false_clause(request, mask)
        if wrong:
            reply.exhaustive_leaves.add(false_clause=wrong)
            continue
        model, cycle = _difference_model_or_cycle(request, mask)
        if cycle is not None:
            reply.exhaustive_leaves.add(negative_cycle_atoms=cycle)
            continue
        reply.status = pb.SAT
        reply.reason_code = 'EXACT_INTEGER_MODEL'
        del reply.exhaustive_leaves[:]
        reply.atom_values.extend(bool(mask & (1 << i)) for i in range(len(request.atoms)))
        for i, name in enumerate(request.integer_variables, 1):
            reply.integer_values.add(name=name, value=model[i])
        return _encode(reply)
    if limit >= total:
        reply.status = pb.UNSAT
        reply.reason_code = 'EXHAUSTIVE_CLAUSE_OR_NEGATIVE_CYCLE_CERTIFICATE'
    else:
        del reply.exhaustive_leaves[:]
    try:
        return _encode(reply)
    except ValueError:
        return _encode(pb.SolveResult(schema_version=1, status=pb.UNKNOWN,
                       reason_code='CERTIFICATE_SIZE_LIMIT', request_sha256=digest,
                       assignments_checked=reply.assignments_checked))


def verify_frame(request_frame: bytes, result_frame: bytes) -> bytes:
    """Independent check: no call to solve_frame or Bellman-Ford searching."""
    try:
        request = _decode(request_frame, pb.SolveRequest, MAX_REQUEST)
        result = _decode(result_frame, pb.SolveResult, MAX_RESULT)
        validate_request(request)
        if (result.schema_version != 1 or result.request_sha256 != hashlib.sha256(request_frame).digest() or
                result.formalization_verified or result.host_approved or
                result.assignments_checked > (1 << len(request.atoms)) or
                result.assignments_checked > (request.max_assignments or MAX_ASSIGNMENTS)):
            raise ValueError("unbound result or dishonest assurance")
        if result.status == pb.SAT:
            if (result.reason_code != 'EXACT_INTEGER_MODEL' or result.exhaustive_leaves or
                    len(result.atom_values) != len(request.atoms) or
                    len(result.integer_values) != len(request.integer_variables)):
                raise ValueError("malformed SAT witness")
            values = {ZERO: 0}
            for expected_name, item in zip(request.integer_variables, result.integer_values):
                if item.name != expected_name:
                    raise ValueError("misordered or missing integer valuation")
                values[item.name] = item.value
            mask = sum((1 << i) for i, yes in enumerate(result.atom_values) if yes)
            if _first_false_clause(request, mask):
                raise ValueError("model falsifies a clause")
            for i, atom in enumerate(request.atoms):
                if atom.WhichOneof('predicate') == 'difference':
                    d = atom.difference
                    holds = values[d.left] - values[d.right] <= d.bound
                    if holds != result.atom_values[i]:
                        raise ValueError("model falsifies theory assignment")
            if result.assignments_checked != mask + 1:
                raise ValueError("incorrect search transcript")
            return _encode(pb.CheckResult(evidence_valid=True, reason_code='SAT_MODEL_VALID'))
        if result.status == pb.UNSAT:
            count = 1 << len(request.atoms)
            if (result.reason_code != 'EXHAUSTIVE_CLAUSE_OR_NEGATIVE_CYCLE_CERTIFICATE' or
                    result.assignments_checked != count or len(result.exhaustive_leaves) != count or
                    result.atom_values or result.integer_values):
                raise ValueError("missing exhaustive UNSAT certificate")
            for mask, leaf in enumerate(result.exhaustive_leaves):
                first = _first_false_clause(request, mask)
                if first:
                    if leaf.false_clause != first or leaf.negative_cycle_atoms:
                        raise ValueError("bad conflicting-clause certificate")
                elif leaf.false_clause or not _check_cycle(request, mask, list(leaf.negative_cycle_atoms)):
                    raise ValueError("invalid difference-logic negative cycle")
            return _encode(pb.CheckResult(evidence_valid=True, reason_code='UNSAT_CERTIFICATE_VALID'))
        if result.status == pb.UNKNOWN:
            if (result.reason_code not in ('ASSIGNMENT_BUDGET_EXCEEDED', 'CERTIFICATE_SIZE_LIMIT') or
                    result.atom_values or result.integer_values or result.exhaustive_leaves):
                raise ValueError("UNKNOWN must not carry proof claims")
            return _encode(pb.CheckResult(evidence_valid=False, reason_code='UNKNOWN_NOT_A_PROOF'))
        raise ValueError("unknown result status")
    except (ValueError, OverflowError):
        return _encode(pb.CheckResult(evidence_valid=False, reason_code='INVALID_EVIDENCE'))


def check_frame(check_frame: bytes) -> bytes:
    request = _decode(check_frame, pb.CheckRequest, MAX_REQUEST + MAX_RESULT + 1024)
    return verify_frame(request.solve_request, request.solve_result)


def _property_inputs(frame: bytes):
    prop = _decode(frame, pb.PropertyRequest, MAX_REQUEST)
    if not prop.HasField('assumptions'):
        raise ValueError('property missing assumptions')
    req = prop.assumptions
    validate_request(req)
    if not 1 <= abs(prop.required_literal) <= len(req.atoms):
        raise ValueError('property literal must name an existing atom')
    base = _encode(req, MAX_REQUEST)
    counterexample_req = pb.SolveRequest()
    counterexample_req.CopyFrom(req)
    counterexample_req.clauses.add(literals=[-prop.required_literal])
    validate_request(counterexample_req)
    negate = _encode(counterexample_req, MAX_REQUEST)
    return prop, base, negate


def prove_frame(property_frame: bytes) -> bytes:
    """Check assumptions, then assumptions AND NOT proposition; no NL claims."""
    prop, base, negate = _property_inputs(property_frame)
    assumptions = pb.SolveResult.FromString(solve_frame(base))
    negative = pb.SolveResult.FromString(solve_frame(negate))
    if assumptions.status == pb.UNSAT:
        verdict = pb.INCONSISTENT_ASSUMPTIONS
    elif assumptions.status == pb.SAT and negative.status == pb.UNSAT:
        verdict = pb.PROVEN
    elif negative.status == pb.SAT:
        verdict = pb.COUNTEREXAMPLE
    else:
        verdict = pb.INCONCLUSIVE
    return _encode(pb.PropertyResult(schema_version=1, verdict=verdict,
                   property_sha256=hashlib.sha256(property_frame).digest(),
                   assumptions_check=assumptions, negated_property_check=negative),
                   MAX_RESULT * 2 + 2048)


def verify_property_frame(property_frame: bytes, proof_frame: bytes) -> bytes:
    """Separate verifier checks both exact models or exhaustive proofs."""
    try:
        _prop, base, negate = _property_inputs(property_frame)
        proof = _decode(proof_frame, pb.PropertyResult, MAX_RESULT * 2 + 2048)
        if (proof.schema_version != 1 or
            proof.property_sha256 != hashlib.sha256(property_frame).digest() or
            proof.formalization_verified or proof.host_approved or
            not proof.HasField('assumptions_check') or not proof.HasField('negated_property_check')):
            raise ValueError('misbound property evidence')
        left = pb.CheckResult.FromString(verify_frame(base, _encode(proof.assumptions_check)))
        right = pb.CheckResult.FromString(verify_frame(negate, _encode(proof.negated_property_check)))
        a, n = proof.assumptions_check.status, proof.negated_property_check.status
        expected = (
            pb.INCONSISTENT_ASSUMPTIONS if a == pb.UNSAT else
            pb.PROVEN if a == pb.SAT and n == pb.UNSAT else
            pb.COUNTEREXAMPLE if n == pb.SAT else pb.INCONCLUSIVE
        )
        if expected != proof.verdict:
            raise ValueError('wrong property verdict')
        if expected == pb.INCONCLUSIVE:
            return _encode(pb.CheckResult(evidence_valid=False,reason_code='INCONCLUSIVE_NO_PROOF'))
        if (expected == pb.INCONSISTENT_ASSUMPTIONS and (not left.evidence_valid or n == pb.SAT)) or (
            expected == pb.PROVEN and (not left.evidence_valid or not right.evidence_valid)) or (
            expected == pb.COUNTEREXAMPLE and (not right.evidence_valid or a == pb.UNSAT)):
            raise ValueError('missing or contradictory underlying evidence')
        return _encode(pb.CheckResult(evidence_valid=True, reason_code='PROPERTY_EVIDENCE_VALID'))
    except (ValueError, OverflowError):
        return _encode(pb.CheckResult(evidence_valid=False,reason_code='INVALID_PROPERTY_EVIDENCE'))
