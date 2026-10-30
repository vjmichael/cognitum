"""Offline source-to-descriptor field parity sanity check, not protoc CI."""
from pathlib import Path
import re
import unittest

from google.protobuf.descriptor import FieldDescriptor
from cognitum.proto import memory_pb2 as pb

PROTO = Path(__file__).resolve().parents[1] / "proto/cognitum/memory/v1/evidence.proto"


class MemorySchemaParityTest(unittest.TestCase):
    def test_wire_fields_and_enum_values_match_source(self):
        source = PROTO.read_text(encoding="utf-8")
        source = re.sub(r"//[^\n]*", "", source)
        nodes = re.findall(r"\b(message|enum)\s+(\w+)\s*\{([^{}]+)\}", source)
        self.assertEqual(len(nodes), len(pb.DESCRIPTOR.message_types_by_name)
                         + len(pb.DESCRIPTOR.enum_types_by_name))
        for kind, name, body in nodes:
            if kind == "enum":
                expected = re.findall(r"(\w+)\s*=\s*(\d+)\s*;", body)
                actual = [(v.name, str(v.number)) for v in
                          pb.DESCRIPTOR.enum_types_by_name[name].values]
                self.assertEqual(expected, actual, name)
                continue
            expected = re.findall(
                r"\b(repeated\s+)?(\w+)\s+(\w+)\s*=\s*(\d+)\s*;", body)
            actual = pb.DESCRIPTOR.message_types_by_name[name].fields
            self.assertEqual(len(expected), len(actual), name)
            for (repeated, declared_type, declared_name, number), field in zip(expected, actual):
                self.assertEqual((declared_name, int(number)), (field.name, field.number))
                self.assertEqual(bool(repeated.strip()), field.is_repeated)
                if field.type == FieldDescriptor.TYPE_MESSAGE:
                    type_name = field.message_type.name
                elif field.type == FieldDescriptor.TYPE_ENUM:
                    type_name = field.enum_type.name
                else:
                    type_name = {FieldDescriptor.TYPE_STRING: "string",
                                 FieldDescriptor.TYPE_UINT32: "uint32",
                                 FieldDescriptor.TYPE_UINT64: "uint64",
                                 FieldDescriptor.TYPE_BOOL: "bool"}[field.type]
                self.assertEqual(declared_type, type_name, declared_name)


if __name__ == "__main__":
    unittest.main()
