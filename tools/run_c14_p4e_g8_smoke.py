"""Offline G8 acceptance smoke: no third-party runtime besides NumPy/SciPy."""
import copy
import json
from pathlib import Path
from tools import run_c14_p4e_g7_study as g7
from tools import run_c14_p4e_g8_uncertainty as g8
from tools import run_c14_p4e_g8_crosslibrary_intervals as cross
from cognitum import causal_uncertainty as wire
from cognitum.proto import causal_uncertainty_pb2 as pb

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'docs/components/causal/P4E-G8-calibration-evidence.json').read_text())
assert report['numerical_replay_verified'] and g8.verify_report(report)
print('PASS 2000_fixture_math_replay')
assert report['summary']['300']['observed_heterogeneous']['empirical_point_interval_coverage_on_eligible_cases']<.95
print('PASS empirical_undercoverage_detected')
assert report['summary']['300']['hidden_confounder']['calibration_eligible_cases']==0
assert report['summary']['900']['no_overlap']['calibration_eligible_cases']==0
print('PASS invalid_assumptions_not_calibrated')


def to_req(scenario):
    x,meta=g7.make_fixture(scenario,101,300)
    q=pb.CausalUncertaintyRequest(schema_version=1,fixture_id=scenario,trace_id='smoke',confidence=.95,minimum_cell_count=5,
         known_hidden_confounder=(scenario=='hidden_confounder'))
    for z,t,y in x:q.observations.add(covariate=bool(z),treatment=bool(t),outcome=bool(y))
    return q

q=to_req('observed_homogeneous');res,rec=wire.calculate(q)
assert wire.verify(q,res,rec) and res.point_interval.point_interval_available
print('PASS typed_protobuf_result_receipt')
q=to_req('hidden_confounder');res,rec=wire.calculate(q)
assert wire.verify(q,res,rec) and not res.point_interval.point_interval_available
print('PASS hidden_confounder_bounds_only')
q=to_req('no_overlap');res,rec=wire.calculate(q)
assert wire.verify(q,res,rec) and not res.point_interval.point_interval_available
print('PASS no_overlap_bounds_only')
report2=json.loads((ROOT/'docs/components/causal/P4E-G8-genuine-crosslibrary-intervals.json').read_text())
assert cross.verify_report(report2)
print('PASS genuine_library_interval_report_structure')
print('ALL 7 G8 OFFLINE CHECKS PASSED')
