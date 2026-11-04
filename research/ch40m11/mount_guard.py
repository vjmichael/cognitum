"""Fail-closed CH40-M.11 Linux isolated executor (research prototype).

Precondition: caller already in fresh user + mount + NETWORK namespaces,
with parent UID remapped to namespace root, and NO_NEW_PRIVS enabled.
Constructs a private tmpfs root; binds only allowlisted read-only inputs and
writable worker state, chroots, then irreversibly drops all effective, permitted
and bounding capabilities, locks NOROOT securebits, and execs intended command.
This is not a general purpose sandbox; do not pass attacker-controlled policy.
"""
from __future__ import annotations
import argparse, ctypes, os, pathlib, resource, subprocess, sys

LIB=ctypes.CDLL(None,use_errno=True)
PR_SET_SECUREBITS=28; PR_CAPBSET_DROP=24; PR_SET_NO_NEW_PRIVS=38; PR_SET_DUMPABLE=4
CAP_VERSION_3=0x20080522
class CapHeader(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
class CapData(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]

def check_prctl(op,*args):
    if LIB.prctl(op,*args)!=0: raise OSError(ctypes.get_errno(),f'prctl {op} failed')

def run(cmd):
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)

def bind(src,dst,readonly):
    src=pathlib.Path(src).resolve(strict=True)
    dst=pathlib.Path(dst)
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():dst.mkdir(exist_ok=True)
    else:dst.touch(exist_ok=True)
    run(['/usr/bin/mount','--bind',str(src),str(dst)])
    if readonly:run(['/usr/bin/mount','-o','remount,bind,ro',str(dst)])

def drop_caps(maxcap):
    # Deny setuid and root privilege restoration; lock securebits before losing CAP_SETPCAP.
    check_prctl(PR_SET_SECUREBITS,1|2|4|8)
    for cap in range(maxcap+1):check_prctl(PR_CAPBSET_DROP,cap)
    hdr=CapHeader(CAP_VERSION_3,0);data=(CapData*2)()
    ret=LIB.syscall(126,ctypes.byref(hdr),ctypes.byref(data))
    if ret!=0:raise OSError(ctypes.get_errno(),'capset zero failed')
    check_prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)
    check_prctl(PR_SET_DUMPABLE,0)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--root',required=True)
    a.add_argument('--max-as-mib',type=int,default=2048)
    a.add_argument('--max-cpu-sec',type=int,default=90)
    a.add_argument('--ro',action='append',default=[])
    a.add_argument('--rw',action='append',default=[])
    a.add_argument('command',nargs=argparse.REMAINDER)
    x=a.parse_args()
    if not x.command or x.command[0]!='--' or len(x.command)<2:raise RuntimeError('explicit -- command required')
    if not pathlib.Path('/proc/self/uid_map').read_text().strip().startswith('0 '):raise RuntimeError('user namespace UID map missing')
    if not pathlib.Path('/proc/self/ns/net').exists():raise RuntimeError('network namespace missing')
    maxcap=int(pathlib.Path('/proc/sys/kernel/cap_last_cap').read_text())
    base=pathlib.Path(x.root).resolve(strict=True)
    run(['/usr/bin/mount','-t','tmpfs','-o','size=64m,nosuid,nodev','tmpfs',str(base)])
    (base/'tmp').mkdir(mode=0o1777)
    (base/'mnt/data').mkdir(parents=True)
    (base/'dev').mkdir()
    for link,target in [('bin','usr/bin'),('sbin','usr/sbin'),('lib','usr/lib'),('lib64','usr/lib64')]:
        (base/link).symlink_to(target)
    standard=['/usr','/opt/pyvenv','/dev/null','/dev/urandom']
    for src in standard+x.ro:bind(src,base/src.lstrip('/'),True)
    for src in x.rw:
        if any(src==s or src.startswith(s+'/') for s in standard+x.ro):
            raise RuntimeError('writable path overlaps readonly mount')
        bind(src,base/src.lstrip('/'),False)
    # Do not retain a directory descriptor to the original root.
    os.chdir(str(base));os.chroot('.');os.chdir('/')
    drop_caps(maxcap)
    if not 64<=x.max_as_mib<=4096 or not 1<=x.max_cpu_sec<=360:raise RuntimeError('resource limits outside reviewed range')
    resource.setrlimit(resource.RLIMIT_AS,(x.max_as_mib*1048576,x.max_as_mib*1048576))
    resource.setrlimit(resource.RLIMIT_CPU,(x.max_cpu_sec,x.max_cpu_sec+1))
    resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
    print('M11_ISOLATED: user+network+mount namespaces; private chroot; immutable readonly binds; zero capabilities; no_new_privs',flush=True)
    os.execv(x.command[1],x.command[1:])
if __name__=='__main__':main()
