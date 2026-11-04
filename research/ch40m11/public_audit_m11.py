"""Independent read-only M11 PUBLIC chain auditor.

Checks checkpoint+anchor signatures, canonical encodings, sequence and original
source/journal hash *commitments*. It cannot independently reproduce the 296
mathematical checks without the separately pinned 800MB originals and M8 code.
External expected key fingerprints and current tip are needed to establish
trust and detect rollback of an otherwise valid historical signed snapshot.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,pathlib,sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
PROTO='CH40M11-PUBLIC-DUAL-CHAIN-AUDIT-V1'
class Refusal(ValueError):pass

def canon(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def sha(b):return hashlib.sha256(b).hexdigest()
def b64(b):return base64.b64encode(b).decode('ascii')
def un64(s):return base64.b64decode(s,validate=True)

def verify(doc,*,expected_anchor_tip=None,expected_anchor_key_sha=None,expected_verifier_key_sha=None):
    if doc.get('protocol')!='CH40M11-PUBLIC-EVIDENCE-V1' or doc.get('scientific_release')!='NO_GO':raise Refusal('research protocol mismatch')
    vp=un64(doc['verifier_public_b64']);ap=un64(doc['anchor_public_b64'])
    if len(vp)!=32 or len(ap)!=32:raise Refusal('bad public key length')
    if expected_verifier_key_sha and sha(vp)!=expected_verifier_key_sha:raise Refusal('external verifier identity mismatch')
    if expected_anchor_key_sha and sha(ap)!=expected_anchor_key_sha:raise Refusal('external anchor identity mismatch')
    v=Ed25519PublicKey.from_public_bytes(vp);a=Ed25519PublicKey.from_public_bytes(ap)
    man=doc['m10_manifest']
    if man.get('trusted_verifier_public_sha256')!=sha(vp) or man.get('scientific_release')!='NO_GO':
        raise Refusal('manifest incompatible with keys')
    genesis=sha(b'CH40M10-GENESIS\0'+canon(man))
    prev=genesis;tips=[];counts=0
    checkpoints=doc['checkpoint_rows']
    if not isinstance(checkpoints,list) or not 1<=len(checkpoints)<=15:raise Refusal('bad checkpoint count')
    for idx,row in enumerate(checkpoints):
        bodyraw=un64(row['body_b64']);sig=un64(row['signature_b64'])
        if sha(bodyraw)!=row['body_sha']:raise Refusal('changed checkpoint hash')
        try:v.verify(sig,b'CH40M10-VERIFIER\0'+bodyraw)
        except InvalidSignature as exc:raise Refusal('invalid verifier signature') from exc
        body=json.loads(bodyraw)
        if canon(body)!=bodyraw:raise Refusal('noncanonical signed checkpoint')
        if (body.get('sequence')!=idx+1 or body.get('case')!=man['case_order'][idx] or
            body.get('prev_tip')!=prev or body.get('scientific_release')!='NO_GO'):
            raise Refusal('checkpoint chain or original case order mismatch')
        r=body.get('audited_receipt',{})
        if r.get('status')!='PASS_RESEARCH_ONLY' or r.get('scientific_release')!='NO_GO':raise Refusal('unaccepted inner math receipt')
        receipts=r.get('receipts',[])
        if len(receipts)!=2 or {k.get('backend') for k in receipts}!={'arb_gram','mpfr_gram'}:
            raise Refusal('missing original paired source journals')
        if not all(k.get('original_trace_sha256')==body.get('original_trace_sha256') and k.get('case')==body['case'] and k.get('journal_sha256')==body['journal_sha256'][k['backend']] for k in receipts):
            raise Refusal('source provenance identity mismatch')
        checks=sum(k['children_checked'] for k in receipts)
        if r.get('children_checked')!=checks:raise Refusal('child coverage mismatch')
        counts+=checks
        tip=sha(canon({'previous':prev,'body_sha256':row['body_sha'],'signature':row['signature_b64']}))
        if tip!=row['tip']:raise Refusal('invalid checkpoint tip')
        tips.append(tip);prev=tip
    anchor=doc['anchor']
    if anchor.get('protocol')!='CH40M11-OS-SEPARATED-ANCHOR-V1' or anchor.get('genesis')!=genesis or anchor.get('count')!=len(checkpoints):raise Refusal('anchor genesis or sequence mismatch')
    if anchor.get('verifier_pub_sha256')!=sha(vp) or anchor.get('anchor_pub_sha256')!=sha(ap):raise Refusal('anchor key identity mismatch')
    if not isinstance(anchor.get('entries'),list) or len(anchor['entries'])!=len(checkpoints):raise Refusal('anchor case count mismatch')
    prev_a=sha(b'CH40M11-ANCHOR-GENESIS\0'+canon({'genesis':genesis,'verifier_pub_sha256':sha(vp),'anchor_pub_sha256':sha(ap)}))
    prev_c=genesis
    for idx,item in enumerate(anchor['entries']):
        e=item['event'];sig=un64(item['signature'])
        if (e.get('sequence')!=idx+1 or e.get('prev_anchor_tip')!=prev_a or e.get('prev_checkpoint_tip')!=prev_c or
            e.get('checkpoint_tip')!=tips[idx] or e.get('case')!=man['case_order'][idx] or
            e.get('verifier_body_sha256')!=checkpoints[idx]['body_sha']):raise Refusal('anchor event mismatches signed verifier history')
        try:a.verify(sig,b'CH40M11-ANCHOR-EVENT\0'+canon(e))
        except InvalidSignature as exc:raise Refusal('invalid anchor signature') from exc
        atip=sha(canon({'event':e,'signature':item['signature']}))
        if atip!=item['anchor_tip']:raise Refusal('bad anchor event tip')
        prev_a=atip;prev_c=tips[idx]
    if prev_a!=anchor['anchor_tip'] or prev_c!=anchor['checkpoint_tip']:
        raise Refusal('anchor head inconsistent')
    if expected_anchor_tip and prev_a!=expected_anchor_tip:raise Refusal('ANCHOR_ROLLBACK against externally pinned tip')
    return {'protocol':PROTO,'status':'CRYPTOGRAPHIC_CHAIN_ONLY','scientific_release':'NO_GO',
        'cases':len(checkpoints),'signed_child_coverage':counts,'anchor_tip':prev_a,
        'verifier_public_sha256':sha(vp),'anchor_public_sha256':sha(ap),
        'math_independently_recomputed_in_this_public_audit':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=pathlib.Path)
    p.add_argument('--expected-anchor-tip');p.add_argument('--expected-anchor-key-sha');p.add_argument('--expected-verifier-key-sha')
    a=p.parse_args()
    try:print('M11_PUBLIC_AUDIT '+json.dumps(verify(json.loads(a.evidence.read_text()),expected_anchor_tip=a.expected_anchor_tip,expected_anchor_key_sha=a.expected_anchor_key_sha,expected_verifier_key_sha=a.expected_verifier_key_sha),sort_keys=True))
    except (Refusal,OSError,KeyError,ValueError,InvalidSignature) as e:
        print('M11_PUBLIC_REFUSED '+repr(e),file=sys.stderr);sys.exit(2)
if __name__=='__main__':main()
