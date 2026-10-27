# -*- coding: utf-8 -*-
# Protobuf descriptor-backed Python message classes for cognitum/v1/capability.proto.
# Exact message schema is defined in proto/cognitum/v1/capability.proto.
# Descriptor is compiled from the same field definitions; do not edit by hand.
# Requires the optional Python protobuf runtime (see pyproject.toml [proto]).
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf.internal import builder as _builder

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1ccognitum/v1/capability.proto\x12\x0bcognitum.v1"(\n\x0bEvidenceRef\x12\x0c\n\x04kind\x18\x01 \x01(\t\x12\x0b\n\x03ref\x18\x02 \x01(\t".\n\x18CalculateRationalRequest\x12\x12\n\nexpression\x18\x01 \x01(\t"i\n\x17CalculateRationalResult\x12\r\n\x05value\x18\x01 \x01(\t\x12*\n\x08evidence\x18\x02 \x03(\x0b2\x18.cognitum.v1.EvidenceRef\x12\x13\n\x0blimitations\x18\x03 \x03(\t"\xb5\x01\n\x17NumericalEstimateResult\x12\r\n\x05value\x18\x01 \x01(\t\x12\x0e\n\x06method\x18\x02 \x01(\t\x12\x12\n\x05lower\x18\x03 \x01(\tH\x00\x88\x01\x01\x12\x12\n\x05upper\x18\x04 \x01(\tH\x01\x88\x01\x01\x12*\n\x08evidence\x18\x05 \x03(\x0b2\x18.cognitum.v1.EvidenceRef\x12\x13\n\x0blimitations\x18\x06 \x03(\tB\x08\n\x06_lowerB\x08\n\x06_upper"\xae\x01\n\x19RetrievedReferencesResult\x12\x12\n\ncandidates\x18\x01 \x03(\t\x12\x1a\n\x12source_snapshot_id\x18\x02 \x01(\t\x12 \n\x18index_source_snapshot_id\x18\x03 \x01(\t\x12*\n\x08evidence\x18\x04 \x03(\x0b2\x18.cognitum.v1.EvidenceRef\x12\x13\n\x0blimitations\x18\x05 \x03(\t"4\n\x11CapabilityFailure\x12\x0c\n\x04code\x18\x01 \x01(\t\x12\x11\n\tretryable\x18\x02 \x01(\x08b\x06proto3')
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "cognitum.proto.capability_pb2", globals())
