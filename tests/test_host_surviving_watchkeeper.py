"""P46R5: host crash monitor integration + fail-closed cgroup admission.

The local /sys/fs/cgroup mount is read-only: live kernel cgroup.kill
containment is intentionally NOT asserted by this suite.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from cognitum import host_surviving_watchkeeper as w
from cognitum import host_survivor_arm as arm
from cognitum import cgroup2_fixed_runner as runner
from cognitum.cgroup2_contract import ContainmentUnavailable

ROOT = Path(__file__).resolve().parent.parent
WATCHER_SCRIPT = r'''
import os, sys, json
from pathlib import Path
from cognitum.host_surviving_watchkeeper import monitor_parent, kill_and_observe
parent, lease_fd, ready_fd = (int(x) for x in sys.argv[1:4])
receipt = Path(sys.argv[4])
parentfd = os.pidfd_open(parent)
os.write(ready_fd, b'R')
os.close(ready_fd)
reason = monitor_parent(parentfd, lease_fd, timeout=10)
mock_written = mock_empty = False
if len(sys.argv) > 5:
    scopefd=os.open(sys.argv[5], os.O_RDONLY|os.O_DIRECTORY)
    mock_written,mock_empty=kill_and_observe(scopefd,timeout=.1,require_real_kernel=False)
    os.close(scopefd)
receipt.write_text(json.dumps({'trigger': reason, 'watcher_pid':os.getpid(),
    'simulated_kill_written':mock_written,'simulated_empty':mock_empty}))
os.close(parentfd)
os.close(lease_fd)
'''
HOST_SCRIPT = r'''
import os, subprocess, sys, time, select
lease_r, lease_w = os.pipe2(os.O_CLOEXEC)
ready_r, ready_w = os.pipe2(os.O_CLOEXEC)
watch = subprocess.Popen([sys.executable,'-u','-c',sys.argv[2],str(os.getpid()),str(lease_r),str(ready_w),sys.argv[1],sys.argv[3]],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    close_fds=True, pass_fds=(lease_r,ready_w), start_new_session=True)
# Intentionally retain another copy of the lease writer in a surviving child.
helper = subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],
    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
    close_fds=True,pass_fds=(lease_w,),start_new_session=True)
os.close(lease_r); os.close(ready_w)
print('BORN',watch.pid,helper.pid,flush=True)
if not select.select([ready_r],[],[],4)[0] or os.read(ready_r,1)!=b'R':
    print('FAILED_READY',flush=True);sys.exit(73)
print('READY',flush=True)
# Keep parent and another writer alive until observer kills this host.
time.sleep(30)
'''


def _get_line(p, timeout=5):
    assert p.stdout is not None
    if not select.select([p.stdout], [], [], timeout)[0]:
        raise RuntimeError('TIMEOUT_READING_HANDSHAKE')
    result = p.stdout.readline(100).decode('ascii', 'replace').strip()
    if not result:
        raise RuntimeError('EOF_READING_HANDSHAKE')
    return result


def _pidfd_exited(fd, timeout_ms=3000):
    p=select.poll();p.register(fd,select.POLLIN|select.POLLHUP)
    return bool(p.poll(timeout_ms))


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux-only')
class LinuxWatcherTests(unittest.TestCase):
    def test_actual_kernel_readonly_prevents_all_spawn(self):
        if not os.statvfs('/sys/fs/cgroup').f_flag & getattr(os, 'ST_RDONLY', 1):
            self.skipTest('needs ro cgroup')
        with patch.object(runner.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ContainmentUnavailable, 'READ_ONLY'):
                runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00')
            spawn.assert_not_called()

    def test_fake_scope_never_arms_watcher(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/'cgroup.kill').write_text('')
            with patch.object(arm.subprocess,'Popen') as spawn:
                with self.assertRaisesRegex(w.WatchkeeperDenied,'NOT_KERNEL_CGROUP_SCOPE'):
                    arm.arm_watchkeeper(p)
                spawn.assert_not_called()

    def test_cgroup_kernel_fd_does_not_accept_fake_directory(self):
        with tempfile.TemporaryDirectory() as t:
            fd=os.open(t, os.O_RDONLY|os.O_DIRECTORY)
            try:self.assertFalse(w.kernel_cgroup_dirfd(fd))
            finally:os.close(fd)
        fd=os.open('/sys/fs/cgroup',os.O_RDONLY|os.O_DIRECTORY)
        try:self.assertTrue(w.kernel_cgroup_dirfd(fd))
        finally:os.close(fd)

    def test_mock_kernel_write_observes_empty_only_if_reported(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'cgroup.kill').write_text(''); (p/'cgroup.events').write_text('populated 0\nfrozen 0\n')
            fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
            try:
                self.assertEqual(w.kill_and_observe(fd,timeout=.1,require_real_kernel=False),(True,True))
                self.assertEqual((p/'cgroup.kill').read_text(),'1')
            finally: os.close(fd)
        # A MOCK directory does not qualify production kernel acceptance.

    def test_mock_populated_never_reports_cleared(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'cgroup.kill').write_text(''); (p/'cgroup.events').write_text('populated 1\n')
            fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
            try:self.assertEqual(w.kill_and_observe(fd,timeout=.06,require_real_kernel=False),(True,False))
            finally:os.close(fd)

    def test_mock_missing_or_duplicate_populated_fails_closed(self):
        for raw in ('frozen 0\n','populated 1\npopulated 0\n', 'populated XYZ\n'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as t:
                p=Path(t);(p/'cgroup.kill').write_text(''); (p/'cgroup.events').write_text(raw)
                fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
                try:self.assertEqual(w.kill_and_observe(fd,timeout=.05,require_real_kernel=False),(False,False))
                finally:os.close(fd)

    def test_atomic_receipt_cannot_replace_existing_job(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);os.chmod(p,0o700)
            fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
            try:
                w._write_receipt(fd,'a'*32,{'test':'first'})
                with self.assertRaises(FileExistsError):
                    w._write_receipt(fd,'a'*32,{'test':'second'})
                self.assertEqual(json.loads((p/('p46r5-'+ 'a'*32+'.json')).read_text()),{'test':'first'})
            finally:os.close(fd)

    def test_reject_world_readable_receipt_dir(self):
        with tempfile.TemporaryDirectory() as t:
            os.chmod(t,0o755)
            fd=os.open(t,os.O_RDONLY|os.O_DIRECTORY)
            try:
                with self.assertRaisesRegex(w.WatchkeeperDenied, 'UNTRUSTED_RECEIPT_DIRECTORY'):
                    w._write_receipt(fd, '0'*32, {'test':1})
            finally:os.close(fd)

    def test_host_receipt_requires_real_fields_and_no_duplicate_keys(self):
        self.assertEqual(arm._strict_receipt(b'{"a":1}')['a'],1)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            arm._strict_receipt(b'{"status":"OK","status":"FAIL"}')
        with self.assertRaisesRegex(ValueError, 'NON_FINITE'):
            arm._strict_receipt(b'{"value": NaN}')
        with self.assertRaises(ValueError):
            arm._strict_receipt(b'[]')

    def test_nonmatching_or_contradictory_receipt_denied(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            fake_proc=MagicMock(pid=1234);fake_proc.wait.return_value=0
            h=arm.ArmedWatchkeeper(fake_proc,-1,'c'*32,p,42,43)
            h.receipt_path.write_text(json.dumps({'schema':w.SCHEMA,'job_id':'c'*32,'watchkeeper_pid':1234,
                'trigger':'LEASE_CLOSED','status':'KERNEL_TREE_CLEARED','ready_before_trigger':True,
                'observed_parent_pid':os.getpid(), 'scope_device':42,'scope_inode':43,'elapsed_ms':10,
                'watchkeeper_survived_its_own_crash':False,
                'kernel_cgroup2_verified':True,'cgroup_kill_written':True,'subtree_empty':False,
                'production_authorized':False,'independent_attestation':False}))
            with self.assertRaisesRegex(w.WatchkeeperDenied,'CONTRADICTORY'):
                h.await_cleanup()

    def test_host_rejects_watchkeeper_receipt_from_wrong_scope_inode(self):
        with tempfile.TemporaryDirectory() as t:
            proc=MagicMock(pid=258);proc.wait.return_value=0
            h=arm.ArmedWatchkeeper(proc,-1,'e'*32,Path(t),42,43)
            d={'schema':w.SCHEMA,'job_id':'e'*32,'watchkeeper_pid':258,
               'observed_parent_pid':os.getpid(),'scope_device':42,'scope_inode':44,
               'trigger':'LEASE_CLOSED','ready_before_trigger':True,
               'kernel_cgroup2_verified':True,'cgroup_kill_written':True,
               'subtree_empty':True,'status':'KERNEL_TREE_CLEARED',
               'elapsed_ms':10,'production_authorized':False,
               'independent_attestation':False,
               'watchkeeper_survived_its_own_crash':False}
            h.receipt_path.write_text(json.dumps(d))
            with self.assertRaisesRegex(w.WatchkeeperDenied,'CONTRADICTORY'):
                h.await_cleanup()
            d['scope_inode']=43
            h.receipt_path.write_text(json.dumps(d))
            self.assertEqual(h.await_cleanup()['scope_inode'],43)

    def test_lease_close_monitor_returns_when_parent_still_alive(self):
        with tempfile.TemporaryDirectory() as t:
            receipt=str(Path(t)/'lease.json')
            rd,wr=os.pipe2(os.O_CLOEXEC); ready_r,ready_w=os.pipe2(os.O_CLOEXEC)
            proc=None
            try:
                proc=subprocess.Popen([sys.executable,'-u','-c',WATCHER_SCRIPT,str(os.getpid()),str(rd),str(ready_w),receipt],
                    cwd=ROOT,pass_fds=(rd,ready_w),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,start_new_session=True)
                os.close(rd);rd=-1;os.close(ready_w);ready_w=-1
                self.assertEqual(os.read(ready_r,1),b'R')
                os.close(wr);wr=-1
                self.assertEqual(proc.wait(timeout=6),0)
                self.assertEqual(json.loads(Path(receipt).read_text())['trigger'],'LEASE_CLOSED')
            finally:
                for fd in (rd,wr,ready_r,ready_w):
                    if fd>=0:os.close(fd)
                if proc is not None:
                    if proc.poll() is None:proc.kill()
                    proc.wait(timeout=6)

    def test_watchkeeper_survives_host_sigkill_despite_inherited_lease(self):
        if not hasattr(signal,'pidfd_send_signal') or not hasattr(os,'pidfd_open'):
            self.skipTest('pidfd APIs required')
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.prctl(36,1,0,0,0)!=0:
            self.skipTest('subreaper not available')
        parent=None
        watch_pid=helper_pid=0
        watch_fd=helper_fd=-1
        watch_reaped=helper_reaped=False
        with tempfile.TemporaryDirectory() as t:
            receipt=Path(t)/'crash.json'
            mock_scope=Path(t)/'simulation'
            mock_scope.mkdir()
            (mock_scope/'cgroup.kill').write_text('')
            (mock_scope/'cgroup.events').write_text('populated 0\n')
            try:
                parent=subprocess.Popen([sys.executable,'-u','-c',HOST_SCRIPT,str(receipt),WATCHER_SCRIPT,str(mock_scope)],
                    cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    start_new_session=True,bufsize=0)
                first=_get_line(parent)
                values=first.split()
                self.assertEqual(len(values),3,first)
                self.assertEqual(values[0],'BORN',first)
                watch_pid,helper_pid=int(values[1]),int(values[2])
                watch_fd=os.pidfd_open(watch_pid);helper_fd=os.pidfd_open(helper_pid)
                self.assertEqual(_get_line(parent),'READY')
                parent.kill()  # Actual launching host is forcibly terminated.
                self.assertEqual(parent.wait(timeout=6),-signal.SIGKILL)
                deadline=time.monotonic()+6
                while time.monotonic()<deadline and not receipt.exists():
                    time.sleep(.02)
                self.assertTrue(receipt.exists(), 'watchkeeper failed to survive host death')
                result=json.loads(receipt.read_text())
                self.assertEqual(result['trigger'],'HOST_PIDFD_EXITED', result)
                self.assertEqual(result['watcher_pid'],watch_pid)
                self.assertTrue(result['simulated_kill_written'])
                self.assertTrue(result['simulated_empty'])
                self.assertEqual((mock_scope/'cgroup.kill').read_text(),'1')
                # The other lease holder is STILL ALIVE: EOF alone cannot do it.
                self.assertFalse(_pidfd_exited(helper_fd, 0))
                self.assertTrue(_pidfd_exited(watch_fd,3000))
                waited,status=os.waitpid(watch_pid,0)
                self.assertEqual(waited,watch_pid)
                self.assertEqual(os.waitstatus_to_exitcode(status),0)
                watch_reaped=True
            finally:
                if parent is not None:
                    if parent.poll() is None:parent.kill()
                    parent.wait(timeout=6)
                    for f in (parent.stdout,parent.stderr):
                        if f:f.close()
                for fd,pid,done in ((helper_fd,helper_pid,helper_reaped),
                                    (watch_fd,watch_pid,watch_reaped)):
                    if fd >= 0:
                        if not done:
                            if not _pidfd_exited(fd,0):
                                signal.pidfd_send_signal(fd,signal.SIGKILL)
                            if pid:
                                try:os.waitpid(pid,0)
                                except ChildProcessError:pass
                        os.close(fd)


if __name__=='__main__':unittest.main()
