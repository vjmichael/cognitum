"""R3-R1 real-source transport and archive refusal tests; no external network."""
from datetime import datetime, timezone
from hashlib import sha256
from copy import deepcopy
import json
import pytest

from tools.orcbench02 import capture_r3 as r
from tools.orcbench02 import cohorts as c

START=1_800_000_456_789
END=START+2000
WINDOW_END=(START//c.HOUR)*c.HOUR-2*c.HOUR
WINDOW_START=WINDOW_END-192*c.HOUR

def source(site='KSEA', hours=192):
    rows=[]
    for i in range(hours):
        second=(WINDOW_START+i*c.HOUR+50*60_000)//1000
        rows.append({
            'icaoId':site, 'obsTime':second,
            'receiptTime':datetime.fromtimestamp(second+300,timezone.utc).isoformat(),
            'rawOb':f'METAR {site} 010053Z 18010KT 10SM CLR 17/09 A3000',
            'temp':float(17+(i%9)),
        })
    return json.dumps(rows,sort_keys=True,separators=(',',':')).encode()

class Response:
    status=200
    headers={'Content-Type':'application/json; charset=utf-8', 'Date':'Sat, 21 Nov 2026 05:02:12 GMT'}
    def __init__(self,raw): self.raw=raw
    def read(self,n):
        assert n==2_000_001
        return self.raw
    def __enter__(self):return self
    def __exit__(self,*args):return False

class Opener:
    def __init__(self,raw):self.raw=raw
    def open(self,request,timeout):
        assert request.get_method()=='GET'
        assert request.full_url==r.fixed_url('KSEA')
        assert timeout==25
        return Response(self.raw)

def capture(site='KSEA'):
    raw=source(site)
    cohort=c.build_site(raw,site,capture_start_ms=START,
                        capture_end_ms=END,sha256_pin=sha256(raw).hexdigest())
    receipt={
        'schema':r.SCHEMA,'station':site,'source_url':r.fixed_url(site),
        'source_sha256':sha256(raw).hexdigest(),'source_bytes':len(raw),
        'capture_started_ms':START,'capture_completed_ms':END,
        'provider_http_date':'Sat, 21 Nov 2026 05:02:12 GMT',
        'provider_content_type':'application/json','https':'SYSTEM_CA_PINNED_DOMAIN_NO_REDIRECT',
        'preregistration_sha256':r.STUDY_PROTOCOL_SHA,
        'cohort_sha256':sha256(c.canonical(cohort)).hexdigest(),
        'source_rows':len(json.loads(raw)),
        'fixed_window_exclusive_end_ms':cohort['source_clock_end_exclusive_ms'],
        'site_horizons':[1,3,6],
        'first_capture_clock_independently_signed':False,
        'historical_public_availability_verified':False,
        'original_sensor_signed':False,'production_admission':False,
        'model_fitting_performed':False,
    }
    return raw,cohort,receipt

def test_fixed_station_url_and_original_protocol():
    assert r.fixed_url('KDEN')=='https://aviationweather.gov/api/data/metar?ids=KDEN&format=json&hours=240'
    with pytest.raises(c.Refusal):r.fixed_url('KMCI')

def test_source_mock_response_and_utc_capture_clocks():
    raw=source()
    actual,cohort,receipt=r.download_one('KSEA',opener=Opener(raw),clock=lambda:START)
    assert actual==raw and receipt['source_sha256']==sha256(raw).hexdigest()
    assert receipt['capture_started_ms']==START
    assert receipt['capture_completed_ms']==START
    assert cohort['original_source_rows']==192
    assert not receipt['historical_public_availability_verified']
    assert not receipt['original_sensor_signed']

def test_archive_independent_replay_and_no_overwrite(tmp_path):
    root=tmp_path/'data'
    raw,cohort,receipt=capture()
    r.save_one(root,'KSEA',raw,cohort,receipt)
    assert r.verify_one(root,'KSEA')==(receipt,cohort)
    assert (root/'KSEA-original.json').read_bytes()==raw
    with pytest.raises(FileExistsError):r.save_one(root,'KSEA',raw,cohort,receipt)

def test_altered_source_and_cohort_refused(tmp_path):
    root=tmp_path/'data'
    raw,cohort,receipt=capture()
    r.save_one(root,'KSEA',raw,cohort,receipt)
    original=root/'KSEA-original.json'
    original.write_bytes(raw+b' ')
    with pytest.raises(c.Refusal,match='original NOAA bytes'):
        r.verify_one(root,'KSEA')
    original.write_bytes(raw)
    cf=root/'KSEA-cohort.json'
    cf.write_bytes(cf.read_bytes().replace(b'KSEA',b'KMCI'))
    with pytest.raises(c.Refusal,match='cohort changed'):
        r.verify_one(root,'KSEA')

def test_false_publication_signatures_refused(tmp_path):
    raw,cohort,receipt=capture()
    receipt['historical_public_availability_verified']=True
    root=tmp_path/'data'
    with pytest.raises(c.Refusal,match='scientific/production'):
        r.save_one(root,'KSEA',raw,cohort,receipt)

def test_unqualified_content_type_and_204_refused():
    for status,mime in [(204,'application/json'),(200,'text/html')]:
        response=Response(source())
        response.status=status
        response.headers={'Content-Type':mime}
        class Bad:
            def open(self,request,timeout):return response
        with pytest.raises(c.Refusal):
            r.download_one('KSEA',opener=Bad(),clock=lambda:START)

def test_changed_original_station_refused():
    with pytest.raises(c.Refusal,match='station label'):
        r.download_one('KSEA',opener=Opener(source('KDEN')),clock=lambda:START)

def test_inadmissible_400_row_source_refused():
    raw=json.dumps(json.loads(source())*3).encode()
    with pytest.raises(c.Refusal,match='400-row'):
        r.download_one('KSEA',opener=Opener(raw),clock=lambda:START)

def test_redirect_denied_without_switching_origin():
    with pytest.raises(c.Refusal,match='redirect'):
        r.RejectRedirect().redirect_request(None,None,302,'redirect',{},'https://attacker.invalid/')
