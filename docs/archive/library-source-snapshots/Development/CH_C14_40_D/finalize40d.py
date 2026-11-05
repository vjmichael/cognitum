"""Independently replay and freeze all CH40-D exported local witnesses.

Per-case source and witness bytes are never trusted merely for being saved.
Each of four local witness objects is recomputed by the separate verifier.
"""
import argparse,hashlib,json,pathlib,zipfile
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256
from witness_checker40d import verify
from witness_producer40d import obj_sha

ROOT=pathlib.Path(__file__).resolve().parent
ARCHIVE=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
TYPES=['DIRECT','COUPLED_TANGENT','TAYLOR2','KRAWCZYK']

def finalize(archive,out):
    archive=pathlib.Path(archive);out=pathlib.Path(out)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ORIGINAL_ZIP_SHA256:raise ValueError('External historical ZIP SHA256 mismatch')
    entries={};allvalid=0;status={};certified_historical=0
    with zipfile.ZipFile(archive) as z:
        pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
        for case in sorted(pins):
            fp=out/(case+'.json')
            if not fp.exists():raise ValueError('Missing original case witness: '+case)
            payload=json.loads(fp.read_bytes())
            if payload['case']!=case or payload['source_archive_sha256']!=ORIGINAL_ZIP_SHA256 or payload['scientific_release']!='NO_GO':raise ValueError('Forged case identity')
            cert=decode_case(z,case,pins)
            if payload['source_certificate_sha256']!=obj_sha(cert):raise ValueError('Wrong historical certificate digest')
            if sorted(payload['witnesses'])!=sorted(TYPES) or sorted(payload['receipts'])!=sorted(TYPES):raise ValueError('Missing/extra proof types')
            for kind in TYPES:
                got=verify(cert,payload['witnesses'][kind])
                if got!=payload['receipts'][kind]:raise ValueError('Forged verifier receipt '+case+'/'+kind)
                if got['global_optimality_certified'] or got['scientific_release']!='NO_GO':raise ValueError('Illegal scientific promotion')
                allvalid+=1;certified_historical+=bool(got['historical_producer_cap_certified'])
            entries[case]={'status':'PASS','witness_file_sha256':hashlib.sha256(fp.read_bytes()).hexdigest(),
                           'source_certificate_sha256':obj_sha(cert),
                           'newton':payload['witnesses']['KRAWCZYK']['claim']['status'],
                           'witnesses':len(TYPES)}
            status[entries[case]['newton']]=status.get(entries[case]['newton'],0)+1
            print('AUDIT PASS',case,'witnesses',len(TYPES),'newton',entries[case]['newton'],flush=True)
    report={'protocol':'CH40D-LOCAL-WITNESS-V1','source_zip_sha256':ORIGINAL_ZIP_SHA256,
            'status':'PASS_LOCAL_WITNESS_VERIFY_ONLY',
            'cases_verified':len(entries),'local_witnesses_verified':allvalid,
            'methods':TYPES,'newton_diagnostic_counts':status,
            'historical_displays_individually_supported':certified_historical,
            'complete_archived_optimized_producer_bound_certification':False,
            'ch39_live_attestation_integration':False,
            'bounded_root_global_gap_certified':False,'unrestricted_global_optimality_certified':False,
            'scientific_release':'NO_GO','case_hashes':entries,
            'math_independence':'CH40-B producer uses 85-digit Decimal IV; standalone CH40-D checker implements rational directed coupled/direct bounds and separately written 95-digit Decimal derivatives; both Decimal transcendental backends are libmpdec, not algorithmically independent native transcendental libraries.'}
    path=out/'CH40D_FINAL_ACCEPTANCE.json'
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path,default=ARCHIVE);p.add_argument('--out',type=pathlib.Path,default=ROOT/'CH40D_RESULTS')
    a=p.parse_args();r=finalize(a.archive,a.out);print('CH40D SUMMARY:',r['status'],r['cases_verified'],'cases',r['local_witnesses_verified'],'witnesses')