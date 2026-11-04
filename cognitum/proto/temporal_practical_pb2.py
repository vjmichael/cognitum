"""Descriptor-backed C17 native temporal Protobuf classes; protoc CI parity."""
from google.protobuf import descriptor_pb2 as d,descriptor_pool,message_factory
f=d.FileDescriptorProto()
f.name="cognitum/temporal/v1/practical.proto"
f.package="cognitum.temporal_practical.v1"
f.syntax="proto3"
T=d.FieldDescriptorProto
def field(name,kind,rep=False,ref=None):
    return (name,kind,rep,ref)
def msg(name,fields):
    entry=f.message_type.add();entry.name=name
    for index,(key,kind,repeated,ref) in enumerate(fields,1):
        obj=entry.field.add();obj.name=key;obj.number=index
        obj.type=getattr(T,"TYPE_"+kind.upper())
        obj.label=T.LABEL_REPEATED if repeated else T.LABEL_OPTIONAL
        if ref:obj.type_name="."+f.package+"."+ref
msg("Sample",[
    field("time_ms","uint64"),field("values","double",True),
    field("observed","bool",True),field("source_id","string"),
    field("observation_id","string")])
msg("FilterRequest",[
    field("schema_version","uint32"),field("units","string",True),
    field("samples","message",True,"Sample"),field("origin_id","string"),
    field("provenance_kind","string"),field("quality_declared","string"),
    field("kind","string"),field("process_variance_per_second","double"),
    field("measurement_variance","double"),field("prior_variance","double"),
    field("innovation_gate_sigma","double"),field("max_forecast_ms","uint32"),
    field("forecast_time_ms","uint64")])
msg("FilterPoint",[
    field("time_ms","uint64"),field("mean","double",True),
    field("variance","double",True),field("normalized_innovation","double",True),
    field("has_innovation","bool",True),field("missing","bool",True),
    field("anomalies","bool",True)])
msg("FilterResult",[
    field("schema_version","uint32"),field("status","string"),
    field("points","message",True,"FilterPoint"),field("forecast_mean","double",True),
    field("forecast_variance","double",True),field("forecast_time_ms","uint64"),
    field("observed_count","uint32"),field("missing_count","uint32"),
    field("anomalies_count","uint32"),field("ood","bool"),
    field("limitations","string",True),field("request_sha256","string")])
msg("HMMObservation",[
    field("time_ms","uint64"),field("category","uint32"),
    field("observed","bool"),field("source_id","string"),
    field("observation_id","string")])
msg("HMMRequest",[
    field("schema_version","uint32"),field("state_names","string",True),
    field("prior","double",True),
    field("transition_rows","message",True,"DoubleVector"),
    field("emission_rows","message",True,"DoubleVector"),
    field("sampling_interval_ms","uint32"),field("model_source","string"),
    field("observations","message",True,"HMMObservation"),
    field("alert_probability","double")])
msg("DoubleVector",[field("values","double",True)])
msg("HMMResult",[
    field("schema_version","uint32"),field("status","string"),
    field("posterior_rows","message",True,"DoubleVector"),
    field("probable_states","string",True),
    field("change_alerts","bool",True),
    field("total_log_likelihood","double"),
    field("limitations","string",True),field("request_sha256","string")])
pool=descriptor_pool.DescriptorPool()
DESCRIPTOR=pool.Add(f)
for name in ("Sample","FilterRequest","FilterPoint","FilterResult",
             "HMMObservation","HMMRequest","DoubleVector","HMMResult"):
    globals()[name]=message_factory.GetMessageClass(
        pool.FindMessageTypeByName(f.package+"."+name))
