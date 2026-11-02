"""Package exact immutable original CH23/CH25 sources and CH26 outputs, verify ZIP replay."""
import hashlib,zipfile,json,os
from pathlib import Path
D=Path(__file__).resolve().parent;base=D.parent
assert (D/'study_summary.json').exists(),'Compile results before packaging'
files=[]
def collect(path,dest,filterfn=None):
    for p in sorted(path.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        if filterfn is not None and not filterfn(p):continue
        files.append((p,str(Path(dest)/p.relative_to(path))))
collect(base/'recovered_ch23/CH_C14_23','CH_C14_23')
collect(base/'CH_C14_24','CH_C14_24',lambda p: p.name in ('verified_bnb.py','mpfr_interval.py','verify_certificate.py','README.md','SHA256SUMS.json') or 'tests' in p.parts)
collect(base/'CH_C14_25','CH_C14_25',lambda p:p.name in ('audit_ch25.py','README.md','SHA256SUMS.json','frozen_protocol_B.json','frozen_protocol_B.sha256','frozen_protocol.json','frozen_protocol.sha256','study_summary.json') or any(x in p.parts for x in ('inputs','certificates','verifications','logs')))
include26=lambda p: ('/transport/' not in str(p) and p.name not in ('first_pid','all_pid','hessian_pid','test_pid') and not p.name.endswith('.zip') and '__pycache__' not in p.parts)
collect(D,'CH_C14_26',include26)
for p,name in files:
    assert p.exists(),name
zipout=base/'Cognitum_CH_C14_26_Fisher_Curvature_15_Original_CH23_Cases_2026-11-02.zip'
with zipfile.ZipFile(zipout,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=True) as z:
    for p,name in files:z.write(p,name)
with zipfile.ZipFile(zipout) as z:
    names=z.namelist()
    assert len(names)==len(set(names))==len(files)
    for p,name in files:
        assert hashlib.sha256(z.read(name)).digest()==hashlib.sha256(p.read_bytes()).digest(),name
print('FULL PACKAGE',zipout,'files',len(files),'size',zipout.stat().st_size,'sha256',hashlib.sha256(zipout.read_bytes()).hexdigest())
# GitHub archival bundle preserves original 15 inputs by exact CH25 bytes, plus proof trees.
parts=[]
for sub in ('certificates','verifications','logs'):
    for p in sorted((D/sub).rglob('*')):
        if p.is_file() and p.suffix in ('.json','.log'):parts.append((p,'CH_C14_26/'+sub+'/'+p.name))
for p in sorted((base/'CH_C14_25/inputs').glob('*.json')):
    parts.append((p,'CH_C14_25/inputs/'+p.name))
for p in (D/'frozen_protocol.json',D/'frozen_protocol.sha256',D/'study_summary.json',D/'Engineering_Report_CH_C14_26.md'):
    parts.append((p,'CH_C14_26/'+p.name))
gitbundle=base/'CH_C14_26_Evidence_Original15.zip'
with zipfile.ZipFile(gitbundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p,name in parts:z.write(p,name)
with zipfile.ZipFile(gitbundle) as z:
    for p,name in parts:assert hashlib.sha256(z.read(name)).digest()==hashlib.sha256(p.read_bytes()).digest()
print('GITHUB EVIDENCE',gitbundle,'files',len(parts),'size',gitbundle.stat().st_size,'sha256',hashlib.sha256(gitbundle.read_bytes()).hexdigest())
