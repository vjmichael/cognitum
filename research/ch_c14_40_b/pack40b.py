"""Create source/reproduction packages with local SHA-256 manifest; no private keys."""
from pathlib import Path
import hashlib,json,zipfile
BASE=Path(__file__).resolve().parent
PARENT=BASE.parent
INZIP='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
EXPECTED='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
FILES=[
'exact_decimal40.py','independent_checker40.py','verify_original40.py','independent_bounds40b.py',
'independent_newton40b.py','batch40b.py','tests/test_ch40b.py',
'RUN_CH40B_INDEPENDENT_WINDOWS.cmd','pack40b.py','README.md','Engineering_Report_CH_C14_40_B.md',
'ch40b_tests.log','batch40b.log','CH40B_original15_results.json']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def create():
    if sha(BASE/INZIP)!=EXPECTED:raise ValueError('Mismatched original sealed CH39 archive')
    for name in FILES:
        if not (BASE/name).is_file():raise ValueError('Missing file '+name)
    manifest={'version':'CH40-B','external_original_CH39_archive_sha256':EXPECTED,
              'source_files':{name:sha(BASE/name) for name in FILES},
              'original_zip_member_count':None,'scientific_disposition':'NO_GO'}
    with zipfile.ZipFile(BASE/INZIP) as z:manifest['original_zip_member_count']=len(z.namelist())
    manname='CH40B_MANIFEST_SHA256.json'
    (BASE/manname).write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    outputs={
     PARENT/'Cognitum_CH_C14_40_B_Independent_Coupled_Taylor_Newton_Original_CH23_2026-11-03.zip':FILES+[manname,INZIP],
     PARENT/'Cognitum_CH_C14_40_B_Source_Tests_2026-11-03.zip':FILES+[manname]
    }
    for dest,members in outputs.items():
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in members:z.write(BASE/name,name)
        with zipfile.ZipFile(dest) as z:
            assert set(z.namelist())==set(members) and z.testzip() is None
            for name in FILES:assert hashlib.sha256(z.read(name)).hexdigest()==manifest['source_files'][name]
            if INZIP in members:assert hashlib.sha256(z.read(INZIP)).hexdigest()==EXPECTED
        print(dest, dest.stat().st_size, sha(dest))
    return outputs

if __name__=='__main__':create()
