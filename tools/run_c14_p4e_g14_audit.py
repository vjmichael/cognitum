"""Independently audit G14 evidence claims; not proof of real worker provenance."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REPORT=Path('docs/components/causal/P4E-G14-genuine-worker-smoke-evidence.json')
EXPECTED={'econml':('0.17.0',100),'causal-learn':('0.1.4.8',250)}


def audit(data):
    if (data.get('milestone')!='C14 P4E G14' or
        data.get('real_scientific_subprocesses')!=2 or
        data.get('real_llm_invoked') is not False or
        data.get('actual_lu_host_authenticated') is not False or
        data.get('native_windows_confinement_verified') is not False or
        data.get('worker_os_attestation_flags_are_test_doubles') is not True or
        data.get('external_actions_authorized')!=0):
        raise ValueError('G14_OVERCLAIMED_OR_MISSING_RESEARCH_BOUNDARY')
    cases=data.get('cases')
    if not isinstance(cases,list) or len(cases)!=2 or set(x.get('backend') for x in cases)!=set(EXPECTED):
        raise ValueError('G14_WRONG_BACKEND_SET')
    for case in cases:
        v,n=EXPECTED[case['backend']]
        if (case.get('version')!=v or case.get('sample_count')!=n or
            case.get('g14_disposition')!='WORKER_ASSURANCE_RESEARCH_DIAGNOSTIC_ONLY' or
            case.get('intervention_request_denied') is not True or
            case.get('worker_shape_verified') is not True or
            case.get('worker_origin_authenticated') is not False or
            case.get('production_os_isolation_verified') is not False or
            not isinstance(case.get('trace_id'),str) or not case['trace_id']):
            raise ValueError('G14_INVALID_WORKER_REPORT')
        for k in ('worker_result_sha256','request_sha256','scientific_payload_sha256_without_timing'):
            raw=case.get(k)
            if not isinstance(raw,str) or len(raw)!=64 or any(ch not in '0123456789abcdef' for ch in raw):
                raise ValueError('G14_INVALID_DIGEST_SHAPE')
        if case['backend']=='econml':
            if len(case.get('effects',[]))!=2 or case.get('skeleton_edges'):raise ValueError('G14_ECONML_SHAPE')
        else:
            if case.get('effects') or case.get('skeleton_edges')!=[[0,1],[1,2]]:
                raise ValueError('G14_PC_SHAPE')
    return {'audited_cases':len(cases),'research_only':True,
            'no_cryptographic_provenance_verified':True}


def main():
    payload=REPORT.read_bytes()
    print('PASS G14 report audit:',audit(json.loads(payload)),
          'report_sha256',hashlib.sha256(payload).hexdigest())
if __name__=='__main__':main()
