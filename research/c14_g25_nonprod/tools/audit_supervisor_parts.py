#!/usr/bin/env python3
"""Independent immutable-record accounting for four bounded supervisor runs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'results'
results=[];accepted=set();term=set();refusals=set();maxdelta=0.;ids=[]
for part in range(4):
    summary=json.loads((D/f'Standalone_Supervisor_Acceptance_part{part}.json').read_text())
    q=(D/f'Supervisor_Blackbox_Requests_part{part}.jsonl').read_bytes()
    r=(D/f'Supervisor_Blackbox_Responses_part{part}.jsonl').read_bytes()
    assert hashlib.sha256(q).hexdigest()==summary[f'Supervisor_Blackbox_Requests_part{part}.jsonl_sha256']
    assert hashlib.sha256(r).hexdigest()==summary[f'Supervisor_Blackbox_Responses_part{part}.jsonl_sha256']
    controls=[json.loads(s) for s in q.decode().splitlines()]
    events=[json.loads(s) for s in r.decode().splitlines()]
    assert len(controls)==11 and len(events)==21
    for i in range(10):
        ctrl=controls[i]
        a,b=events[2*i:2*i+2]
        assert a['event']=='accepted' and b['event']=='result'
        assert a['request_id']==b['request_id']==ctrl['request_id']==ctrl['request']['request_id']
        assert ctrl['request_id'] not in accepted
        accepted.add(ctrl['request_id'])
        assert b['automatic_causal_certification'] is False and b['production_estimator_promotion'] is False
        outcome=b['response']
        assert outcome['automatic_causal_certification'] is False and outcome['production_estimator_promotion'] is False
        term.add(outcome['host_status'])
        if outcome['host_status']=='refused':
            refusals.add(ctrl['request_id'])
            assert outcome['result']['identified_set_plugin'] is None
            assert outcome['result']['identified_set_outer95_conditional'] is None
        else:
            assert outcome['host_status']=='completed'
            assert outcome['result']['identified_set_outer95_conditional'] is not None
    assert controls[-1]==controls[0]
    assert events[-1]['event']=='rejected' and events[-1]['code']=='duplicate_task_id'
    results.append(summary)
    ids.append(summary['source_sha256'])
    maxdelta=max(maxdelta,summary['max_abs_numeric_difference'])
assert len(set(ids))==1
assert len(accepted)==40 and len(refusals)==8 and term=={'completed','refused'}
assert sum(r['accepted_numerical'] for r in results)==32
assert sum(r['scientifically_refused'] for r in results)==8
assert maxdelta < 1e-12
aggregate={
  'milestone':'C14_G25_STANDALONE_SUPERVISOR',
  'date':'2026-11-01',
  'source_sha256':ids[0],
  'total_research_requests':40,
  'accepted_supervisor_requests':40,
  'conditional_reports':32,
  'scientific_refusals':8,
  'duplicate_task_rejections':4,
  'independent_numerical_matches':32,
  'max_abs_numerical_delta':maxdelta,
  'all_receipts_verified':True,
  'research_only':True,
  'automatic_causal_certifications':0,
  'production_promotion':False,
  'cognitum_production_modified':False,
  'lu_modified':False,
  'four_part_e2e_total_seconds':round(sum(r['duration_seconds'] for r in results),3),
  'protocol_version':2,
  'linux_inflight_cancel_and_descendant_cleanup':'PASS_UNIT_HOSTILE_FIXTURE',
  'windows_descendant_cleanup':'OPEN_NOT_TESTED',
  'soft_cooperative_cancel':'OPEN_NOT_IMPLEMENTED',
  'host_runtime_sandbox':'NOT_CLAIMED',
  'scientific_calibration':'FAILED_PREVIOUSLY_UNCHANGED',
  'input_sources':'40 synthetic count tables, including 32 adequate-support and 8 refusal cases',
  'operational_deviation':'First unchunked E2E invocation exceeded local execution limit before any result summaries were written; reran four deterministic 10-case chunks. A later hardening edit to supervisor result validation/pipe cleanup was made; all four chunks rerun against exact final source hash.'
}
(D/'Supervisor_Aggregated_Gate_Audit.json').write_text(json.dumps(aggregate,sort_keys=True,indent=2)+'\n')
print(json.dumps(aggregate,sort_keys=True,indent=2))
