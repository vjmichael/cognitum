"""CH40-A pinned original CH39/CH33 certificate loader and independent checker.

Validates the literal external original CH39 ZIP hash and all checkpoint file,
envelope, compressed certificate and case-ID pins before any pure Decimal math.
No OS/MPFR/legacy verifier imports. Explicitly fails closed on scientific GO.
"""
import argparse, base64, hashlib, io, json, pathlib, sys, time, zlib
from independent_checker40 import verify_certificate,canonical,digest

ORIGINAL_ZIP_SHA256='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'


def decode_case(z,case,pins):
    if case not in pins:raise ValueError('Unfrozen case ID')
    path=f'CH_C14_33/active/{case}/checkpoint.json'
    raw=z.read(path)
    if hashlib.sha256(raw).hexdigest()!=pins[case]['checkpoint_file_sha256']:
        raise ValueError('Checkpoint original source hash mismatch')
    e=json.loads(raw)
    if set(e)!={'body','sha256'} or digest(e['body'])!=e['sha256'] or e['sha256']!=pins[case]['checkpoint_sha256']:
        raise ValueError('Checkpoint envelope source pin mismatch')
    b=e['body']
    if b['case_id']!=case or b['head_sha256']!=pins[case]['original_head_sha256'] or b['stage_nodes']!=pins[case]['nodes']:
        raise ValueError('Checkpoint source identity mismatch')
    compressed=base64.b64decode(b['compressed_certificate'],validate=True)
    de=zlib.decompressobj()
    certificate=de.decompress(compressed,8*1024*1024+1)
    if len(certificate)>8*1024*1024 or not de.eof or de.unused_data or de.unconsumed_tail:
        raise ValueError('Unbounded or malformed compressed proof')
    if hashlib.sha256(certificate).hexdigest()!=b['certificate_sha256']:
        raise ValueError('Checkpoint mathematical content hash mismatch')
    cert=json.loads(certificate)
    if canonical(cert)!=certificate or len(cert['nodes'])!=pins[case]['nodes']:
        raise ValueError('Noncanonical or wrong-length original certificate')
    # Verify a frozen original research identity (not a mere filename match).
    if cert['research_case_id']!=case:
        raise ValueError('Original research ID mismatch')
    # The CH29 protocol supplies a separate SHA-256 for each original case.
    # That digest is NOT equal to the original data_digest: it covers the
    # frozen case wrapper and must be checked against the proper source.
    protocol=json.loads(z.read('CH_C14_29/frozen_protocol.json'))
    if cert['original_case_sha256']!=protocol['original_case_sha256'][case]:
        raise ValueError('Original CH29 case digest does not match protocol')
    return cert


def verify_archive(path,cases=None):
    import zipfile
    archive=pathlib.Path(path)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:
        raise ValueError('Untrusted CH39 ZIP: external original digest mismatch')
    results=[]
    with zipfile.ZipFile(archive) as z:
        pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
        for case in (sorted(pins) if not cases else cases):
            print('INDEPENDENT_DECIMAL40',case,flush=True)
            began=time.monotonic();cert=decode_case(z,case,pins)
            result=verify_certificate(cert)
            results.append({'case_id':case,'seconds':round(time.monotonic()-began,3),'result':result})
            print('PASS',case,result['leaf_bounds_independently_recomputed'],'leaf bounds, bounded gap proven?',result['bounded_gap_proven_by_independent_checker'],flush=True)
    return results


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=pathlib.Path)
    ap.add_argument('--case',action='append',default=None)
    ap.add_argument('--out',type=pathlib.Path)
    a=ap.parse_args()
    res=verify_archive(a.archive,a.case)
    summary={'version':'CH40A','source_archive_sha256':ORIGINAL_ZIP_SHA256,'status':'INDEPENDENT_FINITE_BOX_REPLAYED_UNRESOLVED' if all(not r['result']['bounded_gap_proven_by_independent_checker'] for r in res) else 'REVIEW_REQUIRED','cases':res,'no_scientific_global_claim':True,'production_release':'NO_GO'}
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'cases':len(res),'status':summary['status']}))
    return 0
if __name__=='__main__':raise SystemExit(main())