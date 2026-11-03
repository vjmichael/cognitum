#!/usr/bin/env python3
"""Windows-portable, read-only CH39 archive and signature audit.

Requires Python >=3.9 and the external cryptography package. Never imports
Linux-only trust39.py (fcntl/O_NOFOLLOW), never signs or runs proof workers.
All trust roots are pinned here, independent of package-extracted metadata.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

EXPECTED_ZIP_SHA256 = '9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
EXPECTED_SIGNER_FP = 'ec53b6f7bb956665be5ff9b07b149456992c8df0ce92e4f8fb3c5156b16035ee'
EXPECTED_ATTESTOR_FP = 'a7aac9b236a27959fd087adbad2841b2f3147c447ac5c755dfba6b025c9ae2bb'
EXPECTED_TIP = '112980038c992461c0eaf43c2d3f066191e4c7404b058ba434c1ba1352af68c5'
EXPECTED_CASE_COUNT = 15
EXPECTED_MANIFEST_COUNT = 1099
ZERO = '0' * 64


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def strict_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key: '+str(key))
        value[key] = item
    return value


def strict_json(raw: bytes):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=strict_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))


def is_safe_name(name: str) -> bool:
    # Windows alternate stream/absolute/dot/traversal forms are never extracted.
    if not name or name.startswith(('/', '\\')) or ':' in name or '\\' in name or '\x00' in name:
        return False
    bits = name.rstrip('/').split('/')
    return bool(bits) and all(part not in ('', '.', '..') and not part.endswith((' ', '.')) for part in bits)


def check_package(package: Path, root: Path):
    if not package.is_file():
        raise ValueError('CH39 reproduction ZIP not found: '+str(package))
    actual = file_digest(package)
    if actual != EXPECTED_ZIP_SHA256:
        raise ValueError('ZIP SHA-256 mismatch; expected '+EXPECTED_ZIP_SHA256+' got '+actual)
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(not is_safe_name(n) for n in names):
            raise ValueError('Duplicate or unsafe ZIP member')
        if 'SHA256SUMS_FULL_CH39.json' not in names:
            raise ValueError('Root CH39 manifest absent')
        manifest = strict_json(archive.read('SHA256SUMS_FULL_CH39.json'))
        if type(manifest) is not dict or len(manifest) != EXPECTED_MANIFEST_COUNT:
            raise ValueError('Manifest count differs from pinned CH39 count')
        if set(names) != set(manifest) | {'SHA256SUMS_FULL_CH39.json'}:
            raise ValueError('ZIP members do not match root manifest')
        for name, value in manifest.items():
            if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('Malformed manifest entry '+name)
            if archive.getinfo(name).is_dir():
                raise ValueError('Manifest contains directory entry '+name)
            # Hash *extracted* bytes to catch I/O errors beyond ZIP integrity.
            target = root.joinpath(*name.split('/'))
            if not target.is_file() or target.is_symlink() or file_digest(target) != value:
                raise ValueError('Extracted file missing or SHA-256 changed: '+name)
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC corrupt')
    return {'zip_sha256':actual, 'manifest_sha256_verified_files':len(manifest), 'members':len(names)}


def audit_witness(root: Path):
    # Imports are deliberately limited to CH39's cryptographic primitives;
    # trust39's Linux-only safe_read() and fcntl must NOT be called on Windows.
    sys.path.insert(0, str(root/'CH_C14_39'))
    from protocol39 import (canonical, objhash, parse, sha,
                            verify_signature, verify_ticket, S_DOMAIN)
    public = root/'CH_C14_39'/'CH39_public_witness'
    pins = parse((public/'frozen_pins.json').read_bytes(), 65536)
    heads = strict_json((root/'CH_C14_32'/'heads.json').read_bytes())
    checkpoints = strict_json((root/'CH_C14_33'/'checkpoint_heads.json').read_bytes())
    if (type(pins) is not dict or type(heads) is not dict or type(checkpoints) is not dict
            or len(pins) != EXPECTED_CASE_COUNT or set(pins) != set(heads) or set(pins) != set(checkpoints)):
        raise ValueError('Original CH32/CH33 case set mismatch')
    for case, p in sorted(pins.items()):
        cpfile = root/'CH_C14_33'/'active'/case/'checkpoint.json'
        expected = {'original_head_sha256':heads[case], 'checkpoint_sha256':checkpoints[case],
                    'checkpoint_file_sha256':sha(cpfile.read_bytes()), 'nodes':127}
        if p != expected:
            raise ValueError('Frozen case source mismatch: '+case)

    signer_public = (public/'public.ed25519.pem').read_bytes()
    attestor_public = (public/'attestor_public.ed25519.pem').read_bytes()
    if sha(signer_public) != EXPECTED_SIGNER_FP or sha(attestor_public) != EXPECTED_ATTESTOR_FP:
        raise ValueError('Unexpected signer or attestor public key fingerprint')

    rec = parse((public/'HEAD').read_bytes())
    if objhash(rec) != EXPECTED_TIP:
        raise ValueError('Pinned witness HEAD rollback or modification')
    policy_hash = objhash(pins)
    seen_cases, seen_nonces, seen_files = set(), set(), set()
    n = 0
    cases = []
    while True:
        hash_current = objhash(rec)
        body = verify_signature(rec, signer_public, S_DOMAIN)
        exact = {'version', 'generation', 'parent', 'case_id', 'signer_fingerprint_sha256',
                 'attestor_fingerprint_sha256', 'policy_sha256', 'attestor_ticket', 'scientific_release'}
        if (set(body) != exact or type(body['version']) is not int or body['version'] != 2
                or type(body['generation']) is not int or body['generation'] != EXPECTED_CASE_COUNT - 1 - n):
            raise ValueError('Bad signed witness generation/schema')
        if (body['signer_fingerprint_sha256'] != EXPECTED_SIGNER_FP
                or body['attestor_fingerprint_sha256'] != EXPECTED_ATTESTOR_FP
                or body['policy_sha256'] != policy_hash or body['scientific_release'] != 'NO_GO'):
            raise ValueError('Signed witness policy/fingerprint/release altered')
        case = body['case_id']
        if type(case) is not str or case not in pins or case in seen_cases:
            raise ValueError('Signed case duplicated or unknown')
        ticket = body['attestor_ticket']
        if type(ticket) is not dict or type(ticket.get('body')) is not dict:
            raise ValueError('Attestor signed ticket absent')
        nonce = ticket['body'].get('nonce')
        if type(nonce) is not str or nonce in seen_nonces:
            raise ValueError('Repeated or invalid ticket challenge')
        verify_ticket(ticket, attestor_public, EXPECTED_ATTESTOR_FP, policy_hash, case, nonce, pins)
        seen_cases.add(case)
        seen_nonces.add(nonce)
        cases.append(case)
        filename = f'{body["generation"]:08d}_{hash_current}.json'
        stored = public/'revisions'/filename
        if parse(stored.read_bytes()) != rec:
            raise ValueError('Signed revision missing or altered: '+filename)
        seen_files.add(filename)
        n += 1
        if body['generation'] == 0:
            if body['parent'] != ZERO:
                raise ValueError('Genesis linkage invalid')
            break
        parent = body['parent']
        prev = public/'revisions'/f'{body["generation"]-1:08d}_{parent}.json'
        rec = parse(prev.read_bytes())
        if objhash(rec) != parent:
            raise ValueError('Parent hash mismatch')
    if len(seen_cases) != EXPECTED_CASE_COUNT or n != EXPECTED_CASE_COUNT:
        raise ValueError('Signed cases incomplete')
    existing = {p.name for p in (public/'revisions').iterdir()}
    if existing != seen_files:
        raise ValueError('Orphaned or unknown witness revisions')
    return {'signed_cases':n,'original_case_pins_matched':len(pins),
            'attestor_signatures_verified':n,'final_signer_signatures_verified':n,
            'terminal_witness_tip':EXPECTED_TIP,'case_ids_in_witness_order':list(reversed(cases)),
            'fresh_mpfr_performed':False,'linux_uid_boundary_exercised':False,
            'scientific_disposition':'NO_GO'}


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--package',type=Path,required=True)
    a.add_argument('--root',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True)
    args = a.parse_args()
    out={'status':'FAIL','platform':sys.platform,'python':sys.version.split()[0],
         'mode':'portable offline Windows cryptographic and file-integrity audit'}
    try:
        out['package']=check_package(args.package,args.root)
        out['public_witness']=audit_witness(args.root)
        out['status']='PASS'
    except Exception as exc:
        out['error']=f'{type(exc).__name__}: {exc}'
        print('FAIL:',out['error'],file=sys.stderr)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,sort_keys=True,indent=2))
    return 0 if out['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
