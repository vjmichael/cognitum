"""P46R7 regression: real external restart of inspection worker + fail-closed gate.

NO kernel cgroup kill is simulated as a successful acceptance in the CLI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cognitum import recovery_service as svc
from cognitum import host_recovery as rec

ROOT = Path(__file__).resolve().parent.parent


class RecoveryServiceGates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.cg = self.root / 'fixture-cgroup'
        self.cg.mkdir()

    def test_fake_cgroup_denied_in_execution_even_when_no_records(self):
        with self.assertRaises(rec.RecoveryDenied):
            svc.run_service(self.state, self.cg, cycles=1, interval=.05)

    def test_readonly_kernel_gate_denies_without_scan(self):
        with patch.object(svc.rec, '_kernel_root_fd', return_value=os.open(self.cg, os.O_RDONLY)), \
             patch.object(svc.os, 'fstatvfs', return_value=type('V', (), {'f_flag': os.ST_RDONLY})()), \
             patch.object(svc.rec, 'reconcile_pending') as pending:
            with self.assertRaisesRegex(svc.ServiceDenied, 'CGROUP2_READ_ONLY'):
                svc.run_service(self.state, self.cg, interval=.05, cycles=1)
            pending.assert_not_called()

    def test_inspection_is_explicit_and_never_authorizes(self):
        results = svc.run_service(self.state, self.cg, inspection_only=True,
                                  interval=.05, cycles=1)
        self.assertEqual(results[0]['status'], 'INSPECTION_ONLY')
        self.assertFalse(results[0]['production_authorized'])
        self.assertIsNone(results[0]['kernel_root'])

    def test_single_writer_lock_rejects_parallel_instances(self):
        fd = svc._lock_state(self.state)
        try:
            with self.assertRaisesRegex(svc.ServiceDenied, 'ALREADY_RUNNING'):
                svc._lock_state(self.state)
        finally:
            os.close(fd)
        acquired = svc._lock_state(self.state)
        os.close(acquired)

    def test_private_state_and_symlink_denied(self):
        os.chmod(self.state, 0o755)
        with self.assertRaises(rec.RecoveryDenied):
            svc._lock_state(self.state)
        os.chmod(self.state, 0o700)
        symlink = self.root / 'alias'
        symlink.symlink_to(self.state)
        with self.assertRaises(rec.RecoveryDenied):
            svc._lock_state(symlink)

    def test_closed_marker_is_not_accepted_as_kernel_success(self):
        with patch.object(svc, '_root_ready', return_value={'root_writable_mount': True}), \
             patch.object(svc.rec, 'reconcile_pending', return_value=[
                 {'status': 'HOST_REPORTED_CLOSED_UNATTESTED'}]):
            with self.assertRaisesRegex(svc.ServiceDenied, 'UNATTESTED_CLOSURE'):
                svc.run_service(self.state, self.cg, interval=.05, cycles=1)

    def test_recovery_denial_preserves_non_authorization(self):
        with patch.object(svc, '_root_ready', return_value={'root_writable_mount': True}), \
             patch.object(svc.rec, 'reconcile_pending', return_value=[
                 {'status': 'FAILED_CLOSED'}]):
            with self.assertRaisesRegex(svc.ServiceDenied, 'FAILED_CLOSED'):
                svc.run_service(self.state, self.cg, interval=.05, cycles=1)

    def test_kernel_mock_result_is_still_unattested(self):
        with patch.object(svc, '_root_ready', return_value={'root_writable_mount': True}), \
             patch.object(svc.rec, 'reconcile_pending', return_value=[
                 {'status': 'KERNEL_TREE_CLEARED_UNATTESTED'}]):
            res = svc.run_service(self.state, self.cg, interval=.05, cycles=1)[0]
            self.assertEqual(res['status'], 'KERNEL_OBSERVED_UNATTESTED')
            self.assertFalse(res['independent_attestation'])
            self.assertFalse(res['production_authorized'])

    def test_runtime_cli_refuses_fake_cgroup(self):
        p = subprocess.run([sys.executable, '-m', 'cognitum.recovery_service',
                            '--state-dir', str(self.state), '--delegated-root', str(self.cg)],
                           cwd=ROOT, capture_output=True, text=True, timeout=6)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)['status'], 'FAILED_CLOSED')

    def test_real_host_ro_mount_fails_closed(self):
        if not Path('/sys/fs/cgroup').exists():
            self.skipTest('cgroup2 mount absent')
        if not (os.statvfs('/sys/fs/cgroup').f_flag & os.ST_RDONLY):
            self.skipTest('cgroup hierarchy writable: dedicated isolated kernel test required')
        with self.assertRaises((rec.RecoveryDenied, svc.ServiceDenied)):
            svc.run_service(self.state, Path('/sys/fs/cgroup'), cycles=1, interval=.05)


@unittest.skipUnless(shutil.which('supervisord') and shutil.which('supervisorctl'),
                     'supervisord/supervisorctl unavailable')
class ExternalManagerRestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.cg = self.root / 'fixture-cgroup'
        self.cg.mkdir()
    def test_real_supervisord_restarts_inspection_after_two_sigkills(self):
        # A real separate supervisor daemon restarts the actual P46R7 service.
        # ONLY --inspect-only on a fake cgroup: no kernel-kill acceptance.
        scope = self.cg / ('cognitum-fixture-' + 'a'*24)
        scope.mkdir()
        jobid = 'b'*32
        # The real durable record is made before launching external supervisor.
        # Only the cgroup2 filesystem identity check is mocked during record
        # construction; the running service remains inspection-only.
        with patch.object(rec, 'kernel_cgroup_dirfd', return_value=True):
            rec.record_before_worker_release(self.state, self.cg, scope, jobid,
                                             os.getpid(), 1234)
        conf = self.root / 'supervisord.ini' 
        sock = self.root / 'supervisor.sock'
        log = self.root / 'manager.log'
        out = self.root / 'service.log'
        cmd = f'{sys.executable} -u -m cognitum.recovery_service --state-dir {self.state} --delegated-root {self.cg} --inspect-only --interval 0.10'
        conf.write_text(f'''[unix_http_server]\nfile={sock}\nchmod=0700\n[supervisord]\nnodaemon=true\nlogfile={log}\npidfile={self.root}/supervisor.pid\nchildlogdir={self.root}\nloglevel=warn\n[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface\n[supervisorctl]\nserverurl=unix://{sock}\n[program:keeper]\ncommand={cmd}\ndirectory={ROOT}\nautostart=true\nautorestart=true\nstartsecs=0\nstopasgroup=true\nstdout_logfile={out}\nstderr_logfile={self.root}/errors.log\n''')
        manager = subprocess.Popen(['supervisord', '-n', '-c', str(conf)],
                                   cwd=ROOT, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            last_pid = None
            for iteration in range(3):
                deadline = time.monotonic() + 8
                pid = None
                while time.monotonic() < deadline:
                    if manager.poll() is not None:
                        raise AssertionError('external supervisor exited')
                    if sock.exists():
                        stat_result = subprocess.run(['supervisorctl', '-c', str(conf), 'pid', 'keeper'],
                                                     capture_output=True, text=True, timeout=2)
                        answer = stat_result.stdout.strip()
                        if stat_result.returncode == 0 and answer.isdecimal():
                            value = int(answer)
                            if value > 1 and value != last_pid:
                                pid = value
                                break
                    time.sleep(.10)
                self.assertIsNotNone(pid, 'manager did not restart independent worker')
                # Confirm each newly launched interpreter actually rereads the
                # SAME durable job and does not claim a kernel cleanup.
                observed = False
                until = time.monotonic() + 5
                while time.monotonic() < until:
                    if out.exists():
                        try:
                            lines = [json.loads(line) for line in out.read_text().splitlines()]
                        except json.JSONDecodeError:
                            lines = []
                        observed = any(v.get('service_pid') == pid
                                       and v.get('status') == 'INSPECTION_ONLY'
                                       and len(v.get('records', [])) == 1
                                       and v['records'][0].get('job_id') == jobid
                                       for v in lines)
                    if observed:
                        break
                    time.sleep(.10)
                self.assertTrue(observed, 'new interpreter did not inspect durable pending job')
                last_pid = pid
                if iteration < 2:
                    os.kill(pid, signal.SIGKILL)
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and out.exists() and out.stat().st_size == 0:
                time.sleep(.1)
            self.assertTrue(out.exists() and out.stat().st_size > 0)
            self.assertTrue(all(json.loads(line)['status'] == 'INSPECTION_ONLY'
                                for line in out.read_text().splitlines()))
        finally:
            if sock.exists():
                subprocess.run(['supervisorctl', '-c', str(conf), 'shutdown'],
                               capture_output=True, timeout=3)
            if manager.poll() is None:
                manager.terminate()
            try:
                manager.wait(timeout=4)
            except subprocess.TimeoutExpired:
                manager.kill()
                manager.wait(timeout=3)
