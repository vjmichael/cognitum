"""C06/C07 actual in-memory SQLite and typed Protobuf adversarial acceptance."""
import unittest
from cognitum.proto import host_owned_memory_pb2 as pb
from cognitum.host_owned_memory_wire import execute_query,execute_proposal,verify

def query_request():
    r=pb.Query(schema_version=1,host_authorized_scope="workspace_A",
               scope_id="workspace_A",query_text="spacecraft",
               expected_snapshot_id="snapshot_3",
               expected_owner_revision=3,max_results=8)
    r.snapshot.schema_version=1
    r.snapshot.owner="Lu_ANSF"
    r.snapshot.snapshot_id="snapshot_3"
    r.snapshot.owner_revision=3
    r.snapshot.rows.add(source_id="s1",source_revision=3,
        scope_id="workspace_A",subject="project",text="blue spacecraft",
        citation_handle="cite_1",valid_from_ms=0)
    r.snapshot.rows.add(source_id="s2",source_revision=3,
        scope_id="workspace_B",subject="private",text="secret spacecraft",
        citation_handle="cite_2",valid_from_ms=0)
    return r.SerializeToString(deterministic=True)

def proposal_request():
    r=pb.ProposalRequest(schema_version=1,host_authorized_scope="workspace_A")
    r.snapshot.schema_version=1;r.snapshot.owner="Lu_ANSF"
    r.snapshot.snapshot_id="snapshot_0"
    r.snapshot.scope_id="workspace_A"
    r.event.event_id="decision_1";r.event.scope_id="workspace_A"
    r.event.entity="colony";r.event.predicate="leader"
    r.event.value_type="string";r.event.value="blue"
    r.event.origin_source_id="source_1"
    r.event.actor_authority="user_decision";r.event.action="ASSERT"
    r.event.effective_ms=10;r.event.recorded_ms=10
    return r.SerializeToString(deterministic=True)

class WireTests(unittest.TestCase):
    def test_real_sqlite_fts5_and_protobuf_source_scope(self):
        raw=query_request()
        result=verify("query",raw,execute_query(raw))
        self.assertEqual(result.status,"READ_ONLY")
        self.assertEqual(len(result.hits),1)
        self.assertEqual(result.hits[0].source_id,"s1")
        self.assertEqual(result.hits[0].text,"blue spacecraft")

    def test_real_claim_proposal_without_commit(self):
        raw=proposal_request()
        result=verify("proposal",raw,execute_proposal(raw))
        self.assertEqual(result.status,"HOST_COMMIT_REQUIRED")
        self.assertEqual(len(result.current),1)
        self.assertEqual(result.current[0].authority,"user_decision")

    def test_forged_result_and_cross_scope_refused(self):
        raw=query_request()
        result=pb.QueryResult();result.ParseFromString(execute_query(raw))
        result.hits[0].text="changed by attacker"
        with self.assertRaises(ValueError):
            verify("query",raw,result.SerializeToString(deterministic=True))
        req=pb.Query();req.ParseFromString(raw)
        req.scope_id="workspace_B"
        with self.assertRaises(ValueError):
            execute_query(req.SerializeToString(deterministic=True))

    def test_unknown_fields_and_oversized_request_refused(self):
        raw=proposal_request()
        for bad in (b"",raw+b"\x98\x06\x01",raw+b"\x08\x01",
                    b"\x0a\xff",b"y"*4000001):
            with self.subTest(prefix=bad[:6]),self.assertRaises(ValueError):
                execute_proposal(bad)

if __name__=="__main__":unittest.main()
