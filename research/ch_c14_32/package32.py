"""Reproducible CH32 source+original-data evidence archive and SHA manifest."""
from __future__ import annotations
import hashlib,json,os,zipfile
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
ROOTS=[(BASE/'recovered_ch23/CH_C14_23','CH_C14_23')]+[(BASE/f'CH_C14_{n}',f'CH_C14_{n}') for n in range(24,33)]
EXT={'.py','.json','.jsonl','.md','.txt','.sha256','.csv','.log'}

def files():
    for root,name in ROOTS:
        if not root.is_dir():raise FileNotFoundError(root)
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.is_symlink() or p.suffix.lower() not in EXT:continue
            rel=p.relative_to(root)
            if any(x in {'__pycache__','.pytest_cache','transport','Transport','.git'} for x in rel.parts):continue
            if p.name.startswith('.') or (name=='CH_C14_32' and p.name=='SHA256SUMS_CH32_PACKAGE.json'):continue
            if name=='CH_C14_32':
                if rel.parts[0]=='journals':
                    if p.suffix!='.json':continue
                elif rel.parts[0]=='results':continue
                elif p.name in {'benchmark_pilot.log','pytest_verbose.log','clean_pytest.log'}:continue
            elif name=='CH_C14_29' and 'transport' in rel.parts:continue
            elif p.suffix=='.log' and name!='CH_C14_32':continue
            yield p,f'{name}/{rel.as_posix()}'

def build():
    if not (D/'benchmark_results.json').is_file() or not (D/'heads.json').is_file():
        raise FileNotFoundError('CH32 full-case evidence absent')
    rows=list(files())
    manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for path,name in rows}
    mbytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    full=BASE/'Cognitum_CH_C14_32_Durable_Proof_Journal_Original_CH23_2026-11-02.zip'
    with zipfile.ZipFile(full,'w',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for path,name in rows:z.write(path,name)
        z.writestr('SHA256SUMS_CH32_PACKAGE.json',mbytes)
    (D/'SHA256SUMS_CH32_PACKAGE.json').write_bytes(mbytes)
    with zipfile.ZipFile(full) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate ZIP paths')
        for name,expected in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected:raise AssertionError(name)
        if z.read('SHA256SUMS_CH32_PACKAGE.json')!=mbytes:raise ValueError('Wrong manifest')
    evidence=BASE/'Cognitum_CH_C14_32_Journal_Evidence_15_Original_CH23_2026-11-02.zip'
    selected=[(p,name) for p,name in rows if name.startswith('CH_C14_32/journals/') or name in {
              'CH_C14_32/benchmark_results.json','CH_C14_32/heads.json','CH_C14_32/frozen_protocol.json',
              'CH_C14_32/frozen_protocol.sha256','CH_C14_32/Engineering_Report_CH_C14_32.md',
              'CH_C14_32/pytest.log','CH_C14_32/benchmark.log'}]
    with zipfile.ZipFile(evidence,'w',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p,n in selected:z.write(p,n)
        z.writestr('SHA256SUMS_CH32_EVIDENCE.json',(json.dumps({n:manifest[n] for _,n in selected},indent=2,sort_keys=True)+'\n'))
    print(json.dumps({'full_zip':str(full),'full_files':len(rows),'full_sha256':hashlib.sha256(full.read_bytes()).hexdigest(),
                      'evidence_zip':str(evidence),'evidence_files':len(selected),
                      'evidence_sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()},indent=2))
if __name__=='__main__':build()
