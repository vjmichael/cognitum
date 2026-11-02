"""Pack original CH23–CH30 provenance + CH31 research code/measurements.

Repack historical bytes from the verified CH30 reproduction zip without
rebuilding or altering any frozen original historical content.
"""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
HISTORY=BASE/'Cognitum_CH_C14_30_Incremental_Verifier_Original_CH23_2026-11-02.zip'
FULL=BASE/'Cognitum_CH_C14_31_Progressive_Verification_Cold_Restart_Original_CH23_2026-11-02.zip'
EVID=BASE/'CH_C14_31_Progressive_Restart_Evidence.zip'
LOCAL=['prefix31.py','verifier31.py','restart31.py','benchmark31.py','audit31.py',
       'make_report31.py','package31.py','tests/test_progressive.py',
       'frozen_protocol.json','frozen_protocol.sha256','README.md',
       'Engineering_Report_CH_C14_31.md','benchmark_results.json',
       'benchmark.log','pytest.log']

def digest(b):return hashlib.sha256(b).hexdigest()

def main():
    files={}
    with zipfile.ZipFile(HISTORY,'r') as src:
        if src.testzip() is not None:raise RuntimeError('Historical archive CRC failure')
        for name in src.namelist():
            if '..' in Path(name).parts or name.startswith('/') or name in files:
                raise RuntimeError('Unsafe or duplicate historical archive path')
            files[name]=src.read(name)
    for name in LOCAL:
        p=D/name
        if not p.is_file():raise RuntimeError('Missing CH31 source: '+name)
        filekey='CH_C14_31/'+name
        if filekey in files:raise RuntimeError('Duplicate CH31 path')
        files[filekey]=p.read_bytes()
    digestmap={name:digest(content) for name,content in files.items()}
    manifest=json.dumps(digestmap,indent=2,sort_keys=True)+'\n'
    extra='CH_C14_31/SHA256SUMS_FULL_CH31.json'
    if extra in files:raise RuntimeError('Duplicate manifest')
    with zipfile.ZipFile(FULL,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for key in sorted(files):out.writestr(key,files[key])
        out.writestr(extra,manifest)
    (D/'SHA256SUMS_FULL_CH31.json').write_text(manifest)
    with zipfile.ZipFile(EVID,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for name in LOCAL:out.writestr('CH_C14_31/'+name,(D/name).read_bytes())
        out.writestr(extra,manifest)
    with zipfile.ZipFile(FULL) as z:
        for p,h in digestmap.items():
            if digest(z.read(p))!=h:raise RuntimeError('Repacked payload checksum mismatch: '+p)
        if z.testzip() is not None:raise RuntimeError('ZIP CRC failure')
    with zipfile.ZipFile(EVID) as z:
        for name in LOCAL:
            p='CH_C14_31/'+name
            if digest(z.read(p))!=digestmap[p]:raise RuntimeError('Evidence digest mismatch')
    print(json.dumps({'historical':HISTORY.name,'historical_file_count':len(files)-len(LOCAL),
        'new_research_files':len(LOCAL),'full_entries':len(files)+1,
        'manifest_count':len(digestmap),'full_zip':str(FULL),'full_zip_sha256':digest(FULL.read_bytes()),
        'evidence_zip':str(EVID),'evidence_zip_sha256':digest(EVID.read_bytes())},indent=2))

if __name__=='__main__':main()
