"""C07 descriptor-backed generated-equivalent bindings. Source parity is protoc-gated."""
from google.protobuf import descriptor_pb2 as d
from google.protobuf import descriptor_pool as pool
from google.protobuf.internal import builder
fd = d.FileDescriptorProto()
fd.name = "cognitum/state/v1/events.proto"
fd.package = "cognitum.state.v1"
fd.syntax = "proto3"
S, U, L, I, M, E = (d.FieldDescriptorProto.TYPE_STRING,
                     d.FieldDescriptorProto.TYPE_UINT32,
                     d.FieldDescriptorProto.TYPE_UINT64,
                     d.FieldDescriptorProto.TYPE_INT64,
                     d.FieldDescriptorProto.TYPE_MESSAGE,
                     d.FieldDescriptorProto.TYPE_ENUM)
B = d.FieldDescriptorProto.TYPE_BOOL
def enum(name, choices):
    node = fd.enum_type.add()
    node.name = name
    for n,v in choices:
        item = node.value.add(); item.name=n; item.number=v
def msg(name, fields):
    node = fd.message_type.add(); node.name = name
    for i,(name,typ,target,repeated) in enumerate(fields,1):
        f=node.field.add(); f.name=name; f.number=i; f.type=typ
        f.label=(d.FieldDescriptorProto.LABEL_REPEATED if repeated else d.FieldDescriptorProto.LABEL_OPTIONAL)
        if target: f.type_name = '.cognitum.state.v1.' + target

enum('ValueKind', [('VALUE_KIND_UNSPECIFIED',0),('TEXT',1),('INTEGER',2),('DECIMAL',3),('BOOLEAN',4)])
enum('ClaimOrigin',[('CLAIM_ORIGIN_UNSPECIFIED',0),('USER_VERIFIED',1),('HOST_OBSERVED',2),('IMPORT_OBSERVED',3),('MODEL_HYPOTHESIS',4)])
enum('ClaimAction',[('CLAIM_ACTION_UNSPECIFIED',0),('ASSERT',1),('CONFIRM',2),('CHALLENGE',3),('SUPERSEDE',4),('RETRACT',5),('EXPIRE',6),('TEMPORAL_CORRECT',7)])
enum('ClaimStatus',[('CLAIM_STATUS_UNSPECIFIED',0),('ACTIVE',1),('DISPUTED',2),('RETRACTED',3),('EXPIRED',4)])
enum('UncertaintyKind',[('UNCERTAINTY_UNSPECIFIED',0),('EXPLICITLY_UNCERTAIN',1),('CONDITIONAL',2),('OPEN_QUESTION',3)])
msg('SourceEvidence',[(n,S,None,False) for n in ('session_id','root_entry_id','revision_entry_id','content_sha256','snapshot_id')])
msg('StateEvent',[
 ('schema_version',U,None,False),('event_id',S,None,False),('scope_id',S,None,False),
 ('claim_id',S,None,False),('subject_id',S,None,False),('predicate',S,None,False),
 ('value_kind',E,'ValueKind',False),('value_text',S,None,False),
 ('origin',E,'ClaimOrigin',False),('action',E,'ClaimAction',False),
 ('expected_revision',L,None,False),('recorded_at_ms',I,None,False),('effective_at_ms',I,None,False),
 ('source',M,'SourceEvidence',False),('corrects_event_id',S,None,False),
 ('valid_until_ms',I,None,False),('uncertainty_kind',E,'UncertaintyKind',False),('uncertainty_note',S,None,False)
])
msg('ClaimView',[
 ('scope_id',S,None,False),('claim_id',S,None,False),('subject_id',S,None,False),
 ('predicate',S,None,False),('value_kind',E,'ValueKind',False),('value_text',S,None,False),
 ('origin',E,'ClaimOrigin',False),('status',E,'ClaimStatus',False),('revision',L,None,False),
 ('latest_event_id',S,None,False),('source',M,'SourceEvidence',False),
 ('effective_at_ms',I,None,False),('valid_until_ms',I,None,False),
 ('uncertainty_kind',E,'UncertaintyKind',False),('uncertainty_note',S,None,False)
])
msg('ConflictEdge',[(n,S,None,False) for n in ('first_claim_id','second_claim_id','predicate','subject_id')])
msg('StateProjection',[
 ('schema_version',U,None,False),('scope_id',S,None,False),
 ('claims',M,'ClaimView',True),('conflicts',M,'ConflictEdge',True)
])
msg('AsOfQuery',[
 ('schema_version',U,None,False),('scope_id',S,None,False),('valid_at_ms',I,None,False),
 ('known_at_ms',I,None,False),('include_inactive',B,None,False)
])
msg('HistoricalProjection',[
 ('schema_version',U,None,False),('scope_id',S,None,False),('valid_at_ms',I,None,False),
 ('known_at_ms',I,None,False),('claims',M,'ClaimView',True),
 ('conflicts',M,'ConflictEdge',True),('historical_only',B,None,False)
])
DESCRIPTOR = pool.Default().AddSerializedFile(fd.SerializeToString())
builder.BuildMessageAndEnumDescriptors(DESCRIPTOR,globals())
builder.BuildTopDescriptorsAndMessages(DESCRIPTOR,'cognitum.proto.state_pb2',globals())
