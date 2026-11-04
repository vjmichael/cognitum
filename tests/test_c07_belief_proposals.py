"""C07 host-owned ANSF claim reconciliation: no competing state store."""
from dataclasses import replace
import unittest
from cognitum.belief_proposals import StateEvent,EventSnapshot,propose,current_view

def event(event_id,action="ASSERT",authority="user_decision",value="blue",
          target="",revision=0,scope="workspace_A",time=10):
    return StateEvent(event_id,scope,"colony","leader","string",value,
                      "source_"+event_id,authority,revision,time,time,
                      action,target,"host supplied evidence")

def snapshot(*events,revision=0):
    return EventSnapshot("Lu_ANSF","snap_"+str(revision),revision,
                         "workspace_A",tuple(events))

class C07Tests(unittest.TestCase):
    def test_proposal_is_not_canonical_commit(self):
        s=snapshot()
        e=event("decision_1")
        proposed=propose(s,e,host_authorized_scope="workspace_A")
        self.assertEqual(proposed.status,"HOST_COMMIT_REQUIRED")
        self.assertEqual(s.events,())
        self.assertEqual(proposed.current[0].value,"blue")
        self.assertFalse(current_view(s,host_authorized_scope="workspace_A"))

    def test_supersession_preserves_history_and_current_view(self):
        original=event("decision_1")
        initial=snapshot(original,revision=1)
        second=event("decision_2","SUPERSEDE",value="green",
                     target="decision_1",revision=1,time=20)
        p=propose(initial,second,host_authorized_scope="workspace_A")
        self.assertEqual(tuple(x.value for x in p.current),("green",))
        committed=snapshot(original,second,revision=2)
        self.assertEqual(current_view(committed,host_authorized_scope="workspace_A")[0].value,
                         "green")
        self.assertEqual(original.value,"blue")

    def test_conflicting_source_is_reported_not_autoadopted(self):
        user=event("decision_1")
        imported=event("import_1","ASSERT","imported_claim","red",revision=1,time=20)
        p=propose(snapshot(user,revision=1),imported,
                  host_authorized_scope="workspace_A")
        self.assertEqual({x.value for x in p.current},{"red","blue"})
        self.assertEqual(len(p.competing),1)
        with self.assertRaises(ValueError):
            propose(snapshot(user,revision=1),
                    event("import_2","SUPERSEDE","imported_claim","red",
                          target="decision_1",revision=1,time=20),
                    host_authorized_scope="workspace_A")

    def test_import_cannot_expire_or_confirm_user_decision(self):
        user=event("decision_1")
        initial=snapshot(user,revision=1)
        for operation in ("CONFIRM","EXPIRE","RETRACT","SUPERSEDE","MERGE"):
            imported=event("import_"+operation,operation,"imported_claim","blue",
                           target="decision_1",revision=1,time=20)
            with self.subTest(operation=operation),self.assertRaises(ValueError):
                propose(initial,imported,host_authorized_scope="workspace_A")
        # Reporting contradictory evidence as a challenge is permitted.
        challenge=event("challenge_1","CHALLENGE","imported_claim","red",
                        target="decision_1",revision=1,time=20)
        self.assertEqual(propose(initial,challenge,
                         host_authorized_scope="workspace_A").status,
                         "HOST_COMMIT_REQUIRED")

    def test_confirmation_must_preserve_exact_target_value(self):
        user=event("decision_1")
        for action in ("CONFIRM","RETRACT","EXPIRE"):
            changed=event("changed_"+action,action,"user_decision","yellow",
                          target="decision_1",revision=1,time=20)
            with self.subTest(action=action),self.assertRaises(ValueError):
                propose(snapshot(user,revision=1),changed,
                        host_authorized_scope="workspace_A")

    def test_challenge_keeps_prior_claim_visible(self):
        user=event("decision_1")
        challenged=event("challenge_1","CHALLENGE","imported_claim","red",
                         target="decision_1",revision=1,time=20)
        p=propose(snapshot(user,revision=1),challenged,
                  host_authorized_scope="workspace_A")
        self.assertEqual(len(p.current),2)
        self.assertIn("challenged",{x.status for x in p.current})
        self.assertTrue(any(x.conflict_event_ids for x in p.current))

    def test_retract_and_replay_stale_revision_refused(self):
        user=event("decision_1")
        deletion=event("retract_1","RETRACT","user_decision","blue",
                       target="decision_1",revision=1,time=20)
        p=propose(snapshot(user,revision=1),deletion,
                  host_authorized_scope="workspace_A")
        self.assertEqual(p.current,())
        with self.assertRaises(ValueError):
            propose(snapshot(user,revision=2),deletion,
                    host_authorized_scope="workspace_A")
        with self.assertRaises(ValueError):
            propose(snapshot(user,revision=1),event("decision_1",revision=1),
                    host_authorized_scope="workspace_A")

    def test_scope_host_grant_and_unknown_revision_rejected(self):
        s=snapshot()
        with self.assertRaises(ValueError):
            propose(s,event("bad",scope="workspace_B"),
                    host_authorized_scope="workspace_A")
        with self.assertRaises(ValueError):
            current_view(s,host_authorized_scope="workspace_B")
        with self.assertRaises(ValueError):
            propose(s,event("bad",revision=0),
                    host_authorized_scope="workspace_B")
        with self.assertRaises(ValueError):
            propose(s,event("bad","SUPERSEDE",target="unknown"),
                    host_authorized_scope="workspace_A")

    def test_json_scalar_nonfinite_rejected(self):
        for value in ("NaN","Infinity","-Infinity","null",'{"exec":"code"}'):
            item=replace(event("json_event"),value_type="json_scalar",value=value)
            with self.subTest(value=value),self.assertRaises(ValueError):
                propose(snapshot(),item,host_authorized_scope="workspace_A")
        allowed=replace(event("json_number"),value_type="json_scalar",value="2.5")
        self.assertEqual(propose(snapshot(),allowed,
             host_authorized_scope="workspace_A").status,"HOST_COMMIT_REQUIRED")

    def test_invalid_typed_value_and_fake_ANSF_owner(self):
        with self.assertRaises(ValueError):
            propose(snapshot(),replace(event("e_1"),value_type="boolean",value="maybe"),
                    host_authorized_scope="workspace_A")
        with self.assertRaises(ValueError):
            current_view(replace(snapshot(),owner="Cognitum"),
                         host_authorized_scope="workspace_A")

if __name__=="__main__":unittest.main()
