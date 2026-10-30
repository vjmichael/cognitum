"""C15 T4 P1: conditional, unit-checked, read-only engineering claim audit.

Unlike a physics solver or a trusted inspection, this reference only checks
whether *caller-supplied* numeric claims are mutually consistent. It never
certifies safety, true material properties, provenance, or physical affordances.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Optional

from cognitum.proto import spatial_functional_material_pb2 as pb


class T4Rejected(ValueError):
    """Bad contract: not a conditional engineering finding."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T4Rejected(code)


_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z", re.ASCII)


def _ident(s: str) -> bool:
    return isinstance(s, str) and bool(_ID.fullmatch(s))


def _no_unknown(message) -> bool:
    clean = type(message)()
    clean.CopyFrom(message)
    clean.DiscardUnknownFields()
    return clean == message


# One-dimensional base quantity: conversion factor to the SI unit. This is an
# intentionally small, inspectable subset, not a general units parser.
_UNIT = {
    pb.T4_METER: ("length", 1.0),
    pb.T4_MILLIMETER: ("length", 0.001),
    pb.T4_NEWTON: ("force", 1.0),
    pb.T4_KILONEWTON: ("force", 1000.0),
    pb.T4_PASCAL: ("stress", 1.0),
    pb.T4_MEGAPASCAL: ("stress", 1_000_000.0),
    pb.T4_NEWTON_PER_METER: ("stiffness", 1.0),
    pb.T4_NEWTON_PER_MILLIMETER: ("stiffness", 1000.0),
    pb.T4_RADIAN: ("angle", 1.0),
    pb.T4_DEGREE: ("angle", math.pi / 180.0),
    pb.T4_SQUARE_METER: ("area", 1.0),
    pb.T4_SQUARE_MILLIMETER: ("area", 1e-6),
}
_EVIDENCE = frozenset((pb.T4_MEASUREMENT_ASSERTED, pb.T4_DATASHEET_ASSERTED,
                      pb.T4_INFERRED, pb.T4_HYPOTHETICAL))
_RELIABLE_CLAIM = frozenset((pb.T4_MEASUREMENT_ASSERTED, pb.T4_DATASHEET_ASSERTED))


def _quantity(check, field: str, dimension: str) -> Optional[tuple[float, int, str]]:
    if not check.HasField(field):
        return None
    qty = getattr(check, field)
    _require(qty.evidence in _EVIDENCE and _ident(qty.source_ref), "INVALID_QUANTITY_EVIDENCE")
    _require(qty.unit in _UNIT and _UNIT[qty.unit][0] == dimension, "DIMENSION_MISMATCH")
    _require(math.isfinite(qty.value), "NONFINITE_QUANTITY")
    si = qty.value * _UNIT[qty.unit][1]
    _require(math.isfinite(si), "NONFINITE_CONVERSION")
    return si, qty.evidence, qty.source_ref


def _collect(check, specs: tuple[tuple[str, str], ...]):
    values = [_quantity(check, field, dim) for field, dim in specs]
    sources = sorted({value[2] for value in values if value is not None})
    provisional = any(value is not None and value[1] not in _RELIABLE_CLAIM
                      for value in values)
    return values, sources, provisional


def _close(a: float, b: float) -> bool:
    # Uncertain floating-point boundaries never become a proof of a pass.
    # This conservative band also reflects double conversion of unit claims.
    return abs(a - b) <= 1e-12 * max(1e-12, abs(a), abs(b))


def _emit(result, *, identity, model, values, sources, provisional,
          observed=None, low=None, high=None, invalid=None, part_provisional=False):
    f = result.findings.add(id=identity, conditional_model=model)
    f.source_refs.extend(sources)
    if invalid:
        f.status = pb.T4_CONTRADICTS_CLAIMS
        f.reasons.append(invalid)
    elif observed is None or low is None or high is None:
        f.status = pb.T4_UNDETERMINED
        f.reasons.append("MISSING_NUMERIC_EVIDENCE")
    elif not all(math.isfinite(v) for v in (observed, low, high)):
        f.status = pb.T4_UNDETERMINED
        f.reasons.append("NUMERICALLY_UNBOUNDED")
    else:
        f.computed_si = observed
        f.lower_si = low
        f.upper_si = high
        if _close(observed, low) or _close(observed, high):
            f.status = pb.T4_UNDETERMINED
            f.reasons.append("NUMERIC_BOUNDARY_NEEDS_UNCERTAINTY")
        elif low < observed < high:
            if provisional or part_provisional:
                f.status = pb.T4_UNDETERMINED
                f.reasons.append("INFERRED_OR_HYPOTHETICAL_INPUT")
            else:
                f.status = pb.T4_CONSISTENT_WITH_CLAIMS
                f.reasons.append("ARITHMETICALLY_CONSISTENT_NOT_PHYSICALLY_VERIFIED")
        else:
            f.status = pb.T4_CONTRADICTS_CLAIMS
            f.reasons.append("BOUNDS_VIOLATED_UNDER_SUPPLIED_ASSUMPTIONS")
    if provisional or part_provisional:
        f.reasons.append("PROVISIONAL_CLAIMS_NOT_REAL_WORLD_MEASUREMENTS")
    f.reasons.append("NO_PHYSICAL_VALIDITY_OR_ACTION_AUTHORITY")


def _nonnegative(value, label):
    if value is not None:
        _require(value[0] >= 0, "NEGATIVE_" + label)


def _positive(value, label):
    if value is not None:
        _require(value[0] > 0, "NONPOSITIVE_" + label)


def analyze(request: pb.T4ResearchRequest) -> pb.T4ResearchResult:
    _require(isinstance(request, pb.T4ResearchRequest) and
             request.schema_version == 1 and request.research_only and
             not request.grants_authority, "INVALID_RESEARCH_CONTRACT")
    _require(_no_unknown(request), "UNKNOWN_PROTO_FIELDS")
    _require(_ident(request.graph_id) and _ident(request.conversation_id), "INVALID_SCOPE")
    _require(len(request.parts) <= 128 and len(request.fits) <= 128 and
             len(request.joints) <= 128 and len(request.stresses) <= 128 and
             len(request.deflections) <= 128 and
             sum(map(len, (request.fits, request.joints, request.stresses,
                           request.deflections))) <= 256 and
             len(request.SerializeToString()) <= 120_000, "RESOURCE_LIMIT")

    parts = {}
    for part in request.parts:
        _require(_ident(part.id) and _ident(part.kind) and
                 _ident(part.source_ref) and part.evidence in _EVIDENCE,
                 "INVALID_PART")
        _require(part.id not in parts, "DUPLICATE_PART")
        parts[part.id] = part

    result = pb.T4ResearchResult(
        graph_id=request.graph_id, conversation_id=request.conversation_id,
        research_only=True, grants_authority=False, physical_validity_verified=False,
        request_sha256=hashlib.sha256(request.SerializeToString(deterministic=True)).digest(),
    )
    used = set()

    def _validate(check, part_ids):
        _require(_ident(check.id) and check.id not in used, "INVALID_OR_DUPLICATE_CHECK")
        used.add(check.id)
        _require(all(pid in parts for pid in part_ids), "UNKNOWN_PART")
        if len(part_ids) > 1:
            _require(len(set(part_ids)) == len(part_ids), "SELF_CONNECTION")
        return any(parts[pid].evidence not in _RELIABLE_CLAIM for pid in part_ids)

    for fit in sorted(request.fits, key=lambda x: x.id):
        part_provisional = _validate(fit, (fit.bore_part_id, fit.shaft_part_id))
        specs = (("bore_diameter", "length"), ("shaft_diameter", "length"),
                 ("minimum_clearance", "length"), ("maximum_clearance", "length"))
        values, sources, provisional = _collect(fit, specs)
        bore, shaft, minimum, maximum = values
        _positive(bore, "BORE_DIAMETER"); _positive(shaft, "SHAFT_DIAMETER")
        invalid = "REVERSED_CLEARANCE_INTERVAL" if minimum and maximum and minimum[0] > maximum[0] else None
        _emit(result, identity=fit.id, model="BORE_MINUS_SHAFT_CLEARANCE_M",
              values=values, sources=sources, provisional=provisional,
              part_provisional=part_provisional,
              observed=bore[0]-shaft[0] if bore and shaft else None,
              low=minimum[0] if minimum else None,
              high=maximum[0] if maximum else None, invalid=invalid)

    for joint in sorted(request.joints, key=lambda x: x.id):
        part_provisional = _validate(joint, (joint.parent_part_id, joint.child_part_id))
        _require(joint.kind in (pb.T4_FIXED, pb.T4_REVOLUTE, pb.T4_PRISMATIC), "UNSUPPORTED_JOINT")
        dim = "angle" if joint.kind == pb.T4_REVOLUTE else "length"
        specs = (("lower_limit", dim), ("upper_limit", dim), ("candidate_position", dim))
        values, sources, provisional = _collect(joint, specs)
        lower, upper, candidate = values
        invalid = "REVERSED_JOINT_RANGE" if lower and upper and lower[0] > upper[0] else None
        if (joint.kind == pb.T4_FIXED and all(x is not None for x in values) and
                any(x[0] != 0 for x in values)):
            invalid = "FIXED_JOINT_REQUIRES_ZERO_DISPLACEMENT"
        if joint.kind == pb.T4_FIXED:
            # A zero position for a fixed joint is compatible; the degenerate
            # interval does not admit strict inequalities as a normal joint does.
            if not invalid and all(x is not None for x in values):
                invalid = None
                if not (provisional or part_provisional):
                    f = result.findings.add(id=joint.id, conditional_model="FIXED_ZERO_DISPLACEMENT_M")
                    f.source_refs.extend(sources)
                    f.status = pb.T4_CONSISTENT_WITH_CLAIMS
                    f.reasons.extend(["ARITHMETICALLY_CONSISTENT_NOT_PHYSICALLY_VERIFIED",
                                      "NO_PHYSICAL_VALIDITY_OR_ACTION_AUTHORITY"])
                    continue
        _emit(result, identity=joint.id,
              model=("REVOLUTE_POSITION_RAD" if joint.kind == pb.T4_REVOLUTE else
                     "PRISMATIC_POSITION_M" if joint.kind == pb.T4_PRISMATIC else "FIXED_ZERO_DISPLACEMENT_M"),
              values=values, sources=sources, provisional=provisional,
              part_provisional=part_provisional,
              observed=candidate[0] if candidate else None,
              low=lower[0] if lower else None,
              high=upper[0] if upper else None, invalid=invalid)

    for stress in sorted(request.stresses, key=lambda x: x.id):
        part_provisional = _validate(stress, (stress.part_id,))
        specs = (("applied_force", "force"), ("cross_section_area", "area"),
                 ("allowable_stress", "stress"))
        values, sources, provisional = _collect(stress, specs)
        force, area, limit = values
        _nonnegative(force, "APPLIED_FORCE"); _positive(area, "AREA"); _positive(limit, "ALLOWABLE_STRESS")
        _require(math.isfinite(stress.safety_factor) and
                 1.0 <= stress.safety_factor <= 1_000_000.0,
                 "INVALID_SAFETY_FACTOR")
        sigma = force[0] / area[0] if force and area else None
        allowance = limit[0] / stress.safety_factor if limit else None
        _emit(result, identity=stress.id, model="UNIAXIAL_STRESS_PA_F_OVER_AREA",
              values=values, sources=sources, provisional=provisional,
              part_provisional=part_provisional, observed=sigma, low=-1.0,
              high=allowance)

    for deflection in sorted(request.deflections, key=lambda x: x.id):
        part_provisional = _validate(deflection, (deflection.part_id,))
        specs = (("applied_force", "force"), ("linear_stiffness", "stiffness"),
                 ("maximum_deflection", "length"))
        values, sources, provisional = _collect(deflection, specs)
        force, stiffness, maximum = values
        _nonnegative(force, "APPLIED_FORCE"); _positive(stiffness, "STIFFNESS")
        _nonnegative(maximum, "MAX_DEFLECTION")
        disp = force[0]/stiffness[0] if force and stiffness else None
        _emit(result, identity=deflection.id, model="LINEAR_SPRING_DEFLECTION_M_F_OVER_K",
              values=values, sources=sources, provisional=provisional,
              part_provisional=part_provisional, observed=disp, low=-1.0,
              high=maximum[0] if maximum else None)

    result.warnings.extend((
        "ALL_PROVENANCE_CALLER_ASSERTED_NOT_AUTHENTICATED",
        "NO_VERIFIED_MATERIAL_TESTS_GEOMETRY_OR_CONTACT_PHYSICS",
        "LINEARIZED_UNIAXIAL_MODELS_IGNORE_BUCKLING_FATIGUE_AND_MULTIPLE_LOAD_CASES",
        "NO_PHYSICAL_ACTION_AUTHORITY",
    ))
    return result
