"""C17 typed learned AR checkpoint transport, host-gated training and prediction.

Only a trusted host may explicitly call execute_train(..., host_admitted=True)
after independently verifying user consent and resource scopes. Protobuf bytes
and source strings NEVER confer training rights. No file access or disk loading.
"""
from hashlib import sha256
from .proto import temporal_practical_pb2 as pb
from .temporal_statespace import TemporalSequence,TemporalSample
from .temporal_learned import (
    StateArtifact,train_ridge,forecast,verify_artifact,
)
from .temporal_practical_wire import _read,_write,MAX_INPUT,MAX_OUTPUT


def _history(rows,units,origin,provenance,quality):
    samples=[]
    for row in rows:
        if len(row.values)!=len(row.observed) or len(row.values)!=len(units):
            raise ValueError("invalid learned sequence present/missing masks")
        samples.append(TemporalSample(
            row.time_ms,tuple(v if row.observed[i] else None
                              for i,v in enumerate(row.values)),
            row.source_id,row.observation_id))
    return TemporalSequence(tuple(units),tuple(samples),origin,provenance,quality)


def _pack(a:StateArtifact,dest):
    verify_artifact(a)
    for name in ("schema_version","architecture","source_id","training_sha256",
                 "first_time_ms","last_training_time_ms","step_ms","lags",
                 "training_count","artifact_sha256"):
        setattr(dest,name,getattr(a,name))
    dest.units.extend(a.units)
    for row in a.coefficients:
        dest.coefficients.add(values=row)
    for name in ("intercepts","center","scale","residual_variance",
                 "minimum","maximum"):
        getattr(dest,name).extend(getattr(a,name))


def _unpack(wire):
    a=StateArtifact(
        wire.schema_version,wire.architecture,wire.source_id,
        wire.training_sha256,wire.first_time_ms,
        wire.last_training_time_ms,wire.step_ms,wire.lags,
        tuple(wire.units),
        tuple(tuple(row.values) for row in wire.coefficients),
        tuple(wire.intercepts),tuple(wire.center),tuple(wire.scale),
        tuple(wire.residual_variance),tuple(wire.minimum),
        tuple(wire.maximum),wire.training_count,wire.artifact_sha256,
    )
    return verify_artifact(a)


def execute_train(request:bytes,*,host_admitted:bool=False)->bytes:
    if host_admitted is not True:
        raise PermissionError("Lu host must authorize actual training before dispatch")
    req=_read(request,pb.TrainRequest,MAX_INPUT)
    if req.schema_version!=1:
        raise ValueError("unsupported learned training schema")
    seq=_history(req.samples,req.units,req.origin_id,
                 req.provenance_kind,req.quality_declared)
    artifact=train_ridge(seq,train_count=req.train_count,
                         lags=req.lags,host_admitted=True)
    out=pb.TrainResult(schema_version=1,status="TRAINED",
                       request_sha256=sha256(request).hexdigest(),
                       limitations=[
                           "host_must_verify_permission_beyond_boolean_seam",
                           "train_split_strictly_before_heldout",
                           "sha256_checkpoint_integrity_not_signature",
                           "no_disk_or_Lu_base_model_mutation"])
    _pack(artifact,out.artifact)
    return _write(out)


def verify_train_result(request:bytes,response:bytes):
    req=_read(request,pb.TrainRequest,MAX_INPUT)
    out=_read(response,pb.TrainResult,MAX_OUTPUT)
    if (req.schema_version!=1 or out.schema_version!=1
            or out.status!="TRAINED"
            or out.request_sha256!=sha256(request).hexdigest()
            or not out.HasField("artifact")):
        raise ValueError("invalid learned training result framing")
    art=_unpack(out.artifact)
    # Do not independently train without a new host grant. Checking the
    # checkpoint hash/metadata does not attest the training algorithm ran.
    if (art.source_id!=req.origin_id or art.training_count!=req.train_count
            or art.lags!=req.lags or art.units!=tuple(req.units)):
        raise ValueError("learned training metadata mismatch")
    return out


def execute_forecast(request:bytes)->bytes:
    req=_read(request,pb.ForecastRequest,MAX_INPUT)
    if req.schema_version!=1 or not req.HasField("artifact"):
        raise ValueError("missing typed learned checkpoint")
    a=_unpack(req.artifact)
    history=_history(req.history,a.units,req.origin_id,
                     req.provenance_kind,req.quality_declared)
    result=forecast(a,history,steps=req.steps)
    out=pb.ForecastResult(
        schema_version=1,status=result.status,ood=result.ood,
        steps=result.steps,request_sha256=sha256(request).hexdigest(),
        limitations=result.limitations)
    for row in result.means:out.means.add(values=row)
    for row in result.variances:out.variances.add(values=row)
    return _write(out)


def verify_forecast(request:bytes,response:bytes):
    expected=_read(execute_forecast(request),pb.ForecastResult,MAX_OUTPUT)
    out=_read(response,pb.ForecastResult,MAX_OUTPUT)
    if out!=expected:
        raise ValueError("learned model output differs from source checkpoint replay")
    return out
