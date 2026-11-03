"""Package CH38 and preserve prior CH37 historical artifacts byte-for-byte."""
from __future__ import annotations
import hashlib,json,shutil,tempfile,zipfile
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=Path('/mnt/data')
BASE=ROOT/'Cognitum_CH_C14_37_Three_UID_Dual_Signed_Original_CH23_2026-11-02.zip'
FULL=ROOT/'Cognitum_CH_C14_38_Four_UID_Attestor_Original_CH23_2026-11-02.zip'
EVID=ROOT/'Cognitum_CH_C14_38_Four_UID_Evidence_2026-11-02.zip'
NAMES=['protocol38.py','trust38.py','math38.py','attestor38.py','signer38.py','harness38.py',
       'audit38.py','freeze38.py','package38.py','make_report38.py','README.md','Engineering_Report_CH_C14_38.md',
       'frozen_protocol.json','original15_results.json','public_audit.json','ch38_tests.log','all15_run.log',
       'tests/test_protocol38.py','tests/test_attestor38.py','tests/test_live_denial.py']
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    with zipfile.ZipFile(BASE) as f:
        if f.testzip():raise ValueError('CH37 historical archive corrupted')
        parent={x:hashlib.sha256(f.read(x)).hexdigest() for x in f.namelist() if not x.endswith('/')}
    if any(not (D/n).is_file() for n in NAMES):raise FileNotFoundError('Incomplete accepted CH38 evidence')
    if not (D/'CH38_public_witness/HEAD').exists():raise ValueError('No accepted public four-UID witness')
    with tempfile.TemporaryDirectory(prefix='CH38-package-') as t:
        stage=Path(t)
        with zipfile.ZipFile(BASE) as f:f.extractall(stage)
        target=stage/'CH_C14_38';target.mkdir()
        for n in NAMES:
            s=D/n;dest=target/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,dest)
        for f in sorted((D/'CH38_public_witness').rglob('*')):
            if f.is_file():
                if 'secret' in f.name.lower() or f.name.endswith('.pending'):
                    raise ValueError('Would package private key or uncommitted witness')
                dest=target/'CH38_public_witness'/f.relative_to(D/'CH38_public_witness')
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
        newfiles=sorted(p for p in target.rglob('*') if p.is_file())
        allfiles=sorted(p for p in stage.rglob('*') if p.is_file())
        manifest={str(p.relative_to(stage)):digest(p) for p in allfiles}
        (stage/'SHA256SUMS_FULL_CH38.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        with zipfile.ZipFile(FULL,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as f:
            for p in sorted(x for x in stage.rglob('*') if x.is_file()):f.write(p,p.relative_to(stage).as_posix())
        with zipfile.ZipFile(EVID,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as f:
            for p in newfiles:f.write(p,p.relative_to(stage).as_posix())
        with zipfile.ZipFile(FULL) as f:
            if f.testzip():raise ValueError('Full CH38 package damaged')
            for n,sha in parent.items():
                if hashlib.sha256(f.read(n)).hexdigest()!=sha:raise ValueError('Original CH37 package modified: '+n)
            for n,sha in manifest.items():
                if hashlib.sha256(f.read(n)).hexdigest()!=sha:raise ValueError('CH38 SHA256 manifest mismatch: '+n)
        with zipfile.ZipFile(EVID) as f:
            if f.testzip():raise ValueError('Evidence package damaged')
        final={'status':'PASS','preserved_original_CH37_files':len(parent),
               'source_and_evidence_added':len(newfiles),'full_manifest_verified_entries':len(manifest),
               'full_archive_bytes':FULL.stat().st_size,'full_archive_sha256':digest(FULL),
               'evidence_archive_bytes':EVID.stat().st_size,'evidence_archive_sha256':digest(EVID),
               'private_keys_in_packages':False}
        (D/'package_results.json').write_text(json.dumps(final,sort_keys=True,indent=2)+'\n')
        print(json.dumps(final,sort_keys=True))
if __name__=='__main__':main()
