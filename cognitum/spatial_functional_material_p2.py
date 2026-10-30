"""C15 T4 P2: adversarial, interval-bounded conditional physics-claim audit.

No physical certification or source authentication. P1 is invoked to reject
inconsistent baseline contracts. SciPy HiGHS is optional and cannot silently
turn solver unavailability into a consistency finding.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Optional

from cognitum.proto import spatial_functional_material_pb2 as b
from cognitum.proto import spatial_functional_material_p2_pb2 as p
from cognitum.spatial_functional_material import T4Rejected, _ident, _no_unknown, _EVIDENCE, _RELIABLE_CLAIM, _UNIT, analyze as analyze_p1


# Point-interval checks are not rounding certificates or full IEEE interval
# arithmetic. A small scale-aware guard prevents a near-equality false pass.
def _margin(*values: float) -> float:
    return 1e-12 * max(1e-9, *(abs(x) for x in values))


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise T4Rejected(reason)


@dataclass(frozen=True)
class I:
    lo: float
    hi: float
    provisional: bool
    sources: frozenset[str]


def _checked(lo: float, hi: float, provisional: bool, sources: frozenset[str]) -> I:
    _need(math.isfinite(lo) and math.isfinite(hi), 'NONFINITE_INTERVAL')
    _need(lo <= hi, 'REVERSED_INTERVAL')
    return I(lo, hi, provisional, sources)


def _i(value: p.T4P2Interval, dimension: str) -> Optional[I]:
    if not (value.HasField('center') and value.HasField('radius')):
        return None
    a, d = value.center, value.radius
    for q in (a, d):
        _need(q.evidence in _EVIDENCE and _ident(q.source_ref), 'INVALID_QUANTITY_EVIDENCE')
        _need(q.unit in _UNIT and _UNIT[q.unit][0] == dimension, 'DIMENSION_MISMATCH')
        _need(math.isfinite(q.value), 'NONFINITE_QUANTITY')
    factor = _UNIT[a.unit][1]
    centre = a.value * factor
    radius = d.value * _UNIT[d.unit][1]
    _need(math.isfinite(centre) and math.isfinite(radius), 'NONFINITE_CONVERSION')
    _need(radius >= 0, 'NEGATIVE_UNCERTAINTY_RADIUS')
    return _checked(centre-radius, centre+radius,
                    any(q.evidence not in _RELIABLE_CLAIM for q in (a,d)),
                    frozenset((a.source_ref, d.source_ref)))


def _si(value: p.T4P2SIInterval, *, required: bool = False) -> Optional[I]:
    if not required and not value.ByteSize():
        return None
    _need(value.evidence in _EVIDENCE and _ident(value.source_ref), 'INVALID_SI_EVIDENCE')
    _need(math.isfinite(value.center_si) and math.isfinite(value.radius_si), 'NONFINITE_SI_INTERVAL')
    _need(value.radius_si >= 0, 'NEGATIVE_UNCERTAINTY_RADIUS')
    return _checked(value.center_si-value.radius_si, value.center_si+value.radius_si,
                    value.evidence not in _RELIABLE_CLAIM, frozenset((value.source_ref,)))


def _abs(v: I) -> I:
    lower = 0.0 if v.lo <= 0 <= v.hi else min(abs(v.lo),abs(v.hi))
    return _checked(lower, max(abs(v.lo),abs(v.hi)), v.provisional, v.sources)


def _sub(a: I, c: I) -> I:
    return _checked(a.lo-c.hi, a.hi-c.lo, a.provisional or c.provisional, a.sources|c.sources)


def _add(a: I, c: I) -> I:
    return _checked(a.lo+c.lo, a.hi+c.hi, a.provisional or c.provisional, a.sources|c.sources)


def _multiply(a: I, c: I) -> I:
    products=(a.lo*c.lo,a.lo*c.hi,a.hi*c.lo,a.hi*c.hi)
    return _checked(min(products),max(products),a.provisional or c.provisional,a.sources|c.sources)


def _divide(a: I, c: I) -> Optional[I]:
    if c.lo <= 0 or c.hi <= 0:
        return None
    vals=(a.lo/c.lo,a.lo/c.hi,a.hi/c.lo,a.hi/c.hi)
    return _checked(min(vals),max(vals),a.provisional or c.provisional,a.sources|c.sources)


def _positive(v: I, reason: str) -> bool:
    # wholly nonpositive is invalid; overlapping zero is an indeterminate
    # interval, never silently clamped to an arbitrarily small denominator.
    _need(v.hi > 0, reason)
    return v.lo > 0


def _status(out, id: str, model: str, reason: str, status=b.T4_UNDETERMINED,
            v: Optional[I] = None, sources=(), provisional=False, robust=False):
    f=out.findings.add(id=id, conditional_model=model, status=status,
                       robust_for_claimed_intervals=bool(robust and status==b.T4_CONSISTENT_WITH_CLAIMS))
    f.reasons.append(reason)
    f.reasons.append('CONDITIONAL_CLAIM_NOT_PHYSICAL_CERTIFICATION')
    if provisional:
        f.reasons.append('PROVISIONAL_OR_HYPOTHETICAL_EVIDENCE')
    f.source_refs.extend(sorted(set(sources) | (set(v.sources) if v else set())))
    if v is not None:
        f.computed_min_si=v.lo
        f.computed_max_si=v.hi
    return f


def _decision(out, id, model, value: Optional[I], lower: Optional[I], upper: Optional[I], sources, provisional):
    refs=set(sources)
    for v in (value,lower,upper):
        if v: refs |= v.sources; provisional |= v.provisional
    if value is None or lower is None or upper is None:
        return _status(out,id,model,'MISSING_INTERVAL_EVIDENCE',v=value,sources=refs,provisional=provisional)
    m=_margin(value.lo,value.hi,lower.lo,lower.hi,upper.lo,upper.hi)
    if lower.lo > upper.hi + m:
        return _status(out,id,model,'CONTRADICTORY_ALLOWABLE_BOUNDS',b.T4_CONTRADICTS_CLAIMS,value,refs,provisional)
    if value.hi < lower.lo - m or value.lo > upper.hi + m:
        return _status(out,id,model,'ALL_REALIZATIONS_OUTSIDE_SUPPLIED_BOUNDS',b.T4_CONTRADICTS_CLAIMS,value,refs,provisional)
    if value.lo > lower.hi + m and value.hi < upper.lo - m and not provisional:
        return _status(out,id,model,'ROBUST_WITHIN_CALLER_ASSERTED_INTERVALS',b.T4_CONSISTENT_WITH_CLAIMS,value,refs,False,True)
    return _status(out,id,model,'INTERVAL_OVERLAP_OR_PROVISIONAL_EVIDENCE',v=value,sources=refs,provisional=provisional)


def _thermal(v: I, alpha_lo: float, alpha_hi: float, temp_lo: float, temp_hi: float, sources, provisional) -> Optional[I]:
    alpha=_checked(alpha_lo,alpha_hi,provisional,frozenset(sources))
    temp=_checked(temp_lo,temp_hi,provisional,frozenset(sources))
    growth=_multiply(alpha,temp)
    factor=_checked(1+growth.lo,1+growth.hi,growth.provisional,growth.sources)
    if factor.lo <= 0:
        return None
    return _multiply(v,factor)


def _fit(out, check, parts):
    model='TOLERANCED_BORE_SHAFT_CLEARANCE_SI'
    _need(_ident(check.id) and check.bore_part_id in parts and check.shaft_part_id in parts,
          'INVALID_TOLERANCE_FIT_SCOPE')
    _need(check.bore_part_id!=check.shaft_part_id,'SELF_CONNECTION')
    v1=_i(check.bore_diameter,'length'); v2=_i(check.shaft_diameter,'length')
    lo=_i(check.allowed_min_clearance,'length'); hi=_i(check.allowed_max_clearance,'length')
    provisional=any(parts[x].evidence not in _RELIABLE_CLAIM for x in (check.bore_part_id,check.shaft_part_id))
    sources={parts[x].source_ref for x in (check.bore_part_id,check.shaft_part_id)}
    if check.HasField('thermal_range') and not check.thermal_exposure_declared:
        raise T4Rejected('UNDECLARED_THERMAL_INPUT')
    for v in (v1,v2):
        if v and not _positive(v,'NONPOSITIVE_DIAMETER'):
            return _status(out,check.id,model,'DIAMETER_INTERVAL_REACHES_ZERO',sources=sources,provisional=provisional)
    if check.thermal_exposure_declared:
        if not check.HasField('thermal_range') or v1 is None or v2 is None:
            return _status(out,check.id,model,'THERMAL_EVIDENCE_MISSING',sources=sources,provisional=provisional)
        t=check.thermal_range
        values=(t.bore_alpha_min_per_kelvin,t.bore_alpha_max_per_kelvin,t.shaft_alpha_min_per_kelvin,
                t.shaft_alpha_max_per_kelvin,t.delta_temperature_min_kelvin,t.delta_temperature_max_kelvin)
        _need(all(math.isfinite(x) for x in values),'INVALID_THERMAL_MODEL')
        _need(t.evidence in _EVIDENCE and _ident(t.source_ref),'INVALID_THERMAL_EVIDENCE')
        _need(values[0]<=values[1] and values[2]<=values[3] and values[4]<=values[5],'REVERSED_THERMAL_INTERVAL')
        _need(max(abs(x) for x in values[:4]) <= .01 and max(abs(x) for x in values[4:])<=500,
              'THERMAL_RESOURCE_LIMIT')
        sources.add(t.source_ref)
        provisional |= t.evidence not in _RELIABLE_CLAIM
        v1=_thermal(v1,values[0],values[1],values[4],values[5],sources,provisional)
        v2=_thermal(v2,values[2],values[3],values[4],values[5],sources,provisional)
        if v1 is None or v2 is None:
            return _status(out,check.id,model,'THERMAL_EXPANSION_NONPHYSICAL',sources=sources,provisional=provisional)
    return _decision(out,check.id,model,_sub(v1,v2) if v1 and v2 else None,lo,hi,sources,provisional)


def _assembly(out, check, joints, parts):
    model='LINEAR_JOINT_ASSEMBLY_SCIPY_HIGHS'
    _need(_ident(check.id) and 1<=len(check.joint_check_ids)<=12 and len(check.constraints)<=32,
          'INVALID_JOINT_ASSEMBLY')
    ids=list(check.joint_check_ids)
    if not check.constraints:
        return _status(out,check.id,model,'NO_CROSS_JOINT_CONSTRAINTS')
    _need(len(set(ids))==len(ids) and all(x in joints for x in ids), 'UNKNOWN_OR_DUPLICATE_JOINT')
    selected=[joints[x] for x in ids]
    _need(all(j.kind==selected[0].kind and j.kind in (b.T4_PRISMATIC,b.T4_REVOLUTE) for j in selected),
          'MIXED_JOINT_DIMENSIONS')
    dimension='angle' if selected[0].kind==b.T4_REVOLUTE else 'length'
    bounds=[]; sources=set(); provisional=False; uncertain_bounds=False; missing=False
    for j in selected:
        lower=_P1_quantity(j,'lower_limit',dimension)
        upper=_P1_quantity(j,'upper_limit',dimension)
        candidate=_P1_quantity(j,'candidate_position',dimension) if check.enforce_candidate_positions else None
        if lower is None or upper is None or (check.enforce_candidate_positions and candidate is None):
            missing=True; continue
        provisional |= any(p.evidence not in _RELIABLE_CLAIM for p in (parts[j.parent_part_id],parts[j.child_part_id]))
        sources.update((parts[j.parent_part_id].source_ref,parts[j.child_part_id].source_ref))
        for v in (lower,upper,candidate):
            if v: sources |= v.sources; provisional |= v.provisional
        if lower.lo > upper.hi + _margin(lower.lo,upper.hi):
            return _status(out,check.id,model,'JOINT_LIMITS_INVERTED',b.T4_CONTRADICTS_CLAIMS,sources=sources,provisional=provisional)
        if candidate:
            # Proposed positions are required to satisfy the joint's own limits.
            c_lo,c_hi=max(lower.lo,candidate.lo),min(upper.hi,candidate.hi)
        else:
            c_lo,c_hi=lower.lo,upper.hi
        bounds.append((c_lo,c_hi))
    A=[]; B=[]
    for c in check.constraints:
        _need(_ident(c.id) and 1<=len(c.terms)<=12 and len({t.joint_check_id for t in c.terms})==len(c.terms),
              'INVALID_LINEAR_CONSTRAINT')
        _need(all(t.joint_check_id in ids and math.isfinite(t.coefficient) and abs(t.coefficient)<=1e6 for t in c.terms),
              'INVALID_LINEAR_TERM')
        coeff=[0.0]*len(ids)
        for t in c.terms: coeff[ids.index(t.joint_check_id)]=t.coefficient
        _need(any(coeff),'ZERO_LINEAR_CONSTRAINT')
        low=_i(c.lower,dimension); high=_i(c.upper,dimension)
        if low is None or high is None: missing=True; continue
        sources |= low.sources | high.sources
        provisional |= low.provisional or high.provisional
        uncertain_bounds |= (low.lo != low.hi or high.lo != high.hi)
        if low.lo > high.hi + _margin(low.lo,high.hi):
            return _status(out,check.id,model,'LINEAR_BOUNDS_INVERTED',b.T4_CONTRADICTS_CLAIMS,sources=sources,provisional=provisional)
        A.extend((coeff,[-x for x in coeff])); B.extend((high.hi,-low.lo))
    if missing:
        return _status(out,check.id,model,'INCOMPLETE_JOINT_GRAPH',sources=sources,provisional=provisional)
    _need(all(math.isfinite(x) for pair in bounds for x in pair) and
          all(math.isfinite(x) for x in B),'NONFINITE_SOLVER_INPUT')
    if any(lo>hi + _margin(lo,hi) for lo,hi in bounds):
        return _status(out,check.id,model,'DISJOINT_CANDIDATE_LIMITS',b.T4_CONTRADICTS_CLAIMS,sources=sources,provisional=provisional)
    try:
        from scipy.optimize import linprog
    except ImportError:
        return _status(out,check.id,model,'SOLVER_UNAVAILABLE_FAIL_CLOSED',sources=sources,provisional=provisional)
    try:
        import numpy as np
        # Scale the dimensional values and constraint rhs by a common reference
        # magnitude; avoid solver default feasibility tolerance obscuring tiny
        # length/angle contradictions. Require a meaningful numerical margin.
        scale=max(1e-9, max((abs(x) for x in B),default=0),
                  max((abs(x) for pair in bounds for x in pair),default=0))
        result=linprog(c=[0.0]*len(ids),A_ub=np.array(A,dtype=float) if A else None,
                       b_ub=np.array(B,dtype=float)/scale if B else None,
                       bounds=[(x/scale,y/scale) for x,y in bounds], method='highs',
                       options={'presolve':True, 'primal_feasibility_tolerance':1e-9,
                                'dual_feasibility_tolerance':1e-9})
        if result.status == 2:
            return _status(out,check.id,model,'SCIPY_FEASIBILITY_INFEASIBLE',b.T4_CONTRADICTS_CLAIMS,sources=sources,provisional=provisional)
        if result.status != 0 or result.x is None:
            return _status(out,check.id,model,'SOLVER_NONCONCLUSIVE',sources=sources,provisional=provisional)
        x=np.asarray(result.x,dtype=float)
        if not np.isfinite(x).all() or any(np.dot(row,x)>bound/scale + 1e-8 for row,bound in zip(A,B)):
            return _status(out,check.id,model,'SOLVER_RESIDUAL_NOT_VERIFIED',sources=sources,provisional=provisional)
        # A zero-objective LP can stop at an active boundary although other
        # interior witnesses exist. Maximize a common nonnegative slack for
        # cross-joint constraints. An LP 'feasible' result with no numerical
        # margin must abstain (even if a tiny inconsistency is tolerated).
        if A:
            padded=np.column_stack((np.asarray(A,dtype=float), np.ones(len(A))))
            interior=linprog(c=[0.0]*len(ids)+[-1.0], A_ub=padded,
                b_ub=np.asarray(B,dtype=float)/scale,
                bounds=[(v/scale,w/scale) for v,w in bounds]+[(0.0,None)],
                method='highs',options={'presolve':True,
                'primal_feasibility_tolerance':1e-9, 'dual_feasibility_tolerance':1e-9})
            if (interior.status != 0 or interior.x is None or
                not np.isfinite(interior.x).all() or interior.x[-1] <= 1e-8 or
                any(np.dot(row,interior.x[:-1])+interior.x[-1] > bound/scale+1e-8
                    for row,bound in zip(A,B))):
                return _status(out,check.id,model,'NUMERICALLY_MARGINAL_LINEAR_FEASIBILITY',sources=sources,provisional=provisional)
    except (ArithmeticError,ValueError,RuntimeError,TypeError):
        return _status(out,check.id,model,'SOLVER_RUNTIME_NONCONCLUSIVE',sources=sources,provisional=provisional)
    if provisional:
        return _status(out,check.id,model,'SOLVER_FEASIBLE_BUT_PROVISIONAL_EVIDENCE',sources=sources,provisional=True)
    if uncertain_bounds:
        # Existential feasibility under expanded bounds is not proof that
        # every allowed realization of those bounds is feasible.
        return _status(out,check.id,model,'EXISTENTIAL_ONLY_UNCERTAIN_ASSEMBLY',sources=sources)
    return _status(out,check.id,model,'LINEAR_FEASIBILITY_ONLY_NOT_KINEMATIC_CERTIFICATION',
                   b.T4_CONSISTENT_WITH_CLAIMS,sources=sources,robust=True)


def _P1_quantity(j,field,dimension):
    if not j.HasField(field): return None
    q=getattr(j,field)
    _need(q.evidence in _EVIDENCE and _ident(q.source_ref),'INVALID_QUANTITY_EVIDENCE')
    _need(q.unit in _UNIT and _UNIT[q.unit][0]==dimension,'DIMENSION_MISMATCH')
    _need(math.isfinite(q.value) and math.isfinite(q.value*_UNIT[q.unit][1]),'NONFINITE_QUANTITY')
    z=q.value*_UNIT[q.unit][1]
    return I(z,z,q.evidence not in _RELIABLE_CLAIM,frozenset((q.source_ref,)))


def _load(out, load, parts):
    model='ENVELOPE_AXIAL_SHEAR_BENDING_BUCKLING_CYCLIC_SIMPLIFIED'
    _need(_ident(load.id) and load.part_id in parts and 1<=len(load.cases)<=16,
          'INVALID_LOAD_ENVELOPE')
    _need(math.isfinite(load.safety_factor) and 1 <= load.safety_factor <= 1e6,
          'INVALID_SAFETY_FACTOR')
    provisional=parts[load.part_id].evidence not in _RELIABLE_CLAIM
    sources={parts[load.part_id].source_ref}
    area=_i(load.axial_area,'area'); shear_area=_i(load.shear_area,'area')
    section=_si(load.section_modulus)
    normal_allow=_i(load.allowable_normal_stress,'stress')
    shear_allow=_i(load.allowable_shear_stress,'stress')
    buckling=_i(load.compression_buckling_limit,'force')
    static=(area,shear_area,section,normal_allow,shear_allow)
    if any(v is None for v in static):
        return _status(out,load.id,model,'MISSING_LOAD_GEOMETRY_OR_ALLOWANCES',sources=sources,provisional=provisional)
    for v in static:
        sources |= v.sources; provisional |= v.provisional
        if not _positive(v,'NONPOSITIVE_LOAD_GEOMETRY_OR_ALLOWANCE'):
            return _status(out,load.id,model,'UNCERTAIN_ZERO_DIVISOR',sources=sources,provisional=provisional)
    if buckling:
        sources |= buckling.sources; provisional |= buckling.provisional
        if not _positive(buckling,'NONPOSITIVE_BUCKLING_ALLOWANCE'):
            return _status(out,load.id,model,'UNCERTAIN_ZERO_BUCKLING_LIMIT',sources=sources,provisional=provisional)
    case_ids=set(); ratios=[]; incomplete=False
    for case in load.cases:
        _need(_ident(case.id) and case.id not in case_ids, 'INVALID_OR_DUPLICATE_LOAD_CASE')
        case_ids.add(case.id)
        force=_i(case.axial_force,'force'); shear=_i(case.shear_force,'force'); moment=_si(case.bending_moment)
        if force is None or shear is None or moment is None:
            incomplete=True; continue
        sources |= force.sources | shear.sources | moment.sources
        provisional |= force.provisional or shear.provisional or moment.provisional
        f_abs=_abs(force); v_abs=_abs(shear); m_abs=_abs(moment)
        normal=_add(_divide(f_abs,area),_divide(m_abs,section))
        shear_stress=_divide(v_abs,shear_area)
        normal_ratio=_divide(normal,_checked(normal_allow.lo/load.safety_factor,
                                             normal_allow.hi/load.safety_factor,normal_allow.provisional,normal_allow.sources))
        shear_ratio=_divide(shear_stress,_checked(shear_allow.lo/load.safety_factor,
                                                 shear_allow.hi/load.safety_factor,shear_allow.provisional,shear_allow.sources))
        ratios.extend((normal_ratio,shear_ratio))
        # Compression sign convention is negative axial F. A straddling force
        # demands a buckling limit too: never infer 'pure tension'.
        if force.lo < 0:
            if buckling is None:
                incomplete=True
            else:
                comp=_checked(max(0,-force.hi),max(0,-force.lo),force.provisional,force.sources)
                ratios.append(_divide(comp,_checked(buckling.lo/load.safety_factor,
                    buckling.hi/load.safety_factor,buckling.provisional,buckling.sources)))
        if case.cyclic:
            if not case.applied_cycles or not load.fatigue_allowable_cycles or not _ident(load.fatigue_source_ref) or load.fatigue_evidence not in _EVIDENCE:
                incomplete=True
            else:
                sources.add(load.fatigue_source_ref)
                provisional |= load.fatigue_evidence not in _RELIABLE_CLAIM
                frac=case.applied_cycles/load.fatigue_allowable_cycles
                ratios.append(_checked(frac,frac,provisional,frozenset((load.fatigue_source_ref,))))
        elif case.applied_cycles:
            raise T4Rejected('UNDECLARED_CYCLIC_LOADING')
    if not ratios:
        return _status(out,load.id,model,'NO_COMPLETE_LOAD_CASE',sources=sources,provisional=provisional)
    _need(all(v is not None for v in ratios),'UNBOUNDED_LOAD_DIVISION')
    worst=_checked(max(x.lo for x in ratios),max(x.hi for x in ratios),
                   provisional or any(x.provisional for x in ratios),
                   frozenset(sources) | frozenset().union(*(x.sources for x in ratios)))
    m=_margin(worst.lo,worst.hi,1.0)
    if worst.lo > 1 + m:
        return _status(out,load.id,model,'ALL_REALIZATIONS_EXCEED_CLAIMED_LIMIT',b.T4_CONTRADICTS_CLAIMS,worst,sources,provisional)
    if incomplete:
        return _status(out,load.id,model,'MISSING_BUCKLING_FATIGUE_OR_LOAD_CASE_EVIDENCE',v=worst,sources=sources,provisional=provisional)
    if worst.hi < 1-m and not provisional:
        return _status(out,load.id,model,'CONDITIONAL_SIMPLIFIED_ENVELOPE_WITHIN_LIMIT',b.T4_CONSISTENT_WITH_CLAIMS,worst,sources,False,True)
    return _status(out,load.id,model,'LOAD_RATIO_OVERLAPS_LIMIT_OR_IS_PROVISIONAL',v=worst,sources=sources,provisional=provisional)


def analyze(request:p.T4P2ResearchRequest)->p.T4P2ResearchResult:
    _need(isinstance(request,p.T4P2ResearchRequest) and request.schema_version==1 and
          request.research_only and not request.grants_authority and request.HasField('baseline'),
          'INVALID_RESEARCH_CONTRACT')
    _need(_no_unknown(request),'UNKNOWN_PROTO_FIELDS')
    _need(len(request.fits)<=64 and len(request.assemblies)<=32 and len(request.loads)<=64 and
          (len(request.fits)+len(request.assemblies)+len(request.loads))<=128 and
          len(request.SerializeToString())<=120_000,'RESOURCE_LIMIT')
    analyze_p1(request.baseline)  # validates P1 envelope, never authorizes.
    parts={x.id:x for x in request.baseline.parts}
    joints={x.id:x for x in request.baseline.joints}
    out=p.T4P2ResearchResult(graph_id=request.baseline.graph_id,
        conversation_id=request.baseline.conversation_id, research_only=True,
        grants_authority=False,physical_validity_verified=False,
        request_sha256=hashlib.sha256(request.SerializeToString(deterministic=True)).digest())
    ids=set()
    for seq,fn in ((request.fits,lambda x:_fit(out,x,parts)),
                   (request.assemblies,lambda x:_assembly(out,x,joints,parts)),
                   (request.loads,lambda x:_load(out,x,parts))):
        for item in sorted(seq,key=lambda x:x.id):
            _need(_ident(item.id) and item.id not in ids,'DUPLICATE_OR_INVALID_FINDING_ID')
            ids.add(item.id)
            fn(item)
    out.warnings.extend((
        'CALLER_ASSERTED_INPUTS_NOT_AUTHENTICATED',
        'INTERVAL_FEASIBILITY_IS_NOT_FREQUENCY_OR_MEASUREMENT_CALIBRATION',
        'SIMPLIFIED_LOAD_RATIOS_NOT_A_BUCKLING_FATIGUE_OR_FEA_CERTIFICATE',
        'NO_COLLISION_CONTACT_CONSTRAINTS_OR_TRUE_KINEMATIC_LOOP_SOLVER',
        'NO_PHYSICAL_ACTION_AUTHORITY',
    ))
    return out
