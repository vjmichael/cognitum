"""P46R6: durable restart ledger and fail-closed reconciliation.

The fake cgroup data in these tests is explicitly mocked; passing them is NOT
kernel cgroup.kill acceptance or systemd service-manager integration.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cognitum import host_recovery as rec
from cognitum import cgroup2_fixed_runner as runner
from cognitum.cgroup2_contract import preflight
from cognitum.host_surviving_watchkeeper import WatchkeeperDenied

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ID = 'a' * 32
SCOPE_NAME = 'cognitum-fixture-' + ('b'*24)


class RecoveryFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.cgroot = self.root / 'cgroup'
        self.cgroot.mkdir()
        self.scope = self.cgroot / SCOPE_NAME
        self.scope.mkdir()
        (self.scope / 'cgroup.kill').write_bytes(b'')
        (self.scope / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
        (self.scope / 'cgroup.procs').write_bytes(b'')
        self.kernel_mock = patch.object(rec, 'kernel_cgroup_dirfd', return_value=True)
        self.kernel_mock.start()
        self.addCleanup(self.kernel_mock.stop)

    def record(self, jobid=FIXTURE_ID):
        return rec.record_before_worker_release(
            self.state, self.cgroot, self.scope, jobid, os.getpid(), 1234)

    def recover(self, *, status=True, jobid=FIXTURE_ID, execute=True):
        def fake_kill(fd, timeout=5):
            # Only a simulation: cannot certify Linux cgroup.kill execution.
            return bool(status), bool(status)
        with patch.object(rec, 'kill_and_observe', side_effect=fake_kill):
            return rec.reconcile_job(self.state, self.cgroot, jobid, execute=execute)


class LedgerTests(RecoveryFixture):
    def test_prelaunch_record_is_private_durable_and_exact_scope(self):
        recorded = self.record()
        p = self.state / ('p46r6-pending-' + FIXTURE_ID + '.json')
        self.assertTrue(p.is_file())
        self.assertEqual(json.loads(p.read_text()), recorded)
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.assertEqual(recorded['scope_inode'], self.scope.stat().st_ino)
        self.assertFalse(recorded['production_authorized'])

    def test_immutable_record_cannot_be_overwritten(self):
        self.record()
        with self.assertRaises(FileExistsError):
            self.record()
        self.assertEqual(len(list(self.state.glob('p46r6-pending-*'))), 1)

    def test_untrusted_state_directory_denied(self):
        os.chmod(self.state, 0o755)
        with self.assertRaisesRegex(rec.RecoveryDenied, 'NOT_PRIVATE'):
            self.record()
        self.assertFalse(list(self.state.glob('p46r6-pending-*')))

    def test_symlink_scope_and_path_traversal_denied(self):
        link = self.cgroot / ('cognitum-fixture-' + 'c'*24)
        link.symlink_to(self.scope, target_is_directory=True)
        with self.assertRaises(rec.RecoveryDenied):
            rec.record_before_worker_release(self.state, self.cgroot, link,
                                             FIXTURE_ID, os.getpid(), 1234)
        with self.assertRaisesRegex(rec.RecoveryDenied, 'SCOPE_NOT_EXACT_CHILD'):
            rec.record_before_worker_release(self.state, self.cgroot, self.root,
                                             FIXTURE_ID, os.getpid(), 1234)

    def test_no_real_cgroup_denies_prelaunch_without_monkeypatch(self):
        with patch.object(rec, 'kernel_cgroup_dirfd', return_value=False):
            with self.assertRaisesRegex(rec.RecoveryDenied, 'NOT_KERNEL_CGROUP2'):
                self.record()

    def test_strict_duplicate_and_nonstrict_record_content_denied(self):
        self.record()
        name = self.state / ('p46r6-pending-'+FIXTURE_ID+'.json')
        original = name.read_text()
        # The test deliberately changes untrusted input; recovery must reject.
        name.write_text(original.replace('"schema":', '"schema":"bad","schema":', 1))
        with self.assertRaisesRegex(rec.RecoveryDenied, 'DUPLICATE'):
            rec.reconcile_job(self.state, self.cgroot, FIXTURE_ID)

    def test_inspection_does_not_kill_or_claim_kernel_cleanup(self):
        self.record()
        with patch.object(rec, 'kill_and_observe') as mock:
            result = rec.reconcile_job(self.state, self.cgroot, FIXTURE_ID)
        mock.assert_not_called()
        self.assertEqual(result['status'], 'INSPECTION_ONLY')
        self.assertFalse(result['production_authorized'])
        self.assertFalse(list(self.state.glob('p46r6-attempt-*')))

    def test_mock_success_still_unattested_and_durable_attempt(self):
        self.record()
        result = self.recover()
        self.assertEqual(result['status'], 'KERNEL_TREE_CLEARED_UNATTESTED')
        self.assertFalse(result['production_authorized'])
        self.assertFalse(result['independent_attestation'])
        attempts = list(self.state.glob('p46r6-attempt-*'))
        self.assertEqual(len(attempts), 1)
        self.assertEqual(json.loads(attempts[0].read_text()), result)
        self.assertTrue((self.state/('p46r6-pending-'+FIXTURE_ID+'.json')).exists())

    def test_kernel_kill_denial_fails_closed(self):
        self.record()
        result = self.recover(status=False)
        self.assertEqual(result['status'], 'FAILED_CLOSED')
        self.assertEqual(result['reason'], 'KERNEL_KILL_NOT_CONFIRMED')
        self.assertFalse(result['subtree_empty'])

    def test_postkill_population_conflict_overrides_reported_success(self):
        self.record()
        (self.scope / 'cgroup.events').write_text('populated 1\n')
        result = self.recover(status=True)
        self.assertEqual(result['status'], 'FAILED_CLOSED')
        self.assertEqual(result['reason'], 'FINAL_KERNEL_STATE_NOT_EMPTY')
        self.assertTrue(result['kill_written'])

    def test_drifted_cgroup_inode_denies_before_kill(self):
        self.record()
        p = self.state / ('p46r6-pending-'+FIXTURE_ID+'.json')
        data = json.loads(p.read_text())
        data['scope_inode'] += 1
        p.write_text(json.dumps(data))
        with patch.object(rec, 'kill_and_observe') as kill:
            result = rec.reconcile_job(self.state, self.cgroot, FIXTURE_ID, execute=True)
        kill.assert_not_called()
        self.assertEqual(result['reason'], 'SCOPE_IDENTITY_CHANGED')

    def test_boot_id_change_denies_before_open_kernel_scope(self):
        self.record()
        with patch.object(rec, '_boot_id', return_value='12345678-0000-0000-0000-000000000000'):
            result = rec.reconcile_job(self.state, self.cgroot, FIXTURE_ID, execute=True)
        self.assertEqual(result['status'], 'FAILED_CLOSED')
        self.assertEqual(result['reason'], 'BOOT_ID_CHANGED')

    def test_multi_job_restart_scan_and_bounded_enumeration(self):
        self.record(FIXTURE_ID)
        self.record('d'*32)
        with patch.object(rec, 'kill_and_observe', return_value=(True, True)):
            values = rec.reconcile_pending(self.state, self.cgroot, execute=True)
        self.assertEqual(len(values), 2)
        self.assertTrue(all(v['status'] == 'KERNEL_TREE_CLEARED_UNATTESTED' for v in values))
        with self.assertRaisesRegex(rec.RecoveryDenied, 'TOO_MANY_PENDING_RECORDS'):
            rec.reconcile_pending(self.state, self.cgroot, max_records=1)

    def test_malformed_pending_file_cannot_become_success(self):
        name = self.state / ('p46r6-pending-'+FIXTURE_ID+'.json')
        name.write_text('{"schema": nonsense}')
        os.chmod(name, 0o600)
        result = rec.reconcile_pending(self.state, self.cgroot, execute=True)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['status'],'FAILED_CLOSED')
        self.assertFalse(result[0]['kill_written'])

    def test_restarted_child_interpreter_reads_existing_ledger(self):
        self.record()
        # A genuinely distinct Python process opens the durable ledger.
        script = 'import json,sys;from pathlib import Path;from cognitum import host_recovery as r; print(json.dumps(r.reconcile_pending(Path(sys.argv[1]), Path(sys.argv[2]))))'
        completed = subprocess.run([sys.executable, '-c', script, str(self.state), str(self.cgroot)],
                                   cwd=ROOT, capture_output=True, timeout=7, check=True)
        values = json.loads(completed.stdout)
        self.assertEqual(values[0]['status'], 'INSPECTION_ONLY')
        self.assertFalse(values[0]['production_authorized'])
        self.assertFalse(list(self.state.glob('p46r6-attempt-*')))

    def test_host_closed_marker_is_stable_and_no_new_cleanup_attempt(self):
        self.record()
        rec.mark_closed_after_verified_cleanup(self.state, FIXTURE_ID)
        with patch.object(rec, 'kill_and_observe') as kill:
            value = rec.reconcile_job(self.state, self.cgroot, FIXTURE_ID, execute=True)
        kill.assert_not_called()
        self.assertEqual(value['status'], 'HOST_REPORTED_CLOSED_UNATTESTED')
        self.assertFalse(value['independent_attestation'])
        with self.assertRaises(FileExistsError):
            rec.mark_closed_after_verified_cleanup(self.state, FIXTURE_ID)

    def test_contradictory_closed_marker_cannot_hide_pending_job(self):
        self.record()
        rec.mark_closed_after_verified_cleanup(self.state, FIXTURE_ID)
        p = self.state / ('p46r6-closed-' + FIXTURE_ID + '.json')
        data = json.loads(p.read_text())
        data['scope_inode'] += 1
        p.write_text(json.dumps(data))
        with self.assertRaisesRegex(rec.RecoveryDenied, 'CONTRADICTORY_CLOSED_RECORD'):
            rec.reconcile_job(self.state, self.cgroot, FIXTURE_ID, execute=True)

    def test_watchkeeper_sigkill_then_independent_restart_simulated_cleanup(self):
        # A real disposable watchdog dies; recovery runs in an entirely new
        # interpreter. Its kernel functions are MOCKED and cannot certify cgroup2.
        watcher = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'],
                                   cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        try:
            rec.record_before_worker_release(
                self.state, self.cgroot, self.scope, FIXTURE_ID, os.getpid(), watcher.pid)
            watcher.kill()
            self.assertEqual(watcher.wait(timeout=4), -9)
            script = """import json, sys
from pathlib import Path
from unittest.mock import patch
from cognitum import host_recovery as r
with patch.object(r, 'kernel_cgroup_dirfd', return_value=True), patch.object(r, 'kill_and_observe', return_value=(True, True)):
    result=r.reconcile_pending(Path(sys.argv[1]), Path(sys.argv[2]),execute=True)
print(json.dumps(result))
"""
            proc = subprocess.run([sys.executable, '-c', script, str(self.state), str(self.cgroot)],
                                  cwd=ROOT, capture_output=True, timeout=7, check=True)
            result = json.loads(proc.stdout)
            self.assertEqual(result[0]['status'],'KERNEL_TREE_CLEARED_UNATTESTED')
            self.assertTrue(list(self.state.glob('p46r6-attempt-*')))
            self.assertEqual(result[0]['independent_attestation'], False)
        finally:
            if watcher.poll() is None: watcher.kill()
            watcher.wait(timeout=4)

    def test_public_cli_cannot_use_a_fake_filesystem_as_kernel_cgroup(self):
        self.record()
        cmd = [sys.executable, '-m', 'cognitum.host_recovery',
               '--state-dir', str(self.state), '--delegated-root', str(self.cgroot), '--execute']
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=6)
        self.assertEqual(proc.returncode, 2)
        body = json.loads(proc.stdout)
        # P46R8: the CLI now rejects a non-cgroup root *before* reading any
        # pending job. It must not return an apparently successful result list.
        self.assertEqual(body['status'], 'FAILED_CLOSED')
        self.assertFalse('results' in body)

    def test_empty_recovery_directory_on_fake_root_is_denied(self):
        proc = subprocess.run([sys.executable, '-m', 'cognitum.host_recovery',
                               '--state-dir', str(self.state), '--delegated-root', str(self.cgroot),
                               '--execute'], cwd=ROOT, capture_output=True, text=True, timeout=6)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)['status'], 'FAILED_CLOSED')

    def test_actual_host_cgroup_preflight_is_denied_here(self):
        check = preflight('/sys/fs/cgroup')
        if check.writable and check.admitted_for_fixture:
            self.skipTest('Live delegated cgroup acceptance requires isolated security harness')
        self.assertFalse(check.admitted_for_fixture)
        self.assertNotEqual(check.reason, 'FIXTURE_SCOPE_POSSIBLE_NOT_OS_SANDBOX')


class LauncherOrderTests(unittest.TestCase):
    def test_new_durable_mode_records_before_worker_spawn(self):
        from test_p46r5_handoff_integration import MockScope, MockWatchkeeper
        MockScope.root = Path('/unused')
        watch = MockWatchkeeper()
        watch.proc.pid = 1234
        from cognitum.alpha_native import make_call
        import struct
        MockScope.events = []
        original = runner.subprocess.Popen
        def record(*args):
            MockScope.events.append('record-fsynced')
        def spawn(*a, **kw):
            self.assertIn('record-fsynced', MockScope.events)
            MockScope.events.append('worker-spawned')
            return original(*a, **kw)
        call = make_call('p46r6','1/3 + 1/6')
        frame = struct.pack('>I',len(call))+call
        with patch.object(runner, 'FixtureCgroupScope', MockScope), \
             patch.object(runner, 'arm_watchkeeper', return_value=watch), \
             patch.object(runner, 'record_before_worker_release', side_effect=record), \
             patch.object(runner, 'mark_closed_after_verified_cleanup') as closed, \
             patch.object(runner.subprocess, 'Popen', side_effect=spawn):
            result = runner.execute_fixed_in_cgroup(frame, recovery_state_dir=Path('/unused'))
        self.assertTrue(result['durable_recovery_recorded'])
        closed.assert_called_once_with(Path('/unused'), watch.jobid)
        self.assertLess(MockScope.events.index('record-fsynced'), MockScope.events.index('worker-spawned'))

    def test_durable_record_failure_prevents_any_worker_spawn(self):
        from test_p46r5_handoff_integration import MockScope, MockWatchkeeper
        MockScope.root = Path('/unused')
        MockScope.events = []
        watch = MockWatchkeeper()
        watch.proc.pid = 1234
        with patch.object(runner,'FixtureCgroupScope',MockScope), \
             patch.object(runner,'arm_watchkeeper',return_value=watch), \
             patch.object(runner,'record_before_worker_release',side_effect=rec.RecoveryDenied('DISK_FULL')), \
             patch.object(runner.subprocess,'Popen') as proc:
            with self.assertRaisesRegex(rec.RecoveryDenied, 'DISK_FULL'):
                runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00', recovery_state_dir=Path('/unused'))
        proc.assert_not_called()
        self.assertTrue(any(e in MockScope.events for e in ('scope-emergency-cleanup','watchkeeper-observed-clean')))


if __name__ == '__main__': unittest.main()
