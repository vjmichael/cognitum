"""Compare checked-in Protobuf binding descriptors with compiler-produced .proto.

Usage: python tools/check_proto_descriptors.py compiled_cognitum.pb
Run protoc first: python -m grpc_tools.protoc -Iproto
  --descriptor_set_out=compiled_cognitum.pb proto/cognitum/v1/capability.proto

Compiler output may add synthetic JSON-name metadata; compare wire-shape
semantics, field numbers, presence, and oneofs without comparing raw hashes.
"""
from pathlib import Path
import sys

from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from cognitum.proto import capability_pb2, ce_handoff_pb2, worker_pb2, supervisor_acceptance_pb2

EXPECTED = {
    "cognitum/v1/capability.proto": capability_pb2.DESCRIPTOR,
    "cognitum/v1/ce_handoff.proto": ce_handoff_pb2.DESCRIPTOR,
    "cognitum/worker/v1/worker.proto": worker_pb2.DESCRIPTOR,
    "cognitum/security/v1/supervisor_acceptance.proto": supervisor_acceptance_pb2.DESCRIPTOR,
}


def normalized_field(field):
    return (
        field.name, field.number, field.type, field.label, field.type_name,
        field.proto3_optional,
        field.oneof_index if field.HasField("oneof_index") else None,
    )


def normalized_file(descriptor):
    return {
        "name": descriptor.name,
        "package": descriptor.package,
        "syntax": descriptor.syntax,
        "enums": {e.name: tuple((v.name, v.number) for v in e.value) for e in descriptor.enum_type},
        "messages": {
            msg.name: {
                "fields": tuple(normalized_field(f) for f in msg.field),
                "oneofs": tuple(o.name for o in msg.oneof_decl),
                "reserved_ranges": tuple((r.start, r.end) for r in msg.reserved_range),
            }
            for msg in descriptor.message_type
        },
    }


def main(filename):
    produced = FileDescriptorSet()
    produced.ParseFromString(Path(filename).read_bytes())
    if len(produced.file) != 1:
        raise SystemExit("expected one compiled .proto source")
    file_name = produced.file[0].name
    if file_name not in EXPECTED:
        raise SystemExit("unexpected compiled protobuf schema name")
    shipped = FileDescriptorProto.FromString(EXPECTED[file_name].serialized_pb)
    if normalized_file(produced.file[0]) != normalized_file(shipped):
        raise SystemExit("checked-in protobuf bindings differ from compiler .proto wire schema")
    print("Protobuf source/binding schema matches: package, names, fields, oneofs, optional presence")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_proto_descriptors.py compiled_cognitum.pb")
    main(sys.argv[1])
