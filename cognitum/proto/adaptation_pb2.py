"""C18 descriptor-backed Protobuf bindings, independently compiler checked."""
from google.protobuf import descriptor_pb2 as d,descriptor_pool,message_factory
f=d.FileDescriptorProto()
f.name="cognitum/adaptation/v1/adaptation.proto"
f.package="cognitum.adaptation.v1";f.syntax="proto3"
T=d.FieldDescriptorProto
def fld(n,t,rep=False,ref=None):return n,t,rep,ref
def msg(n,fields):
    m=f.message_type.add();m.name=n
    for i,(name,kind,many,ref) in enumerate(fields,1):
        field=m.field.add();field.name=name;field.number=i
        field.type=getattr(T,"TYPE_"+kind.upper())
        field.label=T.LABEL_REPEATED if many else T.LABEL_OPTIONAL
        if ref:field.type_name="."+f.package+"."+ref
msg("Trace",[fld("event_id","string"),fld("occurred_ms","uint64"),
    fld("features","double",True),fld("expected_route","string"),
    fld("source_digest","string"),fld("consent_receipt","string"),
    fld("retention_until_ms","uint64"),fld("privacy_class","string"),
    fld("task_family","string")])
msg("Proposal",[fld("proposal_id","string"),fld("workspace_id","string"),
    fld("target","string"),fld("policy_version","uint32"),
    fld("source_digest","string"),fld("consent_receipt","string"),
    fld("privacy_class","string"),fld("allowed_families","string",True),
    fld("retention_until_ms","uint64"),fld("train_before_ms","uint64"),
    fld("holdout_from_ms","uint64"),fld("base_policy_digest","string"),
    fld("maximum_training_rows","uint32"),fld("maximum_cpu_ms","uint32"),
    fld("rollback_policy_digest","string")])
msg("Vector",[fld("values","double",True)])
msg("Policy",[fld("policy_version","uint32"),fld("workspace_id","string"),
    fld("target","string"),fld("allowed_families","string",True),
    fld("feature_count","uint32"),fld("coefficients","message",True,"Vector"),
    fld("intercepts","double",True),fld("center","double",True),
    fld("scale","double",True),fld("training_digest","string"),
    fld("proposal_id","string"),fld("base_policy_digest","string"),
    fld("status","string"),fld("digest","string")])
msg("Evaluation",[fld("status","string"),fld("count","uint32"),
    fld("accuracy","double"),fld("log_loss","double"),
    fld("worst_family_accuracy","double"),fld("abstention_rate","double"),
    fld("elapsed_ms","double")])
msg("EvaluateRequest",[fld("schema_version","uint32"),
    fld("proposal","message",False,"Proposal"),
    fld("candidate","message",False,"Policy"),
    fld("incumbent","message",False,"Policy"),
    fld("holdout","message",True,"Trace")])
msg("EvaluateResult",[fld("schema_version","uint32"),fld("status","string"),
    fld("candidate_metrics","message",False,"Evaluation"),
    fld("incumbent_metrics","message",False,"Evaluation"),
    fld("candidate_digest","string"),fld("incumbent_digest","string"),
    fld("holdout_digest","string"),fld("reasons","string",True),
    fld("request_sha256","string"),fld("limitations","string",True)])
pool=descriptor_pool.DescriptorPool()
DESCRIPTOR=pool.Add(f)
for name in ("Trace","Proposal","Vector","Policy","Evaluation","EvaluateRequest","EvaluateResult"):
    globals()[name]=message_factory.GetMessageClass(pool.FindMessageTypeByName(f.package+"."+name))
