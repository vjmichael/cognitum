import unittest
from cognitum.research.hdc_index_lifecycle import EphemeralDerivedIndex
from cognitum.proto import research_optional_pb2 as p

DATA=(('first','owns','ship'),('second','owns','station'))

class IndexLifecycle(unittest.TestCase):
    def setUp(self):
        self.store=EphemeralDerivedIndex()
    def test_query_fresh_and_guarded_delivery(self):
        g=self.store.install('rev1',DATA)
        emitted=[]
        self.assertEqual(self.store.deliver('rev1','owns','ship',2,emitted.append),g)
        self.assertEqual(p.HdcCandidates.FromString(emitted[0]).candidate_ids[0],'first')
        self.assertFalse(p.HdcCandidates.FromString(emitted[0]).grants_authority)
    def test_default_no_index(self):
        with self.assertRaisesRegex(ValueError,'STALE_OR_UNINITIALIZED'):
            self.store.deliver('rev1','owns','ship',1,lambda x:None)
    def test_no_revision_swap_without_invalidation(self):
        self.store.install('rev1',DATA)
        with self.assertRaisesRegex(ValueError,'MUST_INVALIDATE'):
            self.store.install('rev2',DATA)
    def test_edit_delete_retract_revocation_clear_data(self):
        for reason in ['EDIT','RETRACT','DELETE','SCOPE_REVOKED','RESTORE','SOURCE_REPLACED']:
            store=EphemeralDerivedIndex();store.install('rev1',DATA)
            g=store.generation
            self.assertGreater(store.invalidate(reason=reason),g)
            with self.assertRaisesRegex(ValueError,'STALE_OR_UNINITIALIZED'):
                store.deliver('rev1','owns','ship',1,lambda x:self.fail('published'))
            store.install('rev2',DATA)
            with self.assertRaisesRegex(ValueError,'STALE_OR_UNINITIALIZED'):
                store.deliver('rev1','owns','ship',1,lambda x:self.fail('published'))
    def test_bad_records_and_duplicate(self):
        for rows in [(), (('a','owns','ship'),('a','owns','moon')), (('a','owns','ship'),('b','bad/role','moon')), ('bad',)]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                EphemeralDerivedIndex().install('rev1',rows)
    def test_invalidating_during_sink_clears_future_reads(self):
        self.store.install('rev1',DATA)
        received=[]
        def sink(raw):
            received.append(raw)
            self.store.invalidate(reason='DELETE')
        self.store.deliver('rev1','owns','ship',1,sink)
        self.assertEqual(len(received),1)
        with self.assertRaises(ValueError):self.store.deliver('rev1','owns','ship',1,sink)
    def test_explicit_invalid_invalidation_reason(self):
        with self.assertRaises(ValueError):self.store.invalidate(reason='ignore')
    def test_no_sink_or_bad_query(self):
        self.store.install('rev1',DATA)
        with self.assertRaises(ValueError):self.store.deliver('rev1','owns','ship',9,lambda x:None)
        with self.assertRaises(ValueError):self.store.deliver('rev1','owns','ship',1,None)

if __name__=='__main__':unittest.main()
