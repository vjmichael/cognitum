"""P11 Rust source/SQLite contract tests. Rust compilation still required."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tests.test_c06_lu_native_overlay import sql_schema

SOURCE=Path(__file__).resolve().parents[1]/'integrations/lu/src-tauri/lu-core/src/ansf_memory_gate.rs'

class MutationAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.source=SOURCE.read_text()

    def test_separate_memory_mutation_authority_exists(self):
        for term in ('pub trait TrustedMemoryMutationAuthorizer: Send + Sync',
                     'pub enum MemoryMutationKind', 'fn require_mutation(',
                     'MemoryMutationKind::Delete', 'MemoryMutationKind::Revoke',
                     'MemoryMutationKind::Recover'):
            with self.subTest(term=term): self.assertIn(term,self.source)

    def test_unauthenticated_read_only_cannot_mutate(self):
        scope=self.source.split('pub fn with_source_mutation',1)[1].split('pub fn reconcile_source',1)[0]
        self.assertIn('self.require_mutation(principal, authority, kind, event_id)?',scope)
        self.assertIn('self.begin_source_update(principal, authority, kind, event_id, operation_id)?',scope)
        self.assertIn('operation_id: &str',scope)
        self.assertNotIn('self.begin_source_update(principal)?',scope)

    def test_scoped_operations_enforce_action(self):
        body=self.source.split("impl ScopedAnsfMutation<'_>",1)[1].split('/// ANSF source',1)[0]
        for operation in ('Append','Revise','Structure','Import'):
            self.assertIn('self.kind != MemoryMutationKind::'+operation,body)

    def test_raw_write_reservation_is_private(self):
        self.assertIn('fn begin_source_update(&self,principal:',self.source)
        self.assertNotIn('pub fn begin_source_update(&self,principal:',self.source)

    def test_native_test_cases_cover_denial_replay_effects(self):
        for test in ('read_permission_never_implies_mutation_permission',
                     'idempotent_operation_id_and_recovery_are_durable',
                     'explicit_effect_cannot_be_escalated_within_scoped_callback',
                     'untrusted_event_string_is_never_an_authority'):
            self.assertIn('fn '+test+'()',self.source)

    def test_sql_operation_log_is_persistent_and_identity_immutable(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'policy.sqlite'
            db=sqlite3.connect(path)
            try:
                db.executescript(sql_schema())
                db.execute('INSERT INTO c06_memory_access VALUES(?,?,?,?,?,?,?,?)',
                           ('s','p','w',1,0,1,1,0))
                db.execute('INSERT INTO c06_mutation_operations VALUES(?,?,?,?,?)',
                           ('s','op-1','event-1','revise','pending'))
                db.commit()
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute('INSERT INTO c06_mutation_operations VALUES(?,?,?,?,?)',
                               ('s','op-1','event-1','revise','pending'))
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE c06_mutation_operations SET event_id='forged'")
                db.execute("UPDATE c06_mutation_operations SET status='committed'")
                db.commit()
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE c06_mutation_operations SET status='pending'")
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute('DELETE FROM c06_mutation_operations')
                with sqlite3.connect(path) as again:
                    self.assertEqual(again.execute('SELECT status FROM c06_mutation_operations').fetchone()[0],
                                     'committed')
            finally:
                db.close()

if __name__=='__main__':unittest.main()
