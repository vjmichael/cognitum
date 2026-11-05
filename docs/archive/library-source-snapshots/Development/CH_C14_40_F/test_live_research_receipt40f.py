"""Live independent original math replay -> checker research receipt -> mocked OS-peer attestor guard.

No AF_UNIX UID boundary or real private signing key here. Tests the policy adapter,
not CH39 five-account service integration.
"""
from __future__ import annotations
import hashlib,json,pathlib,time
from research_receipt40f import checker_issue_after_live_replay,attestor_research_guard,verify_source_pins,Refusal
ROOT=pathlib.Path(__file__).resolve().parent
source=ROOT/'results'/'one_event_n80_i00_127_original_mpfr_trace.json'
archive=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
nonce='a'*64;policy='b'*64;t=time.perf_counter()
r=checker_issue_after_live_replay(source,archive,nonce,policy)
casehash,pin=verify_source_pins(archive,'one_event_n80_i00')
assert r['node_count']==127 and r['unsupported_caps']==0
args=dict(checker_uid=1004,nonce=nonce,policy_hash=policy,case=r['case_id'],pins={r['case_id']:pin},source_trace_sha=hashlib.sha256(source.read_bytes()).hexdigest(),expected_case_hash=casehash,expected_certificate_sha=r['certificate_sha256'])
used=set();res=attestor_research_guard(r,trusted_peer_uid=1004,used_nonces=used,**args)
assert res['accepted'] and not res['production_admission'] and not res['global_optimality_certified']
for badargs in [dict(trusted_peer_uid=1002),dict(trusted_peer_uid=1004)]:
 try:attestor_research_guard(r,used_nonces=used,**{**args,**badargs})
 except Refusal:pass
 else:raise AssertionError('Research-only replay or forged UID accepted')
result={'case':'one_event_n80_i00','actual_original_127_node_math_checker_reexecuted':True,'research_guard_pass':True,'wrong_peer_uid_refused':True,'repeated_nonce_refused':True,'scientific_release':'NO_GO','live_separate_linux_uid_socket_tested':False,'seconds':round(time.perf_counter()-t,3)}
(ROOT/'CH40F_RESEARCH_RECEIPT_SCOPE_TEST.json').write_text(json.dumps(result,indent=2)+'\n')
print('CH40-F actual full 127-node independent math check + research-only attestor guard PASS',result,flush=True)