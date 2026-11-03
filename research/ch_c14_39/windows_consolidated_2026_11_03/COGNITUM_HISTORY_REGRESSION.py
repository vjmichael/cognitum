#!/usr/bin/env python3
"""CH23-CH39 portable consolidated historical audit and attack-suite.

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


# -- Consolidated cross-milestone regression --
# All package trust constants are defined independently above, never read from ZIP metadata.
import ctypes
import ctypes.util
import datetime as dt
import importlib
import shutil
import tempfile
import time
import traceback
from contextlib import contextmanager

ARCHIVE_NAME = 'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
HISTORICAL_MANIFESTS = {
    'CH32': ('SHA256SUMS_CH32_PACKAGE.json', 778),
    'CH33': ('SHA256SUMS_FULL_CH33.json', 851),
    'CH35': ('SHA256SUMS_FULL_CH35.json', 934),
    'CH36': ('SHA256SUMS_FULL_CH36.json', 973),
    'CH37': ('SHA256SUMS_FULL_CH37.json', 1012),
    'CH38': ('SHA256SUMS_FULL_CH38.json', 1052),
    'CH39': ('SHA256SUMS_FULL_CH39.json', 1099),
}

class Blocked(Exception):
    pass


def print_line(text):
    print(text, flush=True)


def add_test(report, name, fun, kind='LIVE'):
    start = time.monotonic()
    try:
        details = fun()
        outcome = {'name': name, 'status': 'PASS', 'kind': kind, 'seconds': round(time.monotonic()-start, 3)}
        if details is not None: outcome['details'] = details
        print_line('PASS: ' + name)
    except Blocked as exc:
        outcome = {'name': name, 'status': 'BLOCKED', 'kind': kind, 'reason': str(exc)}
        print_line('BLOCKED: ' + name + ' — ' + str(exc))
    except Exception as exc:
        outcome = {'name': name, 'status': 'FAIL', 'kind': kind, 'reason': type(exc).__name__ + ': ' + str(exc)}
        print_line('FAIL: ' + name + ' — ' + outcome['reason'])
    report['tests'].append(outcome)
    return outcome


def required(cond, message):
    if not cond: raise ValueError(message)


def archived_manifest_chain(package: Path):
    previous = {}
    results = {}
    with zipfile.ZipFile(package) as z:
        all_names = set(z.namelist())
        for milestone, (manifest_file, expected_count) in HISTORICAL_MANIFESTS.items():
            manifest = strict_json(z.read(manifest_file))
            required(type(manifest) is dict and len(manifest) == expected_count,
                     milestone + ' historical manifest item count mismatch')
            required(set(previous.items()).issubset(set(manifest.items())),
                     milestone + ' rewrote a historical manifest entry')
            for name, expected_hash in manifest.items():
                required(name in all_names, milestone+' historical source missing: '+name)
                required(type(expected_hash) is str and len(expected_hash)==64,
                         milestone+' malformed digest for '+name)
                required(digest(z.read(name))==expected_hash,
                         milestone+' historical file changed: '+name)
            results[milestone] = {'files_verified':len(manifest), 'status':'PASS'}
            previous = manifest
    return results


def milestone_inventory(package: Path):
    with zipfile.ZipFile(package) as z:
        names=set(z.namelist())
        counts={}
        for i in range(23,40):
            m='CH_C14_'+str(i)
            cnt=sum(name.startswith(m+'/') for name in names)
            required(cnt>=1, 'Missing historical milestone '+m)
            counts[m]=cnt
        # Original CH25 fixture identity, not an independent re-run of its optimizer.
        cases=[name.removeprefix('CH_C14_25/inputs/').removesuffix('.json')
               for name in names if name.startswith('CH_C14_25/inputs/') and name.endswith('.json')]
        expected=set(strict_json(z.read('CH_C14_32/heads.json')))
        required(len(expected)==15 and set(cases)==expected, 'CH25/CH32 frozen fixture case mismatch')
        certificates={name.removeprefix('CH_C14_25/certificates/').removesuffix('.json')
               for name in names if name.startswith('CH_C14_25/certificates/') and name.endswith('.json')}
        required(certificates==expected,'CH25 frozen certificate case mismatch')
        required(set(strict_json(z.read('CH_C14_33/checkpoint_heads.json')))==expected,
                 'CH33 checkpoint case inventory mismatch')
        return {'milestone_file_counts':counts, 'frozen_original_cases':len(expected),
                'scientific_global_optimality':'NO_GO',
                'scope':'Archive source/fixture inventory only, not live mathematical recomputation'}


@contextmanager
def changed_file(path: Path, transform):
    before = path.read_bytes()
    try:
        path.write_bytes(transform(before))
        yield
    finally:
        path.write_bytes(before)


def json_change(original: bytes, change):
    doc=strict_json(original)
    change(doc)
    return (json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n').encode()


def must_reject(fun):
    try:
        fun()
    except Exception as exc:
        return {'rejection_type':type(exc).__name__}
    raise AssertionError('The deliberately corrupted evidence was accepted')


def negative_tests(root: Path, package: Path, report):
    public=root/'CH_C14_39'/'CH39_public_witness'
    head=public/'HEAD'
    pins=public/'frozen_pins.json'
    src_heads=root/'CH_C14_32'/'heads.json'
    original_checkpoint=root/'CH_C14_33'/'active'/'one_event_n80_i00'/'checkpoint.json'
    signer_key=public/'public.ed25519.pem'
    records=sorted((public/'revisions').glob('*.json'))
    required(len(records)==15, 'Expected exactly 15 signed revisions')

    def mutate_reject(label, path, transform):
        def test():
            with changed_file(path,transform):
                return must_reject(lambda:audit_witness(root))
        add_test(report,label,test,kind='ADVERSARIAL_TEMP_COPY')

    mutate_reject('changed witness HEAD case ID',head,
                  lambda b: json_change(b,lambda d: d['body'].__setitem__('case_id','one_event_n80_i00')))
    mutate_reject('rollback witness HEAD by one generation',head,
                  lambda b: records[-2].read_bytes())
    mutate_reject('tampered final signer public key',signer_key,
                  lambda b: b+b'\n')
    mutate_reject('tampered frozen witness case pin',pins,
                  lambda b: json_change(b,lambda d: d['one_event_n80_i00'].__setitem__('nodes',126)))
    mutate_reject('tampered CH33 proof checkpoint',original_checkpoint,
                  lambda b: b+b'\n')
    mutate_reject('tampered CH32 original journal-head pin',src_heads,
                  lambda b: json_change(b,lambda d: d.__setitem__('one_event_n80_i00','0'*64)))
    mutate_reject('altered historical witness revision',records[0],
                  lambda b: b+b'\n' if False else b.replace(b'"signature"',b'"signatureX"',1))

    def missing_revision():
        path=records[0]
        contents=path.read_bytes()
        path.unlink()
        try: return must_reject(lambda:audit_witness(root))
        finally: path.write_bytes(contents)
    add_test(report,'missing signed witness revision',missing_revision,kind='ADVERSARIAL_TEMP_COPY')

    def orphan_revision():
        path=public/'revisions'/('99999999_'+'f'*64+'.json')
        path.write_bytes(b'{}')
        try: return must_reject(lambda:audit_witness(root))
        finally: path.unlink(missing_ok=True)
    add_test(report,'orphaned forged witness revision',orphan_revision,kind='ADVERSARIAL_TEMP_COPY')

    def corrupt_zip():
        with tempfile.TemporaryDirectory(prefix='CH39_Corrupt_') as t:
            changed=Path(t)/'mutated.zip'
            shutil.copyfile(package,changed)
            with changed.open('r+b') as f:
                f.seek(-10,2)
                original_byte=f.read(1)
                f.seek(-10,2)
                f.write(bytes([original_byte[0]^1]))
            return must_reject(lambda:check_package(changed,root))
    add_test(report,'modified ZIP rejected against pinned hash',corrupt_zip,kind='ADVERSARIAL_TEMP_COPY')

    def duplicate_key():
        return must_reject(lambda:strict_json(b'{"a":1,"a":2}'))
    add_test(report,'duplicate JSON keys rejected',duplicate_key,kind='ADVERSARIAL_INPUT')

    def unsafe_paths():
        dangerous=['../evil','/absolute','C:/disk/file','x\\y','a/./b','a//b','a/../b','a/hidden:stream','n.','n ']
        required(all(not is_safe_name(s) for s in dangerous),'Unsafe Windows ZIP path accepted')
        required(all(is_safe_name(s) for s in ['CH_C14_39/README.md','folder/subfolder/file.json']),
                 'Safe archive path rejected')
        return {'blocked_paths':len(dangerous)}
    add_test(report,'path-traversal and alternate-stream rejects',unsafe_paths,kind='ADVERSARIAL_INPUT')


def mpfr_optional(root: Path, explicit_dll: str):
    # This is only the original CH31 seven-node prefix smoke, never the 127-node CH39 check.
    handle=None
    old_find=None
    try:
        if sys.platform=='win32' and ctypes.sizeof(ctypes.c_void_p)!=8:
            raise Blocked('64-bit Python required to load MPFR')
        if explicit_dll:
            mpfr=Path(explicit_dll).resolve(strict=True)
            if not mpfr.is_file() or mpfr.suffix.lower()!='.dll':
                raise Blocked('Explicit DLL is not a Windows MPFR .dll')
            if sys.platform=='win32': handle=os.add_dll_directory(str(mpfr.parent))
            old_find=ctypes.util.find_library
            ctypes.util.find_library=lambda name:str(mpfr) if name=='mpfr' else old_find(name)
        elif not ctypes.util.find_library('mpfr'):
            raise Blocked('MPFR/GMP runtime not discoverable. Install native DLLs and use -MpfrDll path')
        sys.path.insert(0,str(root/'CH_C14_31'))
        sys.path.insert(0,str(root/'CH_C14_30'))
        from verifier31 import load_original_case
        from verifier30 import verify_full
        from prefix31 import project_prefix
        case='one_event_n80_i00'
        inp,proto,duals,archived=load_original_case(case)
        cert63,_=archived(63)
        cert=project_prefix(cert63,7)
        verified=verify_full(cert,inp,{**proto,'node_budget_per_case':7},duals)
        required(verified['replay_status']=='REPLAYED_BUT_UNRESOLVED','Incorrect replay disposition')
        required(verified['nodes_verified']==7 and verified['precision_bits']==224,'Wrong node budget/precision')
        required(verified['unbounded_global_claim'] is False and verified['gap_upper_display']>0.05,
                 'Unjustified global-optimality claim')
        return {'original_case':case,'fresh_mpfr_verified_nodes':7,'precision_bits':224,
                'scientific_result':'REPLAYED_BUT_UNRESOLVED','full_127_node_replay':False}
    except OSError as e:
        # Windows missing dynamic GMP dependency usually manifests as OSError 126.
        raise Blocked('Native MPFR/GMP load error: '+str(e)) from e
    finally:
        if old_find is not None: ctypes.util.find_library=old_find
        if handle is not None:handle.close()


def compare_previous_logs(directory: Path):
    a=directory/'CH39_public_audit.json'
    b=directory/'CH39_public_audit(1).json'
    if not (a.is_file() and b.is_file()):raise Blocked('Provide both prior CH39_public_audit.json and CH39_public_audit(1).json')
    x,y=a.read_bytes(),b.read_bytes()
    required(x==y,'Previous v1/v3 audits differ')
    data=strict_json(x)
    required(data.get('status')=='PASS' and data['public_witness']['signed_cases']==15,'Previous audits did not pass')
    return {'byte_identical':True,'sha256':digest(x)}


def write_summary(path: Path, report):
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(description='One-pass CH23–CH39 frozen Windows evidence and adversarial regression')
    ap.add_argument('-MathProbe','--MathProbe',action='store_true',dest='math_probe')
    ap.add_argument('-MpfrDll','--MpfrDll',default='',dest='mpfr_dll')
    ap.add_argument('--Package',default='',dest='package')
    ap.add_argument('--ResultsDirectory',default='',dest='results')
    ap.add_argument('--PriorLogsDirectory',default='',dest='prior_logs')
    ap.add_argument('--SkipTamper',action='store_true',dest='skip_tamper')
    opts=ap.parse_args()
    directory=Path(__file__).resolve().parent
    pkg=Path(opts.package).resolve() if opts.package else (directory/ARCHIVE_NAME).resolve()
    label=dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    dest=Path(opts.results).resolve() if opts.results else directory/('COGNITUM_Regression_Results_'+label)
    if dest.exists():
        for n in range(1,100):
            candidate=dest.parent/(dest.name+'_'+str(n))
            if not candidate.exists():dest=candidate;break
        else:raise RuntimeError('Unable to create unique results folder')
    dest.mkdir(parents=True)
    report={'suite':'CH23-CH39 Windows consolidated historical proof evidence and adversarial regression',
            'version':'1.0','platform':sys.platform,'python_version':sys.version.split()[0],
            'date_local':dt.datetime.now().astimezone().isoformat(),
            'expected_original_package_sha256':EXPECTED_ZIP_SHA256,
            'status':'RUNNING', 'tests':[],
            'scope':{'archive_evidence_and_signature_reverification':True,
                     'linux_os_isolation_reproduced':False,'historical_worker_crash_replayed':False,
                     'native_full_127_node_mpfr_replay':False,'global_optimality_certified':False}}
    overall_rc=1
    try:
        print_line('Cognitum CH23–CH39 consolidated Windows regression (read-only)')
        print_line('Archived history verification is not a new scientific/global-optimality certification.')
        if sys.version_info<(3,9):raise Blocked('Python 3.9+ required')
        if not pkg.is_file():raise Blocked('Bundled original CH39 reproduction archive missing')
        actual=file_digest(pkg)
        required(actual==EXPECTED_ZIP_SHA256,'Original CH39 ZIP hash differs from independently pinned SHA-256')
        add_test(report,'original CH39 ZIP equals external SHA-256 pin',lambda:{'sha256':actual})
        try:
            import cryptography
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError as err:
            raise Blocked('Python cryptography is not installed: python -m pip install --user cryptography') from err
        report['cryptography_version']=cryptography.__version__
        with tempfile.TemporaryDirectory(prefix='CH39_History_') as td:
            root=Path(td)
            with zipfile.ZipFile(pkg) as z:
                names=z.namelist()
                required(len(names)==len(set(names)) and all(is_safe_name(n) for n in names),
                         'CH39 ZIP contains unsafe or duplicate names')
                z.extractall(root)
            p=add_test(report,'all 1,099 archived source/data SHA-256 values',lambda:check_package(pkg,root))
            if p['status']!='PASS': raise ValueError('Root manifest check failed; cannot trust historical sources')
            c=add_test(report,'CH23–CH39 milestone and frozen case inventory',lambda:milestone_inventory(pkg))
            if c['status']!='PASS': raise ValueError('Frozen original case inventory failed')
            h=add_test(report,'CH32–CH39 cumulative historical manifest preservation',lambda:archived_manifest_chain(pkg))
            if h['status']!='PASS': raise ValueError('Historical cumulative digest chain failed')
            a=add_test(report,'15-case CH39 dual Ed25519 witness chain, frozen pins, 30 signatures',lambda:audit_witness(root))
            if a['status']!='PASS': raise ValueError('Public witness chain failed')
            if not opts.skip_tamper:negative_tests(root,pkg,report)
            if opts.prior_logs:
                add_test(report,'previous CH39 v1/v3 audit JSON byte equality',lambda:compare_previous_logs(Path(opts.prior_logs)))
            if opts.math_probe:
                add_test(report,'optional fresh native 224-bit MPFR seven-node smoke',
                         lambda:mpfr_optional(root,opts.mpfr_dll),kind='OPTIONAL_MATH_SMOKE')
            report['status']='PASS' if all(t['status']=='PASS' for t in report['tests']) else (
                'BLOCKED_OPTIONAL' if any(t['status']=='BLOCKED' for t in report['tests'])
                and not any(t['status']=='FAIL' for t in report['tests']) else 'FAIL')
            overall_rc=0 if report['status']=='PASS' else 2 if report['status']=='BLOCKED_OPTIONAL' else 1
    except Blocked as e:
        report['status']='BLOCKED'
        report['reason']=str(e)
        overall_rc=2
        print_line('BLOCKED: '+str(e))
    except Exception as e:
        report['status']='FAIL'
        report['reason']=type(e).__name__+': '+str(e)
        (dest/'ERROR.log').write_text(traceback.format_exc(),encoding='utf-8')
        overall_rc=1
        print_line('FAIL: '+report['reason'])
    finally:
        report['counts']={status:sum(t['status']==status for t in report['tests'])
                          for status in ['PASS','FAIL','BLOCKED']}
        report['exit_code']=overall_rc
        write_summary(dest/'COGNITUM_REGRESSION_SUMMARY.json',report)
        print_line('Final status: '+report['status']+' | tests='+str(len(report['tests']))+
                   ' passed='+str(report['counts']['PASS'])+
                   ' failed='+str(report['counts']['FAIL'])+
                   ' blocked='+str(report['counts']['BLOCKED']))
        print_line('Results: '+str(dest/'COGNITUM_REGRESSION_SUMMARY.json'))
        print_line('No private keys created or stored; original evidence archive unchanged.')
    return overall_rc

if __name__=='__main__':
    raise SystemExit(main())
