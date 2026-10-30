"""Compare C17 source .proto compiled independently with the checked-in binding."""
from __future__ import annotations
import argparse
from pathlib import Path
from google.protobuf import descriptor_pb2
from cognitum.proto import temporal_filter_pb2 as generated


def check(descriptor_set: bytes):
    observed = descriptor_pb2.FileDescriptorSet.FromString(descriptor_set)
    if len(observed.file) != 1:
        raise ValueError("EXPECTED_ONE_PROTO_FILE")
    expected = descriptor_pb2.FileDescriptorProto.FromString(generated.DESCRIPTOR.serialized_pb)
    actual = observed.file[0]
    if (actual.name, actual.package, actual.syntax) != (expected.name, expected.package, expected.syntax):
        raise ValueError("FILE_IDENTITY_MISMATCH")
    if len(actual.message_type) != len(expected.message_type):
        raise ValueError("MESSAGE_COUNT_MISMATCH")
    for message, reference in zip(actual.message_type, expected.message_type):
        if message.name != reference.name or len(message.field) != len(reference.field):
            raise ValueError("MESSAGE_SHAPE_MISMATCH")
        if [x.name for x in message.oneof_decl] != [x.name for x in reference.oneof_decl]:
            raise ValueError("OPTIONAL_PRESENCE_MISMATCH")
        for field, expected_field in zip(message.field, reference.field):
            properties = lambda f:(f.name,f.number,f.type,f.label,f.type_name,f.proto3_optional,f.oneof_index)
            if properties(field) != properties(expected_field):
                raise ValueError("FIELD_CONTRACT_MISMATCH")
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("compiled_descriptor_set",type=Path)
    args=parser.parse_args()
    check(args.compiled_descriptor_set.read_bytes())
    print("C17_PROTO_SOURCE_BINDING_PARITY_PASS")


if __name__ == "__main__":
    main()
