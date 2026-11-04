"""C13 checked-in descriptor-backed Protobuf classes.

Source of truth: proto/cognitum/probability/v1/probability.proto.
Compiler descriptor parity is checked in dedicated native CI.
"""
from google.protobuf import descriptor_pb2 as d,descriptor_pool,message_factory
f=d.FileDescriptorProto()
f.name="cognitum/probability/v1/probability.proto"
f.package="cognitum.probability.v1"
f.syntax="proto3"
T=d.FieldDescriptorProto
def field(name,kind,rep=False,ref=None):
    return name,kind,rep,ref
def msg(name,fields):
    node=f.message_type.add();node.name=name
    for number,(name,typ,rep,ref) in enumerate(fields,1):
        x=node.field.add();x.name=name;x.number=number
        x.type=getattr(T,"TYPE_"+typ.upper())
        x.label=T.LABEL_REPEATED if rep else T.LABEL_OPTIONAL
        if ref:x.type_name="."+f.package+"."+ref
msg("Evidence",[field("name","string"),
                field("likelihood_by_hypothesis","double",True),
                field("observed","bool")])
msg("BayesRequest",[field("schema_version","uint32"),
                    field("hypotheses","string",True),field("prior","double",True),
                    field("observations","message",True,"Evidence"),
                    field("prior_source","string"),
                    field("likelihood_source","string"),
                    field("assumptions","string",True)])
msg("BayesResult",[field("schema_version","uint32"),field("status","string"),
                   field("posterior","double",True),
                   field("evidence_probability","double"),
                   field("log_evidence","double"),field("method","string"),
                   field("limitations","string",True),field("request_sha256","string")])
msg("BetaRequest",[field("schema_version","uint32"),field("successes","uint32"),
                   field("failures","uint32"),field("alpha_prior","double"),
                   field("beta_prior","double"),field("credibility","double"),
                   field("prior_source","string"),field("data_source","string")])
msg("BetaResult",[field("schema_version","uint32"),field("status","string"),
                  field("posterior_mean","double"),field("credible_lower","double"),
                  field("credible_upper","double"),field("alpha_posterior","double"),
                  field("beta_posterior","double"),field("limitations","string",True),
                  field("request_sha256","string")])
msg("CalibrationRequest",[field("schema_version","uint32"),
                          field("probabilities","double",True),
                          field("labels","uint32",True),field("source","string"),
                          field("bins","uint32")])
msg("CalibrationResult",[field("schema_version","uint32"),field("status","string"),
                         field("brier","double"),field("log_loss","double"),
                         field("expected_calibration_error","double"),
                         field("count","uint32"),field("bins_with_data","uint32"),
                         field("limitations","string",True),field("request_sha256","string")])
p=descriptor_pool.DescriptorPool()
DESCRIPTOR=p.Add(f)
for name in ("Evidence","BayesRequest","BayesResult",
             "BetaRequest","BetaResult","CalibrationRequest","CalibrationResult"):
    globals()[name]=message_factory.GetMessageClass(p.FindMessageTypeByName(f.package+"."+name))
