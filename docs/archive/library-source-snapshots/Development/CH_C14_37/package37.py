"""CH37 reproducible source/evidence package with CH36 history preserved exactly.

Signers' Ed25519 private keys and transient authority state are NOT included.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile, zipfile
from pathlib import Path
D=Path(__file__).resolve().parent
ROOT=Path('/mnt/data')
BASE=ROOT/'Cognitum_CH_C14_36_All_Original_Witness_Real_ENOSPC_2026-11-02.zip'
FULL=ROOT/'Cognitum_CH_C14_37_Three_UID_Dual_Signed_Original_CH23_2026-11-02.zip'
EVIDENCE=ROOT/'Cognitum_CH_C14_37_Independent_Account_Evidence_2026-11-02.zip'
INCLUDE=['protocol37.py','trust37.py','verifier37.py','signer37.py','harness37.py',
         'audit37.py','package37.py','README.md','Engineering_Report_CH_C14_37.md',
         'frozen_protocol.json','original15_results.json','public_audit.json',
         'tests/test_protocol37.py','tests/test_fail_closed_live.py',
         'tests/test_public_archive37.py','ch37_tests.log','live_fail_closed_test.log','all15_run.log',
         'make_report37.py']

def checksum(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    with zipfile.ZipFile(BASE) as z:
        if z.testzip():raise ValueError('Prior original CH36 archive corrupted')
        previous={name:hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist() if not name.endswith('/')}
    missing=[name for name in INCLUDE if not (D/name).is_file()]
    if missing:raise FileNotFoundError(missing)
    if not (D/'CH37_public_witness/HEAD').exists():raise FileNotFoundError('Missing accepted public two-key witness chain')
    with tempfile.TemporaryDirectory(prefix='CH37-verify-package-') as td:
        stage=Path(td)
        with zipfile.ZipFile(BASE) as z:
            z.extractall(stage)
        target=stage/'CH_C14_37';target.mkdir()
        for name in INCLUDE:
            source=D/name;dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest)
        pub=D/'CH37_public_witness'
        for f in sorted(pub.rglob('*')):
            if f.is_file():
                if 'secret' in f.name.lower() or '.pending' in f.name:raise ValueError('Private or pending file included')
                dest=target/'CH37_public_witness'/f.relative_to(pub)
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(f,dest)
        newfiles=sorted([p for p in target.rglob('*') if p.is_file()])
        full_files=sorted([p for p in stage.rglob('*') if p.is_file()])
        manifest={str(p.relative_to(stage)):checksum(p) for p in full_files}
        (stage/'SHA256SUMS_FULL_CH37.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        with zipfile.ZipFile(FULL,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in sorted(x for x in stage.rglob('*') if x.is_file()):z.write(p,p.relative_to(stage).as_posix())
        with zipfile.ZipFile(EVIDENCE,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in newfiles:z.write(p,p.relative_to(stage).as_posix())
        with zipfile.ZipFile(FULL) as z:
            if z.testzip():raise ValueError('Created full archive corrupted')
            full_names=set(z.namelist())
            if not set(previous).issubset(full_names):raise ValueError('Historical original files missing')
            for name,expected in previous.items():
                if hashlib.sha256(z.read(name)).hexdigest()!=expected:raise ValueError('Historical source modified: '+name)
            combined=json.loads(z.read('SHA256SUMS_FULL_CH37.json'))
            for name,dig in combined.items():
                if hashlib.sha256(z.read(name)).hexdigest()!=dig:raise ValueError('CH37 entry hash mismatch: '+name)
        with zipfile.ZipFile(EVIDENCE) as z:
            if z.testzip():raise ValueError('Evidence archive corrupt')
        outcome={'status':'PASS','preserved_original_CH36_entries':len(previous),
                 'full_sha256_verified_entries':len(manifest),'CH37_new_entries':len(newfiles),
                 'zip_full':str(FULL),'zip_full_bytes':FULL.stat().st_size,
                 'zip_full_sha256':checksum(FULL),'zip_evidence':str(EVIDENCE),
                 'zip_evidence_bytes':EVIDENCE.stat().st_size,'zip_evidence_sha256':checksum(EVIDENCE),
                 'private_keys_included':False}
        (D/'package_results.json').write_text(json.dumps(outcome,sort_keys=True,indent=2)+'\n')
        print(json.dumps(outcome,sort_keys=True))
if __name__=='__main__':main()