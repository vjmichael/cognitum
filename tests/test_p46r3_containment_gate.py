"""P46R3 integration readiness, negative controls, and identity-stable fail closed."""
from __future__ import annotations

import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch, Mock

from cognitum import gated_alpha_worker as gate
from cognitum import cgroup2_contract as scope
from cognitum import cgroup2_fixed_runner as runner
from cognitum.alpha_native import make_call, _parse
from cognitum.proto import alpha_native_pb2 as proto
from cognitum.proto.capability_pb2 import CalculateRationalResult

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux-only fixed-worker gate')
class FixedReleaseBarrier(unittest.TestCase):
    def test_exact_single_byte_then_eof(self):
        rd, wr = os.pipe()
        try:
            os.write(wr, b'G')
            os.close(wr); wr = -1
            self.assertTrue(gate.read_release_token(rd, .2))
        finally:
            os.close(rd)
            if wr != -1: os.close(wr)

    def test_bad_tokens_denied(self):
        for raw in (b'', b'X', b'GG', b'GX', b'G\n'):
            with self.subTest(raw=raw):
                rd, wr = os.pipe()
                try:
                    if raw: os.write(wr, raw)
                    os.close(wr); wr = -1
                    self.assertFalse(gate.read_release_token(rd, .2))
                finally:
                    os.close(rd)
                    if wr != -1: os.close(wr)

    def test_inherited_writer_prevents_release(self):
        rd, wr = os.pipe()
        try:
            os.write(wr, b'G')
            start = time.monotonic()
            self.assertFalse(gate.read_release_token(rd, .12))
            self.assertLess(time.monotonic()-start, .8)
        finally:
            os.close(rd); os.close(wr)

    def test_no_token_reaches_deadline(self):
        rd, wr = os.pipe()
        try:
            self.assertFalse(gate.read_release_token(rd, .08))
        finally:
            os.close(rd); os.close(wr)

    def test_invalid_fds_or_timeouts_denied(self):
        for fd, timeout in ((0,.1),(-1,.1),(3,0),(3,31.0),(3,-2),(3,float('inf'))):
            with self.subTest(fd=fd,timeout=timeout):
                self.assertFalse(gate.read_release_token(fd,timeout))

    def test_real_protobuf_worker_executes_on_correct_gate_only(self):
        rd, wr = os.pipe2(os.O_CLOEXEC)
        p = None
        try:
            p = subprocess.Popen([sys.executable,'-m','cognitum.gated_alpha_worker',str(rd)],
                                 pass_fds=(rd,),cwd=ROOT,start_new_session=True,
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,bufsize=0)
            os.close(rd); rd = -1
            call = make_call('p46r3','1/3 + 1/6')
            os.write(wr,b'G'); os.close(wr);wr=-1
            stdout,stderr=p.communicate(struct.pack('>I',len(call))+call,timeout=6)
            self.assertEqual((p.returncode,stderr),(0,b''))
            self.assertEqual(len(stdout)-4,struct.unpack('>I',stdout[:4])[0])
            result=_parse(proto.Reply,stdout[4:],16384)
            self.assertEqual(CalculateRationalResult.FromString(result.result_payload).value,'1/2')
            self.assertFalse(result.lu_integrated or result.os_isolation_verified)
        finally:
            if rd!=-1:os.close(rd)
            if wr!=-1:os.close(wr)
            if p is not None:
                if p.poll() is None: p.kill()
                p.communicate(timeout=6)

    def test_real_worker_extra_byte_never_executes(self):
        rd, wr = os.pipe2(os.O_CLOEXEC)
        p = None
        try:
            p = subprocess.Popen([sys.executable,'-m','cognitum.gated_alpha_worker',str(rd)],
                                 pass_fds=(rd,),cwd=ROOT,start_new_session=True,
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,bufsize=0)
            os.close(rd); rd = -1
            os.write(wr,b'GX'); os.close(wr);wr=-1
            stdout,stderr=p.communicate(timeout=6)
            self.assertEqual((p.returncode,stdout,stderr),(78,b'',b''))
        finally:
            if rd!=-1:os.close(rd)
            if wr!=-1:os.close(wr)
            if p is not None:
                if p.poll() is None:p.kill()
                p.communicate(timeout=6)


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux-only kernel cgroup')
class KernelPreflightAndIdentity(unittest.TestCase):
    def test_real_mount_is_read_only_and_rejects_before_process_spawn(self):
        check=scope.preflight()
        if not os.statvfs('/sys/fs/cgroup').f_flag & getattr(os,'ST_RDONLY',1):
            self.skipTest('This denial assertion requires read-only cgroup mount')
        self.assertEqual(check.reason,'CGROUP2_READ_ONLY')
        self.assertFalse(check.admitted_for_fixture)
        with patch.object(runner.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(scope.ContainmentUnavailable,'READ_ONLY'):
                runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00')
            spawn.assert_not_called()

    def test_forged_cgroup_files_do_not_admit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for f in ('cgroup.procs','cgroup.kill','cgroup.events'):(root/f).write_text('')
            self.assertEqual(scope.preflight(root).reason,'NOT_CGROUP2')
            with patch.object(runner.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(scope.ContainmentUnavailable,'NOT_CGROUP2'):
                    runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00',delegated_root=root)
                spawn.assert_not_called()

    def test_preflight_read_only_rejects_even_when_permission_mocked(self):
        with patch.object(scope.os,'access',return_value=True):
            self.assertFalse(scope.preflight().admitted_for_fixture)

    def test_missing_membership_cannot_release(self):
        proc=Mock(pid=12345)
        target=Mock()
        target.members.return_value=set()
        with self.assertRaisesRegex(scope.ContainmentUnavailable,'WORKER_NOT_IN_KERNEL_CGROUP'):
            runner._require_same_attached_worker(proc,44,33,target)

    def test_pid_identity_change_is_rejected(self):
        proc=Mock(pid=12345)
        proc.poll.return_value=None
        target=Mock();target.members.return_value={12345}
        with patch.object(runner,'_birth_ticks',return_value=34),patch.object(runner,'_pidfd_exited',return_value=False):
            with self.assertRaisesRegex(scope.ContainmentUnavailable,'IDENTITY_CHANGED'):
                runner._require_same_attached_worker(proc,44,33,target)

    def test_dead_pidfd_cannot_release(self):
        proc=Mock(pid=12345);proc.poll.return_value=None
        target=Mock();target.members.return_value={12345}
        with patch.object(runner,'_birth_ticks',return_value=33),patch.object(runner,'_pidfd_exited',return_value=True):
            with self.assertRaisesRegex(scope.ContainmentUnavailable,'IDENTITY_CHANGED'):
                runner._require_same_attached_worker(proc,44,33,target)

    def test_dead_worker_cannot_release_even_when_pidfd_not_signaled(self):
        proc=Mock(pid=12345);proc.poll.return_value=-9
        target=Mock();target.members.return_value={12345}
        with patch.object(runner,'_birth_ticks',return_value=33),patch.object(runner,'_pidfd_exited',return_value=False):
            with self.assertRaisesRegex(scope.ContainmentUnavailable,'IDENTITY_CHANGED'):
                runner._require_same_attached_worker(proc,44,33,target)

    def test_unreadable_proc_identity_denied(self):
        proc=Mock(pid=12345);proc.poll.return_value=None
        target=Mock();target.members.return_value={12345}
        with patch.object(runner,'_birth_ticks',side_effect=FileNotFoundError()),patch.object(runner,'_pidfd_exited',return_value=False):
            with self.assertRaisesRegex(scope.ContainmentUnavailable,'IDENTITY_CHANGED'):
                runner._require_same_attached_worker(proc,44,33,target)

    def test_observed_identical_alive_process_can_be_released_in_mock_only(self):
        proc=Mock(pid=12345);proc.poll.return_value=None
        target=Mock();target.members.return_value={12345}
        with patch.object(runner,'_birth_ticks',return_value=33),patch.object(runner,'_pidfd_exited',return_value=False):
            runner._require_same_attached_worker(proc,44,33,target)
        # This is a logical pre-release check, NOT kernel containment evidence.

    def test_failed_scope_cleanup_is_never_success(self):
        fake=scope.FixtureCgroupScope()
        fake.path=Path('/nonexistent/cognitum-test-scope')
        self.assertFalse(fake.kill_and_verify_empty(timeout=.01))


if __name__=='__main__':unittest.main()
