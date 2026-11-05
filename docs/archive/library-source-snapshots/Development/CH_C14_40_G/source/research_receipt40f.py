"""Strict research-only CH40-F checker->attestor admission *prototype*.

No credential or signature is created by the mathematical checker. The upstream
Linux AF_UNIX SO_PEERCRED authenticated service boundary must supply peer_uid.
This is NOT yet wired into the CH39 live five-UID services.
"""
from __future__ import annotations
import hashlib,json,pathlib,re,zipfile
from typing import MutableSet

PROTOCOL='CH40F-CHECKER-FINITE-ROOT-CAPS-V1'
SCOPE='ORIGINAL_MPFR_DIRECT_COUPLED_AND_INHERITED_LOCAL_CAPS_RESEARCH_ONLY'
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
HEX=re.compile(r'^[a-f0-9]{64}$')
FIELDS={'protocol','case_id','nonce','policy_sha256','original_archive_sha256',
        'original_case_sha256','original_head_sha256','checkpoint_sha256',
        'certificate_sha256','producer_trace_sha256','node_count',
        'direct_caps_certified','coupled_caps_certified','inherited_caps_certified',
        'unsupported_caps','scope','checker_result','scientific_release',
        'global_optimality_certified','attestation_policy'}

class Refusal(ValueError):pass

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def verify_source_pins(archive:pathlib.Path,case:str):
    if sha(archive.read_bytes())!=PIN:raise Refusal('Pinned archive does not match')
    with zipfile.ZipFile(archive) as z:
        proto=json.loads(z.read('CH_C14_29/frozen_protocol.json'))
        pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
    if case not in proto['original_case_sha256'] or case not in pins:raise Refusal('Unknown original case')
    return proto['original_case_sha256'][case], pins[case]

def checker_issue_after_live_replay(trace_file,archive,nonce,policy_hash):
    """Mathematics is *executed* here; cannot issue from saved success JSON."""
    from verify_trace40e import verify
    trace_file=pathlib.Path(trace_file);archive=pathlib.Path(archive)
    if type(nonce)!=str or not HEX.fullmatch(nonce) or type(policy_hash)!=str or not HEX.fullmatch(policy_hash):raise Refusal('Invalid challenge/policy')
    contents=trace_file.read_bytes();trace=json.loads(contents)
    case=trace['case'];case_hash,pin=verify_source_pins(archive,case)
    if trace['original_case_sha256']!=case_hash:raise Refusal('Source case differs')
    audit=verify(trace,archive)
    checks=audit['checks']
    if (checks['nodes']!=127 or checks['direct_certified']+checks['coupled_certified']!=127 or
        checks['inherited_caps_certified']!=127 or checks['untrusted_caps']!=0 or
        not audit['all_recorded_selected_caps_certified'] or audit['scientific_release']!='NO_GO'):
        raise Refusal('Independent verification did not establish complete finite local caps')
    return {'protocol':PROTOCOL,'case_id':case,'nonce':nonce,'policy_sha256':policy_hash,
            'original_archive_sha256':PIN,'original_case_sha256':case_hash,
            'original_head_sha256':pin['original_head_sha256'],'checkpoint_sha256':pin['checkpoint_sha256'],
            'certificate_sha256':trace['certificate_sha256'],'producer_trace_sha256':sha(contents),
            'node_count':127,'direct_caps_certified':checks['direct_certified'],
            'coupled_caps_certified':checks['coupled_certified'],'inherited_caps_certified':127,
            'unsupported_caps':0,'scope':SCOPE,'checker_result':'INDEPENDENT_MATH_CERTIFIED_FINITE_CAPS',
            'scientific_release':'NO_GO','global_optimality_certified':False,
            'attestation_policy':'RESEARCH_ONLY_NEVER_PRODUCTION_OR_SCIENTIFIC_GO'}

def attestor_research_guard(receipt,*,trusted_peer_uid,checker_uid,nonce,policy_hash,case,pins,source_trace_sha,expected_case_hash,expected_certificate_sha,used_nonces:MutableSet[str]):
    """Only validates a receipt that came from an OS-authenticated checker socket.

    The UID must be from SO_PEERCRED in the host transport implementation,
    never user-supplied JSON. Does not sign; caller must use distinct research domain.
    """
    if type(checker_uid)!=int or type(trusted_peer_uid)!=int or checker_uid!=trusted_peer_uid:raise Refusal('Checker UID mismatch')
    if type(receipt)!=dict or set(receipt)!=FIELDS:raise Refusal('Wrong receipt schema')
    if (receipt['protocol']!=PROTOCOL or receipt['scope']!=SCOPE or
        receipt['checker_result']!='INDEPENDENT_MATH_CERTIFIED_FINITE_CAPS' or
        receipt['attestation_policy']!='RESEARCH_ONLY_NEVER_PRODUCTION_OR_SCIENTIFIC_GO' or
        receipt['scientific_release']!='NO_GO' or receipt['global_optimality_certified'] is not False):
        raise Refusal('Forbidden scope escalation')
    if (receipt['case_id']!=case or receipt['nonce']!=nonce or receipt['policy_sha256']!=policy_hash or
        receipt['producer_trace_sha256']!=source_trace_sha):raise Refusal('Challenge/source/policy binding mismatch')
    if any(type(x)!=str or not HEX.fullmatch(x) for x in [receipt['nonce'],receipt['policy_sha256'],receipt['original_archive_sha256'],receipt['original_case_sha256'],receipt['producer_trace_sha256'],receipt['certificate_sha256'],receipt['original_head_sha256'],receipt['checkpoint_sha256']]):raise Refusal('Malformed hash')
    if receipt['original_archive_sha256']!=PIN:raise Refusal('Wrong source ZIP')
    if receipt['original_case_sha256']!=expected_case_hash or receipt['certificate_sha256']!=expected_certificate_sha:
        raise Refusal('Case/certificate source identity differs from protected policy')
    if (type(receipt['node_count'])!=int or receipt['node_count']!=127 or
        type(receipt['direct_caps_certified'])!=int or type(receipt['coupled_caps_certified'])!=int or
        type(receipt['inherited_caps_certified'])!=int or type(receipt['unsupported_caps'])!=int or
        receipt['direct_caps_certified']+receipt['coupled_caps_certified']!=127 or
        receipt['inherited_caps_certified']!=127 or receipt['unsupported_caps']!=0):raise Refusal('Incomplete mathematical cap certification')
    if (case not in pins or receipt['original_head_sha256']!=pins[case]['original_head_sha256'] or receipt['checkpoint_sha256']!=pins[case]['checkpoint_sha256']):raise Refusal('Original CH39 pin mismatch')
    if nonce in used_nonces:raise Refusal('Replayed checker challenge')
    used_nonces.add(nonce)
    return {'accepted':True,'scope':SCOPE,'case_id':case,'scientific_release':'NO_GO',
            'production_admission':False,'global_optimality_certified':False}