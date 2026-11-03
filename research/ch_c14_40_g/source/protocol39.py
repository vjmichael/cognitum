"""CH39: minimal strict, bounded, signed cross-UID protocol. Research Linux only."""
from __future__ import annotations
import base64, hashlib, json, os, re, socket, stat, struct, uuid
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ZERO='0'*64
HEX64=re.compile(r'[a-f0-9]{64}\Z')
ATTEST_FIELDS={'case_id','binding_sha256','original_head_sha256','checkpoint_sha256',
               'archive_sha256','nodes','archive_epochs','mpfr_replayed_frames',
               'proof_replayed','scientific_release','verified_source'}
V_DOMAIN=b'Cognitum/CH40G/RESEARCH/attestor-dual-math-caps/v1\x00'
S_DOMAIN=b'Cognitum/CH40G/RESEARCH/signer-chained-witness/v1\x00'


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def sha(data):return hashlib.sha256(data).hexdigest()
def objhash(v):return sha(canonical(v))
def unique(items):
    result={}
    for k,v in items:
        if k in result:raise ValueError('Duplicate key in strict JSON')
        result[k]=v
    return result

def parse(raw,limit=16384):
    if type(raw)!=bytes or len(raw)>limit or not raw.endswith(b'\n'):
        raise ValueError('Missing newline or message too large')
    v=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if canonical(v)+b'\n'!=raw:raise ValueError('Noncanonical message')
    return v

def safe_read(path,limit=65536):
    fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>limit:raise ValueError('Unsafe source file')
        output=b''
        while len(output)<=limit:
            p=os.read(fd,min(65536,limit+1-len(output)))
            if not p:break
            output+=p
        if len(output)>limit:raise ValueError('Excessive bytes')
        return output
    finally:os.close(fd)

def sync_dir(path):
    fd=os.open(str(path),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def atomic(root,name,payload):
    root=Path(root);tmp=root/f'.dual37-{uuid.uuid4().hex}.pending'
    fd=os.open(tmp,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    os.replace(tmp,root/name);sync_dir(root)

def peersock(conn):return struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i')))
def receive_line(sock,cap=16384):
    buf=b''
    while b'\n' not in buf:
        chunk=sock.recv(min(8192,cap+1-len(buf)))
        if not chunk:raise ValueError('Socket closed mid-record')
        buf+=chunk
        if len(buf)>cap:raise ValueError('Oversized socket message')
    if len(buf)!=buf.index(b'\n')+1:raise ValueError('Trailing socket bytes')
    return parse(buf,cap)

def request(sockpath,body,timeout=900):
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(timeout)
    try:
        sock.connect(str(sockpath));sock.sendall(canonical(body)+b'\n');return receive_line(sock,32768)
    finally:sock.close()

def verify_signature(doc,pem,domain):
    if type(doc)!=dict or set(doc)!={'body','signature'} or type(doc['body'])!=dict:
        raise ValueError('Invalid signed document shape')
    key=serialization.load_pem_public_key(pem)
    if not isinstance(key,Ed25519PublicKey):raise ValueError('Non-Ed25519 key')
    try:key.verify(base64.b64decode(doc['signature'],validate=True),domain+canonical(doc['body']))
    except Exception as exc:raise ValueError('Invalid signature') from exc
    return doc['body']

def verify_attestation(att,case,pin):
    if type(att)!=dict or set(att)!=ATTEST_FIELDS or type(att['case_id'])!=str or att['case_id']!=case:
        raise ValueError('Attestation identity or schema mismatch')
    if att['original_head_sha256']!=pin['original_head_sha256'] or att['checkpoint_sha256']!=pin['checkpoint_sha256']:
        raise ValueError('Attestation does not match frozen original pins')
    if (type(att['nodes'])!=int or att['nodes']!=127 or type(att['archive_epochs'])!=int or att['archive_epochs']!=2 or
        type(att['mpfr_replayed_frames'])!=int or att['mpfr_replayed_frames']!=6 or att['proof_replayed'] is not True or
        att['scientific_release']!='NO_GO' or att['verified_source']!='original_CH23_independent_MPFR_224'):
        raise ValueError('False scientific scope')
    for name in ('binding_sha256','archive_sha256'):
        if type(att[name])!=str or not HEX64.fullmatch(att[name]):raise ValueError('Malformed bound hash')
    return att

def verify_checker_receipt(receipt,attestation,case,nonce,policy_hash):
    if type(receipt)!=dict or set(receipt)!={'version','case_id','nonce','policy_sha256',
           'worker_attestation_sha256','checker_attestation_sha256','checker_result','checker_scope'}:
        raise ValueError('Checker receipt schema mismatch')
    if (type(receipt['version'])!=int or receipt['version']!=1 or receipt['case_id']!=case or
        receipt['nonce']!=nonce or receipt['policy_sha256']!=policy_hash or
        receipt['checker_result']!='INDEPENDENT_REPLAY_ACCEPTED' or
        receipt['checker_scope']!='FROZEN_CH23_127_NODES_6_FRAMES_MPFR_224'):
        raise ValueError('Checker receipt scope or challenge mismatch')
    value=objhash(attestation)
    if receipt['worker_attestation_sha256']!=value or receipt['checker_attestation_sha256']!=value:
        raise ValueError('Checker did not independently agree with worker attestation')
    return receipt

def verify_ticket(ticket,pem,expected_fingerprint,policy_hash,case,nonce,pins):
    if sha(pem)!=expected_fingerprint:raise ValueError('Attestor key replacement')
    b=verify_signature(ticket,pem,V_DOMAIN)
    if set(b)!={'version','nonce','case_id','policy_sha256','attestor_fingerprint_sha256','attestation','checker_receipt','caps_receipt'} or b['version']!=1:
        raise ValueError('Unexpected attestor ticket fields')
    if type(b['nonce'])!=str or not HEX64.fullmatch(b['nonce']) or b['nonce']!=nonce:
        raise ValueError('Attestor response replay or challenge mismatch')
    if b['case_id']!=case or b['policy_sha256']!=policy_hash or b['attestor_fingerprint_sha256']!=expected_fingerprint:
        raise ValueError('Attestor ticket does not bind protected policy')
    if case not in pins:raise ValueError('Unknown frozen case')
    verify_attestation(b['attestation'],case,pins[case]);verify_checker_receipt(b['checker_receipt'],b['attestation'],case,nonce,policy_hash)
    from caps_policy40g import validate_caps
    validate_caps(b['caps_receipt'],case,nonce,policy_hash,pins[case])
    return b['attestation']
