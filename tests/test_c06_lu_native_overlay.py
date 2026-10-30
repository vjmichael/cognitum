"""P6 offline native-overlay contract checks; NOT Rust compilation/tests.

Exercise the literal SQLite DDL embedded in the Rust module and verify that
its checked-in host API shape still points to Lu ANSF/ownership contracts.
Native `cargo test -p lu-core ansf_memory_gate` is a required separate gate.
"""
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUST = ROOT / 'integrations/lu/src-tauri/lu-core/src/ansf_memory_gate.rs'


def sql_schema():
    raw = RUST.read_text(encoding='utf-8')
    match = re.search(r'conn\.execute_batch\(\s*"(.*?)"\s*\)\.map_err\(sql_error\)\?', raw, re.S)
    if match is None:
        raise AssertionError('Rust policy DDL is missing or no longer statically extractable')
    return match.group(1)


class NativeHostSqlContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'native-policy.sqlite'
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=.1)
        self.addCleanup(self.db.close)
        self.db.executescript(sql_schema())
        self.db.execute('INSERT INTO c06_memory_access VALUES (?,?,?,?,?,?,?,?)',
                        ('chat1', 'profile1', 'project1', 1, 0, 1, 1, 0))

    def test_policy_schema_persists_and_owner_is_immutable(self):
        self.assertEqual(self.db.execute('SELECT profile_id FROM c06_memory_access').fetchone()[0], 'profile1')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE c06_memory_access SET profile_id='attacker'")
        another = sqlite3.connect(self.path)
        try:
            self.assertEqual(another.execute('SELECT workspace_id FROM c06_memory_access').fetchone()[0], 'project1')
        finally:
            another.close()

    def test_revocation_is_terminal_even_across_restart(self):
        self.db.execute("UPDATE c06_memory_access SET enabled=0, auth_epoch=2 WHERE session_id='chat1'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE c06_memory_access SET enabled=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('DELETE FROM c06_memory_access')
        reopened = sqlite3.connect(self.path)
        try:
            self.assertEqual(reopened.execute('SELECT enabled FROM c06_memory_access').fetchone()[0], 0)
        finally:
            reopened.close()

    def test_deletion_markers_cannot_be_removed_or_rewritten(self):
        self.db.execute("INSERT INTO c06_memory_tombstone VALUES ('chat1',42)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE c06_memory_tombstone SET root_entry_id=43")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM c06_memory_tombstone")
        self.assertEqual(self.db.execute('SELECT root_entry_id FROM c06_memory_tombstone').fetchone()[0], 42)

    def test_write_reservation_blocks_second_connection_ack(self):
        other = sqlite3.connect(self.path, isolation_level=None, timeout=.04)
        self.addCleanup(other.close)
        self.db.execute('BEGIN IMMEDIATE')
        with self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
            other.execute("UPDATE c06_memory_access SET enabled=0 WHERE session_id='chat1'")
        self.db.execute('COMMIT')
        other.execute("UPDATE c06_memory_access SET enabled=0 WHERE session_id='chat1'")
        self.assertEqual(self.db.execute('SELECT enabled FROM c06_memory_access').fetchone()[0], 0)

    def test_dirty_state_is_durable(self):
        self.db.execute("UPDATE c06_memory_access SET source_dirty=1 WHERE session_id='chat1'")
        other = sqlite3.connect(self.path)
        try:
            self.assertEqual(other.execute('SELECT source_dirty FROM c06_memory_access').fetchone()[0], 1)
        finally:
            other.close()

    def test_native_api_has_recheck_and_no_raw_webview_identity(self):
        code = RUST.read_text(encoding='utf-8')
        for expected in ('OwnershipStore', 'HostPrincipal', 'ResourceAction::Read',
                         'TransactionBehavior::Immediate', 'reconcile_book_index',
                         'fn with_search', 'fn with_citation', 'fn tombstone_root',
                         'fn begin_source_update', 'fn reconcile_source',
                         'fn reject_reentrant_call', 'fn validate_revision', 'SHA256'):
            if expected == 'SHA256':
                expected = 'Sha256::digest'
            self.assertIn(expected, code)
        self.assertNotIn('serde_json', code)
        self.assertNotIn('Command::new', code)


if __name__ == '__main__':
    unittest.main()
