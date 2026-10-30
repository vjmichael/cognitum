"""P7 Lu host-only Protobuf bridge *source/wire* contracts.

These tests never pretend to run native Rust. They protect source parity,
message shape, binary compatibility, and the absent model/host grant surface.
"""
from pathlib import Path
import re
import unittest

from cognitum.proto import memory_pb2 as pb

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'integrations/lu/src-tauri/lu-core'
BRIDGE = NATIVE / 'src/ansf_memory_proto.rs'
GATE = NATIVE / 'src/ansf_memory_gate.rs'
SCHEMA = ROOT / 'proto/cognitum/memory/v1/evidence.proto'
OVERLAY_SCHEMA = NATIVE / 'proto/cognitum/memory/v1/evidence.proto'


class C06P7ProtobufBridgeContract(unittest.TestCase):
    def test_lu_proto_is_exact_cognitum_schema_and_descriptor(self):
        self.assertEqual(OVERLAY_SCHEMA.read_bytes(), SCHEMA.read_bytes())
        self.assertEqual(pb.DESCRIPTOR.name, 'cognitum/memory/v1/evidence.proto')
        self.assertEqual(pb.DESCRIPTOR.package, 'cognitum.memory.v1')

    def test_requests_never_carry_grants_profiles_or_paths(self):
        for cls in (pb.MemoryQuery, pb.CitationLookup):
            fields = set(cls.DESCRIPTOR.fields_by_name)
            self.assertFalse(fields & {
                'owner_id', 'profile_id', 'grant', 'token', 'policy_path',
                'book_path', 'workspace_path', 'authorization_epoch',
            })
        self.assertEqual({'schema_version','literal_query','request_id','max_results','include_historical','exact_sources'},
                         set(pb.MemoryQuery.DESCRIPTOR.fields_by_name))

    def test_round_trip_binary_query_reply_and_citation(self):
        query = pb.MemoryQuery(schema_version=1, request_id='r1', literal_query='silver', max_results=5)
        encoded = query.SerializeToString(deterministic=True)
        self.assertEqual(pb.MemoryQuery.FromString(encoded), query)
        reply = pb.RetrievalReply(schema_version=1, request_id='r1', status=pb.VERIFIED)
        evidence = reply.evidence.add(content_sha256='a'*64, snapshot_id='c06-epoch-4',
                                      citation_handle='c06:chat1:2:3:4', excerpt='silver notebook',
                                      revision_kind=pb.CURRENT)
        evidence.source.session_id = 'chat1'
        evidence.source.chapter_id = '1'
        evidence.source.entry_id = '2'
        evidence.source.revision_id = '3'
        decoded = pb.RetrievalReply.FromString(reply.SerializeToString())
        self.assertEqual(decoded.evidence[0].citation_handle, 'c06:chat1:2:3:4')
        cited = pb.CitationLookup(schema_version=1, request_id='r2',
                citation_handle=decoded.evidence[0].citation_handle,
                snapshot_id=decoded.evidence[0].snapshot_id,
                content_sha256=decoded.evidence[0].content_sha256,
                length_utf8_byte=len(decoded.evidence[0].excerpt.encode('utf-8')))
        cited.source.CopyFrom(decoded.evidence[0].source)
        self.assertEqual(pb.CitationLookup.FromString(cited.SerializeToString()), cited)

    def test_rust_wire_has_limits_canonical_frame_and_source_rechecks(self):
        code = BRIDGE.read_text(encoding='utf-8')
        for required in (
            'MAX_REQUEST_BYTES', 'MAX_REPLY_BYTES', 'decoded.encode_to_vec() != bytes',
            'q.schema_version != CONTRACT_VERSION', '!q.exact_sources.is_empty()',
            'self.gate.with_search(', 'self.gate.with_citation(',
            'q.citation_handle != citation_handle(&locator)', 'q.length_utf8_byte',
            'valid_request_id', 'proto::RetrievalStatus::Verified',
        ):
            with self.subTest(required=required): self.assertIn(required, code)
        self.assertNotIn('serde_json', code)
        self.assertNotIn('Command::new', code)
        self.assertNotIn('register_tool', code)
        self.assertNotIn('tauri::command', code)

    def test_dirty_marker_precedes_mutation_and_result_is_fenced(self):
        code = GATE.read_text(encoding='utf-8')
        method = code.split('pub fn with_source_mutation', 1)[1].split('pub fn reconcile_source', 1)[0]
        expected_order = [
            'self.begin_source_update(principal, authority, kind, event_id, operation_id)?',
            'transaction_with_behavior(TransactionBehavior::Immediate)',
            'self.require_mutation(principal, authority, kind, event_id)?',
            'let result = mutate(&scoped)?',
            'reconcile_book_index(&self.book, &self.catalog, &self.index)',
            'SET source_dirty=0,index_epoch=index_epoch+1',
        ]
        positions = [method.find(item) for item in expected_order]
        self.assertTrue(all(p >= 0 for p in positions), positions)
        self.assertEqual(positions, sorted(positions))
        self.assertIn('fn reject_reentrant_call', code)
        self.assertIn('pub is_current: bool', code)

    def test_build_path_compiles_lu_and_cognitum_descriptors(self):
        code = (ROOT / 'integrations/lu/apply_overlay.py').read_text()
        self.assertIn('"proto/{PROTO}"', code)
        self.assertIn('compile_protos', code)
        self.assertIn('build.rs', code)

if __name__ == '__main__': unittest.main()
