"""C14 P4C actual timestamp / residual-diagnostic smoke (no causal proof)."""
from tests.test_c14_p4c_temporal_diagnostics import case
from cognitum.proto import causal_temporal_diagnostics_pb2 as d
from cognitum.causal_temporal_diagnostics import (
    run_temporal_diagnostics_frame,temporal_diagnostics_receipt,
    make_screen_from_regular_timestamps)


def frame(req):return req.SerializeToString(deterministic=True)


def main():
    count=0
    req=case();raw=frame(req)
    reply=run_temporal_diagnostics_frame(raw,host_authorized=True,enabled=True)
    out=d.TemporalDiagnosticResult.FromString(reply)
    assert out.status==d.TEMP_DIAG_COMPUTED and out.cadence==d.TEMP_CADENCE_REGULAR
    assert out.eligible_for_fixed_lag_screen and temporal_diagnostics_receipt(raw,reply).numerical_replay_checked
    assert make_screen_from_regular_timestamps(raw,reply)
    print('PASS: actual regular cadence, cross-phase P4A candidate, replay');count+=1
    req=case();del req.observations[77];raw=frame(req)
    out=d.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(raw,host_authorized=True,enabled=True))
    assert out.cadence==d.TEMP_CADENCE_GAPPED and out.missing_grid_slots==1 and not out.eligible_for_fixed_lag_screen
    print('PASS: missing timestamp detected; no imputation');count+=1
    req=case();req.observations[72].timestamp_ms+=1;raw=frame(req)
    out=d.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(raw,host_authorized=True,enabled=True))
    assert out.cadence==d.TEMP_CADENCE_IRREGULAR and len(out.residual_tests)==0
    print('PASS: jitter blocked from fixed-lag regression');count+=1
    out=d.TemporalDiagnosticResult.FromString(run_temporal_diagnostics_frame(frame(case())))
    assert out.status==d.TEMP_DIAG_REJECTED
    print('PASS: default-denied host gate');count+=1
    raw=frame(case());reply=run_temporal_diagnostics_frame(raw,host_authorized=True,enabled=True)
    forged=d.TemporalDiagnosticResult.FromString(reply);forged.causal_directions_verified=True
    assert not temporal_diagnostics_receipt(raw,frame(forged)).numerical_replay_checked
    print('PASS: forged causal claim fails replay');count+=1
    print(f'C14 P4C: {count}/{count} smoke; authentic Lu and Windows gates pending')

if __name__=='__main__':main()
