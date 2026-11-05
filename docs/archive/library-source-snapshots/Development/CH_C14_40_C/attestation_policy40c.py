"""CH40-C fail-closed mock CH39 attestor admission protocol.

This is *not* wired to the five-UID Linux services. It demonstrates the
cryptographic and semantic acceptance conditions for a future CH39 adapter.
A full mathematical checker must generate and sign each receipt under a trusted
operator-pinned public key; untrusted clients may never supply that key.
"""
from __future__ import annotations
import base64,hashlib,secrets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
from independent_checker40 import canonical, digest
from rule_checker40c import audit_claim

DOMAIN=b'COGNITUM/CH40C/RESEARCH-ONLY/RECEIPT/V1\x00'
RESEARCH_SCOPE='INDEPENDENT_FINITE_BOX_CONSISTENCY_ONLY'

def signed_receipt(checker_private_key, certificate, source_sha256, nonce):
    """Called only after independent computation; private key remains caller-owned."""
    from rule_checker40c import verify_tree
    proof=verify_tree(certificate)
    if proof['independent_finite_gap_proven']:
        # We do not promote potentially resolved bounded-gap claims in this protocol.
        raise ValueError('New mathematical gap claim requires separate release review')
    envelope={'version':'CH40C-RESEARCH-V1','case':certificate['research_case_id'],
        'source_archive_sha256':source_sha256,'certificate_sha256':proof['certificate_sha256'],
        'checker_result_sha256':hashlib.sha256(canonical(proof)).hexdigest(),
        'nonce':nonce,'scope':RESEARCH_SCOPE,'scientific_release':'NO_GO',
        'producer_optimized_rules_fully_certified':False,'nodes_replayed':127}
    body=canonical(envelope)
    sig=checker_private_key.sign(DOMAIN+body)
    return {'body':envelope,'signature_b64':base64.b64encode(sig).decode('ascii')},proof

class ResearchAttestorGate:
    def __init__(self,*,pinned_checker_public_key,source_archive_sha256,case_certificate_sha256):
        self._public=pinned_checker_public_key
        self._source=source_archive_sha256
        self._pins=dict(case_certificate_sha256)
        self._outstanding={}
        self._consumed=set()
    def challenge(self,case):
        if case not in self._pins:raise ValueError('Case not pinned to sealed source')
        nonce=secrets.token_hex(24)
        self._outstanding[nonce]=case
        return nonce
    def accept(self,ticket,proof,certificate,*,claim_scope=RESEARCH_SCOPE):
        b=ticket.get('body')
        if not isinstance(b,dict):raise ValueError('Ticket without body')
        nonce=b.get('nonce')
        if nonce not in self._outstanding or nonce in self._consumed:raise ValueError('Invalid or consumed challenge')
        expected_case=self._outstanding.pop(nonce)
        self._consumed.add(nonce)  # consume once even on failure (fail closed)
        if claim_scope!=RESEARCH_SCOPE:raise ValueError('Producer/global proof promotion refused')
        if b.get('version')!='CH40C-RESEARCH-V1' or b.get('scope')!=RESEARCH_SCOPE or b.get('scientific_release')!='NO_GO':
            raise ValueError('Wrong signature domain, release, or policy')
        if b.get('case')!=expected_case or b.get('case')!=certificate.get('research_case_id') or digest(certificate)!=self._pins[expected_case]:
            raise ValueError('Case ID mismatch')
        if b.get('source_archive_sha256')!=self._source or b.get('certificate_sha256')!=proof.get('certificate_sha256'):
            raise ValueError('Pinned source identity mismatch')
        if b.get('checker_result_sha256')!=hashlib.sha256(canonical(proof)).hexdigest():
            raise ValueError('Altered checker mathematical result')
        if b.get('nodes_replayed')!=127 or b.get('producer_optimized_rules_fully_certified') is not False:
            raise ValueError('Unverified producer numerical proof')
        try:
            signature=base64.b64decode(ticket['signature_b64'],validate=True)
            self._public.verify(signature,DOMAIN+canonical(b))
        except (InvalidSignature,ValueError,KeyError) as exc:
            raise ValueError('Checker authentication failed') from exc
        # The attestor MUST NOT rerun the mathematical checker or read sealed
        # checker source. A separate checker identity signs the entire receipt;
        # attestor pins both key and original certificate digest and checks the
        # scope. Actual checker computation is outside this service.
        if proof.get('protocol')!='CH40C-DECIMAL-INHERITED-RULE-REPLAY-V1' or proof.get('case')!=expected_case:
            raise ValueError('Unrecognized mathematical checker result')
        if proof.get('certificate_sha256')!=self._pins[expected_case] or proof.get('nodes_replayed')!=127 or len(proof.get('nodes',[]))!=127:
            raise ValueError('Incomplete independently signed proof')
        if proof.get('independent_finite_gap_proven') or proof.get('scientific_release')!='NO_GO':
            raise ValueError('Science status requires further review')
        return {'case':expected_case,'status':'CH40C_RESEARCH_SCOPE_ACCEPTED',
                'certificate_sha256':b['certificate_sha256'],
                'checker_result_sha256':b['checker_result_sha256'],
                'scientific_release':'NO_GO','may_publish_CH39_production_witness':False}