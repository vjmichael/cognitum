"""P46R4 Linux native fixed-worker parent lifetime + release barrier.

Negative OS containment implications remain: no cgroup enforcement or Lu host
authorization are tested by this file. All children are disposable and reaped.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from cognitum import gated_alpha_worker as gate
from cognitum import cgroup2_fixed_runner as runner
from cognitum import cgroup2_contract as cgroup

ROOT = Path(__file__).resolve().parent.parent
SUPERVISOR = r'''
import os, select, signal, struct, subprocess, sys, time
root=sys.argv[1]; mode=sys.argv[2]
release_reader,release_writer=os.pipe2(os.O_CLOEXEC)
cmd=[sys.executable,'-m','cognitum.gated_alpha_worker',str(release_reader),str(os.getpid())]
p=subprocess.Popen(cmd, pass_fds=(release_reader,), cwd=root, stdin=subprocess.PIPE,
                   stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,bufsize=0,
                   start_new_session=True)
os.close(release_reader)
print('CHILD',p.pid,flush=True)
if mode=='pre-release':
    print('BARRIER',flush=True)
    time.sleep(30)
    sys.exit(99)
if mode in ('released-blocked', 'released-blocked-inherited-writer'):
    os.write(release_writer,b'G')
    os.close(release_writer)
    # The actual worker reads a length header and blocks on unfinished body.
    p.stdin.write(struct.pack('>I',100)+b'x')
    p.stdin.flush()
    deadline=time.monotonic()+5
    found=False
    while time.monotonic()<deadline:
        try:
            with open(f'/proc/{p.pid}/cmdline','rb') as src:
                found=b'cognitum.alpha_native_worker' in src.read()
        except FileNotFoundError: pass
        if found: break
        time.sleep(.01)
    if not found: print('NOT_EXECUTED',flush=True);sys.exit(97)
    if len(sys.argv)>2 and mode=='released-blocked-inherited-writer':
        fd=os.dup(p.stdin.fileno())
        holder=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],
                                pass_fds=(fd,),start_new_session=True,
                                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        os.close(fd)
        print('HOLDER',holder.pid,flush=True)
    print('REAL_WORKER_BLOCKED',flush=True)
    time.sleep(30)
    sys.exit(99)
print('BAD_MODE',flush=True)
'''


def _line(pipe, timeout=6):
    # Uses binary unbuffered pipe; never use this helper with arbitrary output.
    if not select.select([pipe], [], [], timeout)[0]:
        raise TimeoutError('supervisor handshake')
    return pipe.readline(100).decode('ascii').strip()


def _subreaper():
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0:
        raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER failed')


def death_observation(mode):
    """Observe a real worker exit by waitpid; identity-stable fail cleanup."""
    _subreaper()
    parent=subprocess.Popen([sys.executable,'-u','-c',SUPERVISOR,str(ROOT),mode],
                             cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
    child=0
    pidfd=None
    holder=0
    holder_fd=None
    reaped=False
    try:
        assert parent.stdout is not None
        hello=_line(parent.stdout)
        if not hello.startswith('CHILD ') or not hello[6:].isdigit():
            raise AssertionError('Child process identity not provided')
        child=int(hello[6:])
        pidfd=os.pidfd_open(child)
        expected='BARRIER' if mode=='pre-release' else 'REAL_WORKER_BLOCKED'
        if mode=='released-blocked-inherited-writer':
            holder_line=_line(parent.stdout)
            if not holder_line.startswith('HOLDER ') or not holder_line[7:].isdigit():
                raise AssertionError('Holder identity missing')
            holder=int(holder_line[7:])
            holder_fd=os.pidfd_open(holder)
        assert _line(parent.stdout)==expected
        os.killpg(parent.pid,signal.SIGKILL)
        parent.wait(timeout=4)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                waited,status=os.waitpid(child,os.WNOHANG)
            except ChildProcessError as exc:
                raise AssertionError('Expected observer adoption of worker') from exc
            if waited == child:
                reaped=True
                survived=False
                if holder_fd is not None:
                    watcher=select.poll();watcher.register(holder_fd,select.POLLIN|select.POLLHUP)
                    survived=not bool(watcher.poll(0))
                return {'reaped':True,'exit_code':os.waitstatus_to_exitcode(status),
                        'worker_pid':child,'holder_survived':survived}
            time.sleep(.02)
        return {'reaped':False, 'exit_code':None,'worker_pid':child}
    finally:
        if parent.poll() is None:
            try: os.killpg(parent.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        parent.wait(timeout=4)
        if pidfd is not None:
            if not reaped:
                poll=select.poll();poll.register(pidfd,select.POLLIN|select.POLLHUP)
                if not poll.poll(0):
                    signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                try: os.waitpid(child,0)
                except ChildProcessError: pass
            os.close(pidfd)
        if holder_fd is not None:
            watcher=select.poll();watcher.register(holder_fd,select.POLLIN|select.POLLHUP)
            if not watcher.poll(0):
                signal.pidfd_send_signal(holder_fd,signal.SIGKILL)
            try: os.waitpid(holder,0)
            except ChildProcessError: pass
            os.close(holder_fd)
        for s in (parent.stdout,parent.stderr):
            if s: s.close()


@unittest.skipUnless(sys.platform.startswith('linux') and hasattr(os,'pidfd_open'),
                     'Linux pidfd process observer required')
class P46R4ParentDeathWorkerGate(unittest.TestCase):
    def test_guard_requires_linux_valid_expected_parent(self):
        self.assertFalse(gate.arm_parent_death_sigkill(0))
        self.assertFalse(gate.arm_parent_death_sigkill(True))
        self.assertFalse(gate.arm_parent_death_sigkill(1))

    def test_cli_rejects_missing_expected_parent(self):
        proc=subprocess.run([sys.executable,'-m','cognitum.gated_alpha_worker','19'],
                            cwd=ROOT,capture_output=True,timeout=5)
        self.assertEqual(proc.returncode,79)

    def test_wrong_parent_identity_never_releases(self):
        rd,wr=os.pipe2(os.O_CLOEXEC)
        try:
            p=subprocess.Popen([sys.executable,'-m','cognitum.gated_alpha_worker',str(rd),str(os.getpid()+100000)],
                               cwd=ROOT,pass_fds=(rd,),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               start_new_session=True,bufsize=0)
            os.close(rd);rd=-1
            out,err=p.communicate(timeout=5)
            self.assertEqual((p.returncode,out,err),(80,b'',b''))
        finally:
            if rd!=-1: os.close(rd)
            os.close(wr)
            if 'p' in locals():
                if p.poll() is None: p.kill()
                p.wait(timeout=5)

    def test_supervisor_death_before_release_kills_worker(self):
        record=death_observation('pre-release')
        self.assertTrue(record['reaped'],record)
        self.assertIn(record['exit_code'],[-signal.SIGKILL,80],record)

    def test_supervisor_death_after_exec_kills_real_worker(self):
        record=death_observation('released-blocked')
        self.assertTrue(record['reaped'],record)
        self.assertEqual(record['exit_code'],-signal.SIGKILL,record)

    def test_cgroup_readonly_denial_precedes_guard_spawn(self):
        if cgroup.preflight().reason!='CGROUP2_READ_ONLY':
            self.skipTest('This observation assumes read-only real cgroup2 mount')
        with patch.object(runner.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(cgroup.ContainmentUnavailable,'CGROUP2_READ_ONLY'):
                runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00')
            spawn.assert_not_called()

    def test_parent_death_kills_real_worker_even_if_pipe_writer_survives(self):
        record=death_observation('released-blocked-inherited-writer')
        self.assertTrue(record['reaped'],record)
        self.assertTrue(record['holder_survived'],record)
        self.assertEqual(record['exit_code'],-signal.SIGKILL,record)


if __name__ == '__main__': unittest.main()
