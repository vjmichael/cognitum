"""C18 real scikit-learn retrieval ranker, temporal holdout and tampering."""
from dataclasses import replace
import unittest

from cognitum.adaptation_retrieval import (
    RetrievalExample,train,predict,evaluate,verify,validate,
)

SHA="a"*64

def examples(nq=16):
    out=[]
    for q in range(nq):
        # Host-provided primary retrieval score is intentionally misleading
        # for this synthetic test, while a second feature indicates relevance.
        for doc in range(4):
            out.append(RetrievalExample(
                "query_"+str(q),"doc_"+str(doc),1000*(q+1),
                (float(4-doc),float(3 if doc==2 else -1)),
                doc==2,SHA,"consent_a"))
    return tuple(out)


class C18RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import numpy,sklearn
        except ImportError:
            raise unittest.SkipTest("optional scikit-learn ranker unavailable")

    def test_real_retrieval_training_beats_original_score(self):
        rows=examples()
        with self.assertRaises(PermissionError):
            train(rows,workspace_id="workspace_a",source_digest=SHA,
                  consent_receipt="consent_a",cutoff_ms=11000,now_ms=20000)
        candidate,holdout=train(rows,workspace_id="workspace_a",
            source_digest=SHA,consent_receipt="consent_a",
            cutoff_ms=11000,now_ms=20000,host_authorized=True)
        self.assertEqual(candidate.status,"candidate")
        self.assertEqual(verify(candidate),candidate)
        original=evaluate(holdout)
        learned=evaluate(holdout,model=candidate)
        self.assertGreater(learned.hit_at_one,original.hit_at_one)
        self.assertEqual(learned.queries,6)
        self.assertGreater(learned.mean_reciprocal_rank,
                           original.mean_reciprocal_rank)

    def test_query_leakage_bad_source_and_corrupt_checkpoint_fail(self):
        rows=examples()
        for bad in (
            rows[:5]+(replace(rows[5],source_digest="b"*64),)+rows[6:],
            rows[:5]+(replace(rows[5],features=(float("nan"),0.)),)+rows[6:],
            rows[:5]+(replace(rows[5],query_id=rows[4].query_id,
                                     document_id=rows[4].document_id),)+rows[6:],
        ):
            with self.subTest(row=str(bad[5])[:60]),self.assertRaises(ValueError):
                validate(bad,cutoff_ms=11000,now_ms=20000,
                         consent_receipt="consent_a",source_digest=SHA)
        candidate,holdout=train(rows,workspace_id="workspace_a",
            source_digest=SHA,consent_receipt="consent_a",
            cutoff_ms=11000,now_ms=20000,host_authorized=True)
        with self.assertRaises(ValueError):
            verify(replace(candidate,weights=(999.,999.)))
        with self.assertRaises(ValueError):
            predict(candidate,replace(holdout[0],consent_receipt="unknown"))
        with self.assertRaises(ValueError):
            evaluate(tuple(replace(x,relevant=False) for x in holdout))


if __name__=="__main__":
    unittest.main()
