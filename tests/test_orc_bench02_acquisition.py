"""BENCH-02-R2 original external source, revision and first-seen custody."""
import json
from copy import deepcopy
import pytest
from tools.orcbench02 import acquisition as a

OBS=1_700_000_000
END=(OBS+500)*1000

def row(**changed):
    r={"icaoId":"KMCI","obsTime":OBS,"receiptTime":"2023-11-14T22:15:00Z",
       "temp":19.5,"rawOb":"METAR KMCI 142213Z 18006KT 10SM CLR 20/05 A3000"}
    r.update(changed)
    return r

def raw(*rows):
    return json.dumps(list(rows),sort_keys=True,separators=(",",":")).encode()

def store(root,original=None,started=END-100,finished=END):
    return a.save_snapshot(root,"KMCI",a.source_url("KMCI"),
        raw(row()) if original is None else original,started,finished,
        "Tue, 14 Nov 2023 22:21:40 GMT","application/json",
        "github-run:987654321:attempt:1")

def test_source_first_seen_not_retroactive_publication(tmp_path):
    root=tmp_path/"capture"
    e=store(root)
    assert e["source_bytes"]>0
    assert e["versions"][0]["first_seen_ms"]==END
    assert e["versions"][0]["awc_receipt_ms"]<END
    assert not e["production_authorized"]
    assert not e["historical_public_availability_verified"]
    assert a.research_asof([e],END-1)==[]
    assert len(a.research_asof([e],END))==1
    assert a.verify_journal(root)==[e]

def test_corrected_and_duplicate_original_versions_preserved(tmp_path):
    root=tmp_path/"data"
    initial=raw(row(temp=None),row(temp=19.5,
         rawOb="METAR KMCI COR 142213Z 18006KT 10SM CLR 20/05 A3000"))
    first=store(root,initial)
    assert first["versions"][0]["temperature_k"] is None
    assert first["versions"][1]["is_revision"]
    later=raw(row(temp=19.5,
        rawOb="METAR KMCI COR 142213Z 18006KT 10SM CLR 20/05 A3000"),
        row(temp=20.0,rawOb="METAR KMCI COR 142213Z 18006KT 10SM CLR 21/05 A3000"))
    second=store(root,later,END+100,END+200)
    assert second["versions"][0]["first_seen_ms"]==END
    assert second["versions"][1]["first_seen_ms"]==END+200
    assert second["versions"][1]["is_revision"]
    assert a.verify_journal(root)==[first,second]
    assert len(a.research_asof([first,second],END))==2
    assert len(a.research_asof([first,second],END+200))==3

def test_provider_reverse_order_not_rewritten(tmp_path):
    e=store(tmp_path/"x",raw(row(obsTime=OBS+60,receiptTime="2023-11-14T22:16:00Z"),
                                row(obsTime=OBS)))
    assert [v["row_index"] for v in e["versions"]]==[0,1]
    assert e["versions"][0]["observed_ms"]>e["versions"][1]["observed_ms"]

@pytest.mark.parametrize("key,value",[
    ("icaoId","KLAX"),("obsTime","2023-11-14"),("obsTime",False),
    ("receiptTime",None),("receiptTime","2001-01-01T00:00:00Z"),
    ("temp","warm"),("temp",float("nan")),("rawOb","METAR KLAX INVALID"),
])
def test_wrong_or_damaged_fields_refuse(key,value):
    with pytest.raises(a.SourceRefusal):
        a.parse_rows(raw(row(**{key:value})),"KMCI",END)

def test_future_server_clock_refuses():
    with pytest.raises(a.SourceRefusal,match="time contradiction"):
        a.parse_rows(raw(row(receiptTime="2023-11-15T22:15:00Z")),"KMCI",END)

def test_wrong_station_or_unsafe_filename_refuses(tmp_path):
    with pytest.raises(a.SourceRefusal):a.source_url("KPHX")
    with pytest.raises(a.SourceRefusal):a.raw_path(tmp_path,"../anything.json")

def test_tampered_original_bytes_detected(tmp_path):
    root=tmp_path/"capture"
    e=store(root)
    p=root/e["raw_filename"]
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(a.SourceRefusal,match="source bytes"):
        a.verify_journal(root)

def test_altered_receipt_digest_detected(tmp_path):
    root=tmp_path/"capture"
    store(root)
    p=root/"receipt-000001.json"
    p.write_bytes(p.read_bytes().replace(b"SYSTEM_CA_HTTPS_NO_REDIRECT",b"HTTP_INSECURE"))
    with pytest.raises(a.SourceRefusal,match="receipt digest"):
        a.verify_journal(root)

def test_orphaned_source_and_missing_receipt_refuse(tmp_path):
    root=tmp_path/"capture"
    store(root)
    (root/"receipt-000001.json").unlink()
    with pytest.raises(a.SourceRefusal,match="unpaired"):
        a.verify_journal(root)

def test_noncontiguous_journal_refuse(tmp_path):
    root=tmp_path/"capture"
    store(root)
    store(root,started=END+100,finished=END+200)
    (root/"receipt-000001.json").rename(root/"receipt-000003.json")
    with pytest.raises(a.SourceRefusal):
        a.verify_journal(root)

def test_no_overwrite_and_replay_refusal(tmp_path):
    root=tmp_path/"capture"
    e=store(root)
    with pytest.raises(FileExistsError):
        a.write_once(root/e["raw_filename"],b"forged")
    with pytest.raises(a.SourceRefusal,match="replayed"):
        store(root,started=END-200,finished=END+200)

def test_forged_first_seen_even_when_rehashed_refused(tmp_path):
    root=tmp_path/"capture"
    e=store(root)
    f=deepcopy(e)
    f["versions"][0]["first_seen_ms"]=END-500
    f["entry_sha256"]=a.hash_json({k:v for k,v in f.items() if k!="entry_sha256"})
    (root/"receipt-000001.json").write_bytes(a.canonical(f))
    with pytest.raises(a.SourceRefusal,match="first-seen"):
        a.verify_journal(root)

def test_oversize_or_more_than_400_rows_refused():
    with pytest.raises(a.SourceRefusal,match="oversized"):
        a.parse_rows(b"X"*(a.MAX_BODY+1),"KMCI",END)
    with pytest.raises(a.SourceRefusal,match="row limit"):
        a.parse_rows(raw(*[row(obsTime=OBS+i) for i in range(401)]),"KMCI",END)

def test_negative_asof_origin_and_forged_publication(tmp_path):
    e=store(tmp_path/"x")
    with pytest.raises(a.SourceRefusal):
        a.research_asof([e],"not-ms")
    f=deepcopy(e); f["production_authorized"]=True
    with pytest.raises(a.SourceRefusal,match="production"):
        a.research_asof([f],END)

def test_bounded_network_request_mock(monkeypatch):
    class Response:
        status=200
        headers={"Content-Type":"application/json","Date":"Tue, 14 Nov 2023 22:21:40 GMT"}
        def read(self,n):
            assert n==a.MAX_BODY+1
            return raw(row())
        def __enter__(self):return self
        def __exit__(self,*e):return False
    class Opener:
        def open(self,request,timeout):
            assert timeout==20 and request.get_method()=="GET"
            assert request.full_url==a.source_url("KMCI")
            return Response()
    out=a.download("KMCI",opener=Opener(),clock=lambda:END)
    assert out["raw"]==raw(row())

def test_non200_or_html_provider_refused():
    class Response:
        def __init__(self,status,ctype):
            self.status=status;self.headers={"Content-Type":ctype}
        def read(self,n):return raw(row())
        def __enter__(self):return self
        def __exit__(self,*e):return False
    class Opener:
        def __init__(self,status,ctype):
            self.status=status;self.ctype=ctype
        def open(self,*args,**kw):return Response(self.status,self.ctype)
    for code,ctype in ((204,"application/json"),(200,"text/html")):
        with pytest.raises(a.SourceRefusal):
            a.download("KMCI",opener=Opener(code,ctype),clock=lambda:END)
