"""C17 native canonical Protobuf temporal Kalman and HMM specialists.

Strict input bounds; exact request hash only correlates, never authorizes.
Output verification recomputes values from the original typed request.
"""
from hashlib import sha256
from math import isfinite
from google.protobuf.message import DecodeError
from .proto import temporal_practical_pb2 as pb
from .temporal_statespace import (
    TemporalSample,TemporalSequence,TemporalModel,filter_sequence,validate,
)
from .temporal_hidden import (
    HiddenStateModel,HiddenObservation,infer_hidden,validate_hmm,
)

MAX_INPUT=200000
MAX_OUTPUT=500000


def _read(frame,cls,maximum):
    if type(frame) is not bytes or not 0<len(frame)<=maximum:
        raise ValueError("invalid temporal wire size")
    obj=cls()
    try:obj.ParseFromString(frame)
    except DecodeError as exc:raise ValueError("malformed temporal protobuf") from exc
    clone=cls();clone.CopyFrom(obj);clone.DiscardUnknownFields()
    if clone!=obj or obj.SerializeToString(deterministic=True)!=frame:
        raise ValueError("unknown or noncanonical temporal protobuf")
    return obj


def _write(obj):
    payload=obj.SerializeToString(deterministic=True)
    if not 0<len(payload)<=MAX_OUTPUT:
        raise ValueError("oversized temporal response")
    return payload


def _sequence(req):
    if req.schema_version!=1:
        raise ValueError("unsupported temporal schema")
    seq=TemporalSequence(tuple(req.units),tuple(
        TemporalSample(item.time_ms,tuple(
            value if item.observed[j] else None
            for j,value in enumerate(item.values)),item.source_id,
            item.observation_id)
        for item in req.samples if len(item.values)==len(item.observed)),
        req.origin_id,req.provenance_kind,req.quality_declared)
    if len(seq.samples)!=len(req.samples):
        raise ValueError("missingness bitmask dimension mismatch")
    model=TemporalModel(
        req.kind,req.process_variance_per_second,
        req.measurement_variance,req.prior_variance,
        req.innovation_gate_sigma,req.max_forecast_ms)
    validate(seq,model)
    return seq,model


def _hidden(req):
    if req.schema_version!=1:
        raise ValueError("unsupported HMM schema")
    model=HiddenStateModel(
        tuple(req.state_names),tuple(req.prior),
        tuple(tuple(row.values) for row in req.transition_rows),
        tuple(tuple(row.values) for row in req.emission_rows),
        req.sampling_interval_ms,req.model_source)
    obs=tuple(HiddenObservation(row.time_ms,
            row.category if row.observed else None,
            row.source_id,row.observation_id) for row in req.observations)
    validate_hmm(model,obs)
    return model,obs


def execute(kind:str,request:bytes):
    if kind=="kalman":
        req=_read(request,pb.FilterRequest,MAX_INPUT)
        seq,model=_sequence(req)
        out=filter_sequence(seq,model,forecast_time_ms=req.forecast_time_ms)
        result=pb.FilterResult(schema_version=1,status=out.status,
                    forecast_time_ms=out.forecast_time_ms or 0,
                    observed_count=out.observed_count,missing_count=out.missing_count,
                    anomalies_count=out.anomalies_count,ood=out.ood,
                    limitations=out.limitations,
                    request_sha256=sha256(request).hexdigest())
        for p in out.points:
            point=result.points.add(time_ms=p.time_ms,mean=p.posterior_mean,
                                    variance=p.posterior_variance,missing=p.missing,
                                    anomalies=p.anomalies)
            point.normalized_innovation.extend(float(v) if v is not None else 0.
                                               for v in p.normalized_innovation)
            point.has_innovation.extend(v is not None for v in p.normalized_innovation)
        result.forecast_mean.extend(out.forecast_mean)
        result.forecast_variance.extend(out.forecast_variance)
        return _write(result)
    if kind=="hmm":
        req=_read(request,pb.HMMRequest,MAX_INPUT)
        model,obs=_hidden(req)
        out=infer_hidden(model,obs,alert_probability=req.alert_probability)
        result=pb.HMMResult(schema_version=1,status=out.status,
                            total_log_likelihood=out.total_log_likelihood or 0.,
                            probable_states=out.probable_states,
                            change_alerts=out.change_alerts,
                            limitations=out.limitations,
                            request_sha256=sha256(request).hexdigest())
        for row in out.posteriors:
            result.posterior_rows.add(values=row)
        return _write(result)
    raise ValueError("unsupported temporal specialist")


def verify(kind:str,request:bytes,response:bytes):
    cls={"kalman":pb.FilterResult,"hmm":pb.HMMResult}.get(kind)
    if cls is None:
        raise ValueError("unsupported temporal specialist")
    result=_read(response,cls,MAX_OUTPUT)
    expected=_read(execute(kind,request),cls,MAX_OUTPUT)
    if (result.schema_version!=1
            or result.request_sha256!=sha256(request).hexdigest()
            or result.status!=expected.status
            or result!=expected):
        raise ValueError("temporal result differs from independently recomputed data")
    return result
