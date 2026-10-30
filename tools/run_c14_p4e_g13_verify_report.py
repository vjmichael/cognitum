"""G13 independent report-shape/authority checker and optional functional replay.

Does not import Cognitum's assurance code for the structural/authority audit.
Functional replay uses the original generator separately and is NOT a signed
third-party verification or an authenticated OS/host security check.
"""
import hashlib
import json
from pathlib import Path
OUT = Path(__file__).resolve().parents[1] / 'docs/components/causal/P4E-G13-adversarial-caller-evidence.json'
SCENARIOS = ('CLEAN_INTERACTION','HIDDEN_COMMON_CAUSE','MISMEASURED_CONFOUNDER',
             'SELECTION_COLLIDER','TRANSPORT_SHIFT','NEGATIVE_CONTROL')
INTENTS = ('SYNTHETIC_DIAGNOSTIC','UNSUPPORTED_CAUSAL_CLAIM',
           'INTERVENTION_RECOMMENDATION','EXTERNAL_TOOL_ACTION')


def audit(obj):
    if (type(obj) is not dict or obj.get('phase')!='C14 P4E G13'
        or obj.get('status')!='OFFLINE_REFERENCE_ONLY_NOT_LLM_BENCHMARK_OR_LU_ADMISSION'
        or obj.get('case_count')!=32 or type(obj.get('results')) is not list
        or len(obj['results'])!=32 or obj.get('design',{}).get('synthetic_mechanisms')!=list(SCENARIOS)
        or obj['design'].get('intents_per_mechanism')!=len(INTENTS)
        or obj['design'].get('caller_text_untrusted') is not True):
        raise ValueError('G13_INVALID_DESIGN_OR_COUNT')
    claims=obj.get('claims',{})
    if set(claims)!={'real_llm_invoked','production_worker_runtime_exercised',
        'lu_host_authenticated','windows_security_attested',
        'causal_identification_proven','external_actions_authorized'} or any(claims.values()):
        raise ValueError('G13_UNAUTHORIZED_RESEARCH_CLAIM')
    cases=set()
    for row in obj['results']:
        name=row.get('case')
        if not isinstance(name,str) or name in cases:
            raise ValueError('G13_DUPLICATE_CASE')
        cases.add(name)
        for flag in ('real_world_causal_claim_allowed','intervention_allowed',
                     'external_action_allowed','lu_host_authenticated'):
            if row.get(flag) is not False:
                raise ValueError('G13_FORGED_AUTHORITY_FLAG')
        if name=='CROSS_CONVERSATION_REPLAY_DENIED':
            if row.get('replay_accepted') is not False: raise ValueError('G13_REPLAY_ACCEPTED')
            continue
        for digest_field in ('request_sha256','decision_sha256','receipt_sha256'):
            h=row.get(digest_field)
            if not isinstance(h,str) or len(h)!=64:
                raise ValueError('G13_MISSING_DIGEST')
            try: bytes.fromhex(h)
            except ValueError: raise ValueError('G13_INVALID_DIGEST') from None
        if not isinstance(row.get('reason_codes'),list):
            raise ValueError('G13_MISSING_REASON_CODES')
        for name_flag in ('g10_g11_g12_replayed','independent_synthetic_arithmetic_replayed'):
            # These must be explicitly booleans, even in expected rejected cases.
            if type(row.get(name_flag)) is not bool:
                raise ValueError('G13_NONBOOL_EVIDENCE_FLAG')
    expected={f'{scenario}:{intent}' for scenario in SCENARIOS for intent in INTENTS}
    expected|={'MODEL_ASSERTS_CAUSAL_PROOF','MODEL_ASSERTS_LU_HOST_AUTHORITY',
        'UPSTREAM_ABSTENTION','UNKNOWN_STUDY_REJECT','FORGED_RECEIPT_REJECT',
        'CROSS_SCENARIO_REPLAY_REJECT','NARRATIVE_INJECTION_NOT_ECHOED',
        'CROSS_CONVERSATION_REPLAY_DENIED'}
    if cases!=expected:
        raise ValueError('G13_INCOMPLETE_MATRIX')
    by_name={v['case']:v for v in obj['results']}
    for scenario in SCENARIOS:
        for intent in INTENTS:
            name=f'{scenario}:{intent}'
            want=('INTEGRATION_DESCRIBE_SYNTHETIC_DIAGNOSTIC_ONLY'
                  if intent=='SYNTHETIC_DIAGNOSTIC' else 'INTEGRATION_ABSTAIN_CAUSAL_OVERREACH')
            if by_name[name].get('disposition') != want:
                raise ValueError('G13_MATRIX_DISPOSITION_MISMATCH')
    extra={'MODEL_ASSERTS_CAUSAL_PROOF':'INTEGRATION_ABSTAIN_UNTRUSTED_ASSERTION',
        'MODEL_ASSERTS_LU_HOST_AUTHORITY':'INTEGRATION_ABSTAIN_UNTRUSTED_ASSERTION',
        'UPSTREAM_ABSTENTION':'INTEGRATION_ABSTAIN_UPSTREAM',
        'UNKNOWN_STUDY_REJECT':'INTEGRATION_REJECT_UNVERIFIED',
        'FORGED_RECEIPT_REJECT':'INTEGRATION_REJECT_UNVERIFIED',
        'CROSS_SCENARIO_REPLAY_REJECT':'INTEGRATION_REJECT_UNVERIFIED',
        'NARRATIVE_INJECTION_NOT_ECHOED':'INTEGRATION_DESCRIBE_SYNTHETIC_DIAGNOSTIC_ONLY'}
    for case,disposition in extra.items():
        if by_name[case].get('disposition')!=disposition:
            raise ValueError('G13_EXTRA_DISPOSITION_MISMATCH')
    return {'cases_checked':32,'authority_grants':0,'synthetic_diagnostics_only':True,
            'external_host_authentication_verified':False}


def main():
    current=json.loads(OUT.read_text())
    status=audit(current)
    from tools.run_c14_p4e_g13_acceptance import conduct
    regenerated=conduct()
    if regenerated!=current: raise ValueError('G13_DETERMINISTIC_REPLAY_MISMATCH')
    print('PASS: 32 structurally audited cases and full deterministic functional replay; '+
          '0 authority grants; '+hashlib.sha256(OUT.read_bytes()).hexdigest())
    return status

if __name__=='__main__':main()
