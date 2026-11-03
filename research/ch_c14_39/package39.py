"""Bundle exact original CH38 package plus CH39 research-only source/evidence.

Strictly preserve original CH38 file bytes and verify archive member digests.
Private keys are created only in disposable /tmp signer+attestor homes; never
included. Refuses to package CH39 before all 15 audited cases and live forgery.
"""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path

BASE=Path('/mnt/data')
CH39=Path(__file__).resolve().parent
PARENT=BASE/'Cognitum_CH_C14_38_Four_UID_Attestor_Original_CH23_2026-11-02.zip'
OUT=BASE/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    a=json.loads((CH39/'original15_results.json').read_text())
    forged=json.loads((CH39/'forgery_results.json').read_text())
    audit=json.loads((CH39/'public_audit.json').read_text())
    if a['case_count']!=15 or audit['signed_cases']!=15 or audit['signer_signatures_verified']!=15 or \
      audit['attestor_signatures_verified']!=15 or forged['status']!='PASS' or forged['signature_created']:
        raise ValueError('CH39 original-data/independent-checker acceptance is incomplete')
    with zipfile.ZipFile(PARENT) as source:
        if source.testzip() is not None:raise ValueError('Parent CH38 corruption')
        base={n:source.read(n) for n in source.namelist() if not n.endswith('/')}
    for n in base:
        if n.startswith('/') or '..' in Path(n).parts or not n.startswith('CH_C14_') and n!='SHA256SUMS_FULL_CH38.json':
            raise ValueError('Unsafe parent archive entry')
    add={}
    for p in CH39.rglob('*'):
        if not p.is_file() or any(x in ('__pycache__','.pytest_cache','.writer.lock') for x in p.relative_to(CH39).parts):continue
        # Retain only accepted public 15-case witnesses; the single-case local rehearsal is not the accepted authority.
        if 'CH39_one_case_public_witness' in p.parts:continue
        if p.name.endswith('.pending') or p.suffix in ('.pem',) and ('secret' in p.name or 'private' in p.name):raise ValueError('Private/pending data detected')
        rel=(Path('CH_C14_39')/p.relative_to(CH39)).as_posix()
        if rel in base:raise ValueError('Unexpected collision with parent archive')
        add[rel]=p.read_bytes()
    frozen=json.loads(add['CH_C14_39/frozen_protocol.json'])
    for n,expected in frozen['CH39_source_sha256'].items():
        if sha(add['CH_C14_39/'+n])!=expected:raise ValueError('CH39 frozen source changed: '+n)
    sums={n:sha(b) for n,b in {**base,**add}.items()}
    if OUT.exists():raise FileExistsError('Do not overwrite a previous packaged archive')
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for n,b in sorted({**base,**add}.items()):z.writestr(n,b)
        z.writestr('SHA256SUMS_FULL_CH39.json',json.dumps(sums,sort_keys=True,indent=2)+'\n')
    with zipfile.ZipFile(OUT) as z:
        if z.testzip() is not None:raise ValueError('Generated ZIP corrupted')
        for n,expected in sums.items():
            if sha(z.read(n))!=expected:raise ValueError('Bundled source changed: '+n)
        if any(sha(z.read(n))!=sha(b) for n,b in base.items()):raise ValueError('CH38 original file changed')
    summary={'zip_name':OUT.name,'zip_sha256':sha(OUT.read_bytes()),'zip_bytes':OUT.stat().st_size,
             'preserved_CH38_files':len(base),'added_CH39_files':len(add),
             'sha256_verified_files':len(sums),'total_members':len(sums)+1,
             'private_keys_included':False,'science_release':'NO_GO'}
    (CH39/'package_results.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    print(json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
