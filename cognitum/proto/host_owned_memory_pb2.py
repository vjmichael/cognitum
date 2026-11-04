"""C06/C07 checked-in descriptor-backed Lu-owned ANSF wire types."""
from google.protobuf import descriptor_pb2 as d,descriptor_pool,message_factory
f=d.FileDescriptorProto();f.name="cognitum/memory/v1/host_owned.proto"
f.package="cognitum.memory.v1";f.syntax="proto3"
T=d.FieldDescriptorProto
def fld(n,t,rep=False,ref=None):return n,t,rep,ref
def msg(name,fields):
    m=f.message_type.add();m.name=name
    for i,(name,kind,repeated,ref) in enumerate(fields,1):
        x=m.field.add();x.name=name;x.number=i
        x.type=getattr(T,"TYPE_"+kind.upper())
        x.label=T.LABEL_REPEATED if repeated else T.LABEL_OPTIONAL
        if ref:x.type_name="."+f.package+"."+ref
msg("Evidence",[
 fld("source_id","string"),fld("source_revision","uint64"),fld("scope_id","string"),
 fld("subject","string"),fld("text","string"),fld("citation_handle","string"),
 fld("valid_from_ms","uint64"),fld("has_valid_to","bool"),
 fld("valid_to_ms","uint64"),fld("tombstoned","bool")])
msg("Snapshot",[fld("schema_version","uint32"),fld("owner","string"),
 fld("snapshot_id","string"),fld("owner_revision","uint64"),
 fld("rows","message",True,"Evidence")])
msg("Query",[fld("schema_version","uint32"),fld("snapshot","message",False,"Snapshot"),
 fld("host_authorized_scope","string"),fld("scope_id","string"),
 fld("query_text","string"),fld("expected_snapshot_id","string"),
 fld("expected_owner_revision","uint64"),fld("max_results","uint32"),
 fld("has_as_of","bool"),fld("as_of_ms","uint64"),fld("subject","string"),
 fld("exact_lookup","bool"),fld("exact_source_id","string")])
msg("Hit",[fld("source_id","string"),fld("source_revision","uint64"),
 fld("subject","string"),fld("citation_handle","string"),fld("text","string"),
 fld("score","double"),fld("snapshot_id","string")])
msg("QueryResult",[fld("schema_version","uint32"),fld("status","string"),
 fld("hits","message",True,"Hit"),fld("request_sha256","string"),
 fld("limitations","string",True)])
msg("StateEvent",[
 fld("event_id","string"),fld("scope_id","string"),fld("entity","string"),
 fld("predicate","string"),fld("value_type","string"),fld("value","string"),
 fld("origin_source_id","string"),fld("actor_authority","string"),
 fld("expected_revision","uint64"),fld("effective_ms","uint64"),
 fld("recorded_ms","uint64"),fld("action","string"),
 fld("replaces_event_id","string"),fld("reason","string")])
msg("EventSnapshot",[fld("schema_version","uint32"),fld("owner","string"),
 fld("snapshot_id","string"),fld("owner_revision","uint64"),
 fld("scope_id","string"),fld("events","message",True,"StateEvent")])
msg("Belief",[fld("entity","string"),fld("predicate","string"),
 fld("value_type","string"),fld("value","string"),fld("status","string"),
 fld("source_event_id","string"),fld("source_revision","uint64"),
 fld("authority","string"),fld("effective_ms","uint64"),
 fld("conflict_event_ids","string",True)])
msg("ProposalRequest",[fld("schema_version","uint32"),
 fld("snapshot","message",False,"EventSnapshot"),
 fld("event","message",False,"StateEvent"),
 fld("host_authorized_scope","string")])
msg("ProposalResult",[fld("schema_version","uint32"),fld("status","string"),
 fld("scope_id","string"),fld("based_on_snapshot_id","string"),
 fld("expected_owner_revision","uint64"),
 fld("current","message",True,"Belief"),
 fld("competing","message",True,"Belief"),
 fld("event_sha256","string"),fld("request_sha256","string"),
 fld("limitations","string",True)])
pool=descriptor_pool.DescriptorPool();DESCRIPTOR=pool.Add(f)
for name in ("Evidence","Snapshot","Query","Hit","QueryResult","StateEvent",
             "EventSnapshot","Belief","ProposalRequest","ProposalResult"):
    globals()[name]=message_factory.GetMessageClass(
        pool.FindMessageTypeByName(f.package+"."+name))
