"""C06 actual SQLite FTS5 over disposable Lu-owned snapshots."""
from dataclasses import replace
import unittest
from cognitum.memory_derived import Evidence,Snapshot,Query,DerivedIndex,validate_snapshot

def snapshot():
    return Snapshot("Lu_ANSF","snapshot_5",5,(
        Evidence("source_1",2,"workspace_A","project","red spacecraft engine","cite_1",0,None),
        Evidence("source_2",3,"workspace_A","project","blue spacecraft engine","cite_2",10,None),
        Evidence("source_3",4,"workspace_B","project","private spacecraft engine","cite_3",0,None),
        Evidence("source_4",5,"workspace_A","project","obsolete spacecraft engine","cite_4",0,None,True),
        Evidence("source_5",5,"workspace_A","inventory","spare reactor component","cite_5",10,20),
    ))

class MemoryTests(unittest.TestCase):
    def test_scoped_fts_exact_and_tombstone(self):
        s=snapshot()
        i=DerivedIndex(s,host_authorized_scope="workspace_A")
        try:
            hits=i.query(Query("workspace_A","spacecraft engine","snapshot_5",5))
            self.assertEqual({x.source_id for x in hits},{"source_1","source_2"})
            self.assertTrue(all(x.citation_handle.startswith("cite_") for x in hits))
            self.assertEqual(i.exact("workspace_A","source_1",expected_owner_revision=5).text,
                             "red spacecraft engine")
            self.assertIsNone(i.exact("workspace_A","source_4",expected_owner_revision=5))
            self.assertIsNone(i.exact("workspace_A","source_3",expected_owner_revision=5))
        finally:i.close()

    def test_scope_staleness_and_subject_temporal_filter(self):
        i=DerivedIndex(snapshot(),host_authorized_scope="workspace_A")
        try:
            for q in (Query("workspace_B","private","snapshot_5",5),
                      Query("workspace_A","spacecraft","snapshot_old",5),
                      Query("workspace_A","spacecraft","snapshot_5",4)):
                with self.assertRaises(ValueError):i.query(q)
            self.assertEqual(len(i.query(Query("workspace_A","reactor","snapshot_5",5,
                                                as_of_ms=15,subject="inventory"))),1)
            self.assertFalse(i.query(Query("workspace_A","reactor","snapshot_5",5,
                                           as_of_ms=30,subject="inventory")))
            with self.assertRaises(ValueError):
                i.exact("workspace_B","source_3",expected_owner_revision=5)
        finally:i.close()

    def test_rebuild_respects_canonical_deletion_and_correction(self):
        s=snapshot()
        old=DerivedIndex(s,host_authorized_scope="workspace_A")
        try:
            self.assertEqual(len(old.query(Query("workspace_A","red","snapshot_5",5))),1)
        finally:old.close()
        rows=list(s.rows)
        rows[0]=replace(rows[0],text="replaced by yellow engine",source_revision=6)
        rows[1]=replace(rows[1],tombstoned=True,source_revision=6)
        current=replace(s,snapshot_id="snapshot_6",owner_revision=6,rows=tuple(rows))
        idx=DerivedIndex(current,host_authorized_scope="workspace_A")
        try:
            self.assertFalse(idx.query(Query("workspace_A","red","snapshot_6",6)))
            self.assertFalse(idx.query(Query("workspace_A","blue","snapshot_6",6)))
            self.assertEqual(len(idx.query(Query("workspace_A","yellow","snapshot_6",6))),1)
        finally:idx.close()

    def test_untrusted_query_syntax_and_malformed_source(self):
        i=DerivedIndex(snapshot(),host_authorized_scope="workspace_A")
        try:
            self.assertIsInstance(i.query(Query("workspace_A",
                    "' OR * AND ( --","snapshot_5",5)),tuple)
            with self.assertRaises(ValueError):
                i.query(Query("workspace_A","good","snapshot_5",5,max_results=999))
        finally:i.close()
        s=snapshot()
        with self.assertRaises(ValueError):
            validate_snapshot(replace(s,owner="Cognitum"))
        with self.assertRaises(ValueError):
            validate_snapshot(replace(s,rows=s.rows+(s.rows[0],)))

if __name__=="__main__":unittest.main()
