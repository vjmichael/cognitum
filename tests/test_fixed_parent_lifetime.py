"""Rebuilt P46 behavior tests (NOT the historical P46 source or 764-test suite)."""
import ctypes
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import time
import unittest

from cognitum.alpha_native import make_call, _parse
from cognitum.proto import alpha_native_pb2 as proto
from cognitum.proto.capability_pb2 import CalculateRationalResult
from cognitum.fixed_parent_lifetime import enter_fixed_worker, main

ROOT = Path(__file__).resolve().parent.parent
PARENT_CODE = '''
import os, subprocess, sys, time, struct
rel_r,rel_w=os.pipe()
ready_r,ready_w=os.pipe()
p=subprocess.Popen([sys.executable,'-m','cognitum.fixed_parent_lifetime',str(os.getpid()),str(rel_r),str(ready_w)], cwd=sys.argv[1],pass_fds=(rel_r,ready_w),start_new_session=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
os.close(rel_r);os.close(ready_w)
print('CHILD',p.pid,flush=True)
mode=sys.argv[2]
if mode=='pre-ready':
    # Observer kills us as soon as worker ID is published.
    time.sleep(20)
    sys.exit(90)
if os.read(ready_r,1)!=b'R':sys.exit(91)
print('READY',flush=True)
if mode=='pre-release':
    time.sleep(20)
    sys.exit(90)
os.write(rel_w,b'G');os.close(rel_w)
if mode=='blocked':
    p.stdin.write(struct.pack('>I',100)+b'x');p.stdin.flush()
    print('BLOCKED',flush=True)
    time.sleep(20)
    sys.exit(90)
print('ERROR_BAD_MODE',flush=True)
'''


def get_line(proc, timeout=5):
    assert proc.stdout is not None
    if not select.select([proc.stdout],[],[],timeout)[0]:
        raise TimeoutError('observer handshake')
    return proc.stdout.readline(96).decode().strip()


def observer_case(mode):
    libc = ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0:
        raise OSError(ctypes.get_errno(),'subreaper unavailable')
    parent=subprocess.Popen([sys.executable,'-u','-c',PARENT_CODE,str(ROOT),mode],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
    child=0
    pidfd=None
    reaped=False
    try:
        first=get_line(parent)
        if not first.startswith('CHILD ') or not first[6:].isdigit():
            raise AssertionError(first)
        child=int(first[6:])
        if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):
            raise unittest.SkipTest('Linux pidfd required for safe cleanup')
        pidfd=os.pidfd_open(child)
        if mode!='pre-ready':
            assert get_line(parent)=='READY'
        if mode=='blocked':
            assert get_line(parent)=='BLOCKED'
        os.kill(parent.pid,signal.SIGKILL)
        parent.wait(timeout=5)
        deadline=time.monotonic()+5
        status=None
        while time.monotonic()<deadline:
            try:
                waited,status=os.waitpid(child,os.WNOHANG)
            except ChildProcessError:
                raise AssertionError('child not adopted')
            if waited==child:
                reaped=True
                break
            time.sleep(.02)
        return reaped,os.waitstatus_to_exitcode(status) if reaped else None
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=5)
        if pidfd is not None:
            if not reaped:
                poller=select.poll();poller.register(pidfd, select.POLLIN|select.POLLHUP)
                if not poller.poll(0):
                    signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                try:os.waitpid(child,0)
                except ChildProcessError:pass
            os.close(pidfd)
        for stream in (parent.stdout,parent.stderr):
            if stream:stream.close()


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux only')
class ParentLifetimeReconstructionTests(unittest.TestCase):
    def test_invalid_identity_is_denied(self):
        self.assertEqual(enter_fixed_worker(1,4,5),76)
        self.assertEqual(main(['1','2']),76)
        self.assertEqual(main(['garbage','3','4']),76)

    def test_successful_fixed_worker_execution_with_parent_held(self):
        release_r,release_w=os.pipe()
        ready_r,ready_w=os.pipe()
        p=None
        try:
            p=subprocess.Popen([sys.executable,'-m','cognitum.fixed_parent_lifetime',str(os.getpid()),str(release_r),str(ready_w)],cwd=ROOT,pass_fds=(release_r,ready_w),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
            os.close(release_r);os.close(ready_w)
            self.assertEqual(os.read(ready_r,1),b'R')
            os.write(release_w,b'G')
            os.close(release_w)
            call=make_call('p46r','1/3 + 1/6')
            out,err=p.communicate(struct.pack('>I',len(call))+call,timeout=5)
            self.assertEqual(p.returncode,0,err)
            self.assertEqual(err,b'')
            n=struct.unpack('>I',out[:4])[0]
            reply=_parse(proto.Reply,out[4:],16384)
            self.assertEqual(n,len(out)-4)
            self.assertEqual(CalculateRationalResult.FromString(reply.result_payload).value,'1/2')
            self.assertFalse(reply.lu_integrated or reply.os_isolation_verified)
        finally:
            for fd in (release_r,ready_r,release_w,ready_w):
                try:os.close(fd)
                except OSError:pass
            if p is not None:
                if p.poll() is None:p.kill()
                p.wait(timeout=5)

    def test_wrong_parent_identity_does_not_release_or_exec(self):
        rel_r,rel_w=os.pipe();ready_r,ready_w=os.pipe()
        p=None
        try:
            p=subprocess.Popen([sys.executable,'-m','cognitum.fixed_parent_lifetime',str(os.getpid()+1000),str(rel_r),str(ready_w)],cwd=ROOT,pass_fds=(rel_r,ready_w),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
            os.close(rel_r);os.close(ready_w)
            stdout,stderr=p.communicate(timeout=5)
            self.assertEqual(p.returncode,78)
            self.assertEqual(stdout,b'')
            self.assertEqual(os.read(ready_r,1),b'')
        finally:
            for fd in (rel_r,rel_w,ready_r,ready_w):
                try:os.close(fd)
                except OSError:pass
            if p is not None:
                if p.poll() is None:p.kill()
                p.wait(timeout=5)

    def test_invalid_gate_token_never_executes_real_worker(self):
        rel_r,rel_w=os.pipe();ready_r,ready_w=os.pipe()
        p=None
        try:
            p=subprocess.Popen([sys.executable,'-m','cognitum.fixed_parent_lifetime',str(os.getpid()),str(rel_r),str(ready_w)],cwd=ROOT,pass_fds=(rel_r,ready_w),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
            os.close(rel_r);os.close(ready_w)
            self.assertEqual(os.read(ready_r,1),b'R')
            os.write(rel_w,b'X');os.close(rel_w)
            stdout,stderr=p.communicate(timeout=5)
            self.assertEqual(p.returncode,79)
            self.assertEqual(stdout,b'')
        finally:
            for fd in (rel_r,rel_w,ready_r,ready_w):
                try:os.close(fd)
                except OSError:pass
            if p is not None:
                if p.poll() is None:p.kill()
                p.wait(timeout=5)

    def test_parent_dies_before_worker_ready(self):
        reaped,code=observer_case('pre-ready')
        self.assertTrue(reaped)
        self.assertIn(code,(-signal.SIGKILL,78))

    def test_parent_dies_after_guard_before_release(self):
        reaped,code=observer_case('pre-release')
        self.assertTrue(reaped)
        self.assertEqual(code,-signal.SIGKILL)

    def test_parent_dies_with_actual_worker_blocked(self):
        reaped,code=observer_case('blocked')
        self.assertTrue(reaped)
        self.assertEqual(code,-signal.SIGKILL)


if __name__=='__main__':unittest.main()
