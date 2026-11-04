"""C18 metadata-only SQLite restart and rollback custody, Windows/Linux."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
import unittest

from cognitum.adaptation_policy import (
    RoutingPolicy,AdaptationProposal,Trace,seal,
)
from cognitum.adaptation_lifecycle import (
    prepare,transition,evaluate_promotion,
)
from cognitum.adaptation_journal import AdaptationJournal

SHA="a"*64

def fixture():
    base=seal(RoutingPolicy(1,"workspace_a","tool_router",("general",),1,
        ((0.,),(0.,),(0.,)),(2.,0.,0.),
        (0.,),(1.,),"b"*64,"original","0"*64,"approved",""))
    candidate=seal(RoutingPolicy(2,"workspace_a","tool_router",("general",),1,
        ((0.,),(0.,),(0.,)),(0.,2.,0.),
        (0.,),(1.,),"c"*64,"candidate1",base.digest,"candidate",""))
    p=AdaptationProposal("candidate1","workspace_a","tool_router",2,SHA,
        "consent_a","public_synthetic",("general",),200000,61000,
        61000,base.digest,80,120000,base.digest)
    hold=tuple(Trace("hold_"+str(i),61000+i*1000,(0.,),"specialist",
         SHA,"consent_a",200000,"public_synthetic","general")
         for i in range(20))
    gate=evaluate_promotion(p,candidate,base,hold)
    if gate.status!="READY_FOR_HOST_APPROVAL":
        raise RuntimeError("fixture promotion did not pass")
    return p,base,candidate,hold,gate

class C18JournalTests(unittest.TestCase):
    def test_real_sqlite_restart_keeps_revocation_and_isolation(self):
        p,b,c,h,g=fixture()
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"policy.sqlite"
            db=AdaptationJournal(path)
            state=prepare(p,b)
            db.put(state,expected_previous=-1)
            state=transition(state,mutation_id="approve1",expected_revision=0,
                 decision="approve",candidate=c,promotion=g,
                 proposal=p,incumbent=b,holdout=h,host_authorized=True)
            db.put(state,expected_previous=0)
            state=transition(state,mutation_id="pause1",expected_revision=1,
                 decision="pause",host_authorized=True)
            db.put(state,expected_previous=1)
            state=transition(state,mutation_id="rollback1",expected_revision=2,
                 decision="rollback",host_authorized=True)
            db.put(state,expected_previous=2)
            state=transition(state,mutation_id="revoke1",expected_revision=3,
                 decision="revoke",host_authorized=True)
            db.put(state,expected_previous=3)
            with self.assertRaises(ValueError):
                db.put(state,expected_previous=3)
            db.close()
            reopened=AdaptationJournal(path)
            recovered=reopened.restore("workspace_a","candidate1")
            self.assertEqual(recovered,state)
            self.assertEqual(recovered.status,"revoked")
            self.assertEqual(recovered.current_policy_digest,b.digest)
            self.assertIsNone(reopened.restore("workspace_other","candidate1"))
            self.assertIsNone(reopened.restore("workspace_a","unknown"))
            metadata=b"".join(x[0] for x in reopened.db.execute(
                "SELECT payload FROM adaptation_revisions").fetchall())
            self.assertNotIn(b"features",metadata)
            self.assertNotIn(b"expected_route",metadata)
            self.assertNotIn(b"consent_a",metadata)
            reopened.close()

    def test_tampered_metadata_and_discontinuous_transition_rejected(self):
        p,b,c,h,g=fixture()
        with TemporaryDirectory() as tmp:
            db=AdaptationJournal(Path(tmp)/"policy.sqlite")
            original=prepare(p,b)
            db.put(original,expected_previous=-1)
            wrong=replace(original,revision=1,seen_mutations=("mutation1",),
                          status="active")
            from cognitum.adaptation_lifecycle import _seal
            with self.assertRaises(ValueError):
                db.put(_seal(wrong),expected_previous=0)
            db.db.execute("UPDATE adaptation_revisions SET payload_sha256=?",
                          ("0"*64,))
            with self.assertRaises(ValueError):
                db.restore("workspace_a","candidate1")
            db.close()

if __name__=="__main__":
    unittest.main()
