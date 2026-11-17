"""Real-package positive tests and adapter fail-closed controls.

Combined CPU regression can run without the optional wheel. The dedicated
grouped native matrix sets C15_REQUIRE_BYTETRACK=1: unavailability is failure.
"""
from dataclasses import replace
import os
from unittest.mock import patch
import pytest
from cognitum.contracts import HostContext
from cognitum.spatial_tracking import Detection,MAX_TRACKS
from cognitum.spatial_bytetrack import (Scope,Frame,execute,MAX_FRAMES,MAX_MISSED,
                                        MAX_MS,CONFIG,VERSION,_engine,_Stop)
BUILD="a"*40
CTX=HostContext("workspace","owner")
SCOPE=Scope("workspace","owner","camera_a",BUILD)

def frame(n,boxes=((10.,10.,20.,30.,.95),)):
    return Frame(n,"camera","r1","b"*64,
          tuple(Detection("det_"+str(n)+"_"+str(i),x,y,w,h,"camera")
                for i,(x,y,w,h,s) in enumerate(boxes)),
          tuple(s for *_,s in boxes))

def run(frames,**kwargs):
    return execute(kwargs.pop("scope",SCOPE),frames,kwargs.pop("context",CTX),
                   expected_build_sha=kwargs.pop("build",BUILD),
                   admit=kwargs.pop("admit",lambda a,c:True),
                   source_current=kwargs.pop("source_current",lambda f,c:True),
                   cancelled=kwargs.pop("cancelled",lambda:False),**kwargs)

@pytest.fixture
def real_backend():
    try: _engine()
    except _Stop as e:
        if os.environ.get("C15_REQUIRE_BYTETRACK")=="1":
            pytest.fail("reviewed actual ByteTrack unavailable: "+e.status)
        pytest.skip("optional reviewed ByteTrack wheel not installed")
    return True

def test_invalid_inputs_and_scope_rejected_before_import():
    f=frame(1)
    bad=((),(frame(2),),(f,f),(replace(f,confidence=()),),
         (replace(f,confidence=(float("nan"),)),),(replace(f,confidence=(1.1,)),),
         (replace(f,confidence=(True,)),),(replace(f,source_sha256="wrong"),),
         (replace(f,detections=(replace(f.detections[0],width=0),)),),
         (replace(f,detections=(f.detections[0],f.detections[0]),confidence=(.7,.8)),),
         tuple(frame(i) for i in range(1,MAX_FRAMES+2)))
    with patch("cognitum.spatial_bytetrack._engine") as engine:
        for fs in bad:assert run(fs).status=="INVALID_INPUT"
        assert run((f,),context=HostContext("other","owner")).status=="DENIED"
        assert run((f,),build="c"*40).status=="DENIED"
        assert run((f,),admit=lambda a,c:1).status=="DENIED"
        assert run((f,),timeout_ms=MAX_MS+1).status=="INVALID_INPUT"
        assert run((f,),cancelled=lambda:True).status=="CANCELLED"
        assert run((f,),source_current=lambda f,c:False).status=="STALE_SOURCE"
        engine.assert_not_called()

def test_missing_backend_and_deadline_have_no_outputs():
    with patch("cognitum.spatial_bytetrack._engine",side_effect=_Stop("UNSUPPORTED")):
        out=run((frame(1),))
        assert out.status=="UNSUPPORTED" and not out.frame_results and out.seal is None
    with patch("cognitum.spatial_bytetrack.monotonic",side_effect=[1.,2.]):
        out=run((frame(1),),timeout_ms=1)
        assert out.status=="TIMED_OUT" and not out.frame_results

def test_real_low_confidence_recovery_and_lifecycle(real_backend):
    fs=(frame(1),frame(2),frame(3,((10.,10.,20.,30.,.15),(400.,400.,20.,30.,.2))),
        frame(4,()),frame(5))
    out=run(fs)
    assert out.status=="COMPLETED",out
    a,b,c,d,e=out.frame_results
    assert not a.update.assignments and a.update.unmatched_detections==("det_1_0",)
    sid=b.new_ids[0]
    assert b.update.assignments==((sid,"det_2_0"),)
    assert c.update.assignments==((sid,"det_3_0"),)
    assert c.update.unmatched_detections==("det_3_1",)
    assert not d.update.assignments and d.update.tracks[0].missed==1
    assert d.update.tracks[0].stable_id==sid and e.update.assignments==((sid,"det_5_0"),)
    assert e.update.tracks[0].missed==0
    # Retire the confirmed identity, and never allocate that stable ID again.
    fs+=tuple(frame(i,()) for i in range(6,6+MAX_MISSED+2))
    end=len(fs);fs+=(frame(end+1),frame(end+2))
    second=run(fs,resume=out.seal)
    assert second.status=="COMPLETED",second
    assert second.frame_results[:len(out.frame_results)]==out.frame_results
    assert any(sid in x.update.retired_ids for x in second.frame_results)
    assert second.frame_results[-1].new_ids and sid not in second.frame_results[-1].new_ids

def test_replay_identity_source_and_namespace_binding(real_backend):
    fs=(frame(1),frame(2))
    a=run(fs);b=run(fs)
    assert a.status==b.status=="COMPLETED" and a.seal==b.seal and a.frame_results==b.frame_results
    assert run(fs,resume=replace(a.seal,receipt_sha256="0"*64)).status=="REPLAY_MISMATCH"
    changed=(replace(fs[0],source_revision="r2"),fs[1])
    assert run(changed,resume=a.seal).status=="REPLAY_MISMATCH"
    other=run(fs,scope=replace(SCOPE,sequence_id="camera_b"))
    assert other.status=="COMPLETED" and other.frame_results[-1].new_ids!=a.frame_results[-1].new_ids
    assert run(fs,scope=replace(SCOPE,sequence_id="camera_b"),resume=a.seal).status=="INVALID_INPUT"

def test_revocation_staleness_and_cancel_discard_results(real_backend):
    fs=(frame(1),frame(2),frame(3))
    out=run(fs,admit=lambda a,c:not (a.phase=="associate" and a.frame_number==3))
    assert out.status=="DENIED" and not out.frame_results
    stale={"on":False}
    def admit(a,c):
        if a.phase=="publish":stale["on"]=True
        return True
    out=run(fs,admit=admit,source_current=lambda f,c:not stale["on"])
    assert out.status=="STALE_SOURCE" and not out.frame_results
    out=run(fs,admit=admit,cancelled=lambda:stale["on"] is True)
    assert out.status=="CANCELLED" and not out.frame_results

def test_actual_backend_one_to_one_and_capacity(real_backend):
    fs=(frame(1,tuple((40.*i,10.,20.,30.,.95) for i in range(MAX_TRACKS))),
        frame(2,tuple((40.*i,10.,20.,30.,.95) for i in range(MAX_TRACKS))))
    out=run(fs)
    assert out.status=="COMPLETED"
    assert len(out.frame_results[-1].update.assignments)==MAX_TRACKS
    more=frame(3,tuple((40.*i,10000.,20.,30.,.95) for i in range(MAX_TRACKS)))
    out=run(fs+(more,))
    assert out.status=="RESOURCE_LIMIT" and not out.frame_results
    # Same package version but altered implementation must be rejected.
    with patch("cognitum.spatial_bytetrack.BLOBS",{"core/bytetrack/tracker.py":"0"*40}):
        assert run((frame(1),)).status=="UNSUPPORTED"

def test_forged_library_source_row_fails_closed(real_backend):
    np,sv,engine,identity=_engine()
    original=engine.update
    def corrupt(inp):
        out=original(inp)
        if len(out):out.xyxy[0,0]+=1
        return out
    with patch.object(engine,"update",side_effect=corrupt):
        with patch("cognitum.spatial_bytetrack._engine",return_value=(np,sv,engine,identity)):
            out=run((frame(1),frame(2)))
            assert out.status=="VERIFICATION_FAILED" and not out.frame_results

def test_configuration_immutable():
    with pytest.raises(TypeError):CONFIG["lost_track_buffer"]=999
