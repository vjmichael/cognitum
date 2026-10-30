"""Fixed *synthetic* separate-partition experiment for P3 falsification.

The independent reference oracle here uses Decimal geometry plus injected
measurement bias; no engineering measurements, field labels or expert review.
It is intentionally NOT a production benchmark or proof of a held-out real set.
"""
from __future__ import annotations
import hashlib
import math
import json
import time
from decimal import Decimal
from pathlib import Path

from cognitum.proto import spatial_functional_material_pb2 as b
from cognitum.proto import spatial_functional_material_p2_pb2 as p2
from cognitum.proto import spatial_functional_material_p3_pb2 as p3
from cognitum.spatial_functional_material_p3 import audit

_PLAN = b'C15-T4-P3-synthetic-only-plan-v1-cal40-holdout40-locked-mechanics'


def quantity(v):
    return b.T4Quantity(value=float(v),unit=b.T4_MILLIMETER,
        evidence=b.T4_MEASUREMENT_ASSERTED,source_ref='synthetic_model_input')


def interval(v, radius):
    z=p2.T4P2Interval()
    z.center.CopyFrom(quantity(v))
    z.radius.CopyFrom(quantity(radius))
    return z


def _scenario(entry, label, partition, kind):
    # P2 has only the asserted nominal dimensions; the reference oracle below
    # uses a separate simulated actual specimen, deliberately sometimes biased.
    nominal_bore=Decimal('10.200')
    nominal_shaft={
        'good':Decimal('10.000'),
        'bad':Decimal('10.500'),
        'biased_pass':Decimal('10.000'),
        'biased_reject':Decimal('10.500'),
        'abstain':Decimal('10.100'),
    }[kind]
    actual_bore=Decimal('10.200')
    actual_shaft={
        'good':Decimal('10.000'),
        'bad':Decimal('10.500'),
        'biased_pass':Decimal('9.850'),
        'biased_reject':Decimal('10.000'),
        'abstain':Decimal('10.030'),
    }[kind]
    clearance=actual_bore-actual_shaft
    # Independent high-precision fixture oracle; it never calls the P2 method.
    cls=(p3.T4P3_OBSERVED_SATISFIES if Decimal('.1') <= clearance <= Decimal('.3')
         else p3.T4P3_OBSERVED_VIOLATES)
    c=entry.cases.add(case_id=label,specimen_group_id='synthetic_specimen_'+label,
        reference_source_ref='synthetic_decimal_oracle_'+label,
        reference_sha256=hashlib.sha256((label+':'+str(clearance)).encode()).digest(),
        partition=partition,reference_kind=p3.T4P3_SYNTHETIC_ORACLE,
        observed_class=cls, finding_id='fit',
        observed_clearance_m=float(clearance/Decimal('1000')))
    x=c.scenario
    x.schema_version=1
    x.research_only=True
    x.baseline.schema_version=1
    x.baseline.research_only=True
    x.baseline.graph_id='graph_'+label
    x.baseline.conversation_id=entry.conversation_id
    for name in ('bore','shaft'):
        x.baseline.parts.add(id=name,kind='part',
            evidence=b.T4_MEASUREMENT_ASSERTED,source_ref='synthetic_part')
    fit=x.fits.add(id='fit',bore_part_id='bore',shaft_part_id='shaft')
    fit.bore_diameter.CopyFrom(interval(nominal_bore,Decimal('.050') if kind=='abstain' else Decimal('.010')))
    fit.shaft_diameter.CopyFrom(interval(nominal_shaft,Decimal('.050') if kind=='abstain' else Decimal('.010')))
    fit.allowed_min_clearance.CopyFrom(interval(Decimal('.1'),0))
    fit.allowed_max_clearance.CopyFrom(interval(Decimal('.3'),0))


def study():
    r=p3.T4P3AuditRequest(schema_version=1,study_id='P3_LOCKED_SYNTHETIC_RESEARCH',
        conversation_id='p3_synthetic_study',research_only=True,
        prespecified_plan_sha256=hashlib.sha256(_PLAN).digest(),
        claimed_nominal_coverage=.9)
    calibration_kinds=('good','bad','good','bad','abstain','good','biased_pass','bad')
    holdout_kinds=('good','biased_pass','bad','biased_reject','abstain','biased_pass','good','bad')
    for index in range(80):
        partition=p3.T4P3_CALIBRATION if index<40 else p3.T4P3_HOLDOUT
        options=calibration_kinds if index<40 else holdout_kinds
        kind=options[index%len(options)]
        _scenario(r,'item_%03d'%index,partition,kind)
    return r


def output():
    r=study()
    result=audit(r)
    # Reference-only wall times for the bundled Python evaluation workload.
    # The same fixtures are evaluated repeatedly; these are not production
    # latency benchmarks, host end-to-end metrics, or energy measurements.
    samples=[]
    for _ in range(11):
        start=time.perf_counter_ns()
        audit(r)
        samples.append((time.perf_counter_ns()-start)/1e6)
    samples=sorted(samples)
    def compact(x):
        def rate(v):
            return dict(numerator=v.numerator,denominator=v.denominator,
                estimate=v.estimate if v.defined else None,
                wilson_95=[v.wilson_95_low,v.wilson_95_high] if v.defined else None)
        return dict(cases=x.cases,decided=x.decided,abstained=x.abstained,
            reference_unknown=x.reference_unknown,
            false_positive=x.false_positive,false_negative=x.false_negative,
            selective_error=rate(x.selective_error),
            false_positive_rate=rate(x.false_positive_rate),
            false_negative_rate=rate(x.false_negative_rate),
            decision_coverage=rate(x.decision_coverage),
            interval_coverage=rate(x.claimed_interval_coverage),
            nominal_coverage_audit=x.nominal_coverage_audit)
    return dict(milestone='C15 T4 P3',source='synthetic_decimal_oracle_only',
        status='RESEARCH_ONLY_NOT_REAL_WORLD_VALIDATION',
        plan_sha256=r.prespecified_plan_sha256.hex(),
        study_sha256=result.request_sha256.hex(),
        calibrations=compact(result.calibration),holdout=compact(result.holdout),
        falsifications=[dict(id=x.case_id,decision=x.label_falsifies_decision,
            interval=x.claimed_interval_falsified) for x in result.audited_cases
            if x.partition==p3.T4P3_HOLDOUT and
                (x.label_falsifies_decision or x.claimed_interval_falsified)],
        warnings=list(result.warnings),
        physically_verified=result.physical_validity_verified,
        independent_evidence_authenticated=result.independent_evidence_authenticated,
        reference_runtime_only=dict(
            process='local_python_80_synthetic_cases',runs=len(samples),
            p50_millis=samples[len(samples)//2],
            p95_nearest_rank_millis=samples[math.ceil(.95*len(samples))-1],
            energy_measured=False,full_host_latency_measured=False),
        VM_dependent_tests='DEFERRED')


if __name__=='__main__':
    import sys
    target=Path(sys.argv[1]) if len(sys.argv)>1 else None
    payload=json.dumps(output(),indent=2,sort_keys=True)+'\n'
    if target:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(payload,encoding='utf8')
    else:
        print(payload)
