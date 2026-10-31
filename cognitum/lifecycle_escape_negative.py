"""P49: fixed Linux breakaway negative control, NOT production sandboxing.

Demonstrates that killing one process group does not contain descendants that
create a new session. The fixture uses pidfds for identity-stable cleanup and
Linux child-subreaper behavior to reap adopted processes. Not a P46 test.
"""
from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

from .reference_lifecycle import _line, _reap, _subreaper

SCHEMA = 'cognitum.lifecycle.breakaway-negative.v1'

CHILD = r'''
import os, sys, time
print('READY', flush=True)
# Remain in supervisor's process group until the observer has a pidfd.
if os.read(0, 1) != b'G': sys.exit(71)
if sys.argv[1] == 'breakaway': os.setsid()
print('GROUP', os.getpgrp(), flush=True)
while True: time.sleep(.1)
'''

SUPERVISOR = r'''
import os, subprocess, sys, time
code = sys.argv[1]
breakaway = sys.argv[2] == 'breakaway'
p = subprocess.Popen([sys.executable, '-u', '-c', code, sys.argv[2]],
                     start_new_session=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, bufsize=0)
print('CHILD', p.pid, flush=True)
if p.stdout.readline() != b'READY\n': sys.exit(70)
print('BARRIER', flush=True)
# Observer must own pidfd before releasing this child to call setsid.
if os.read(0, 1) != b'G': sys.exit(71)
p.stdin.write(b'G'); p.stdin.flush()
group = p.stdout.readline().decode('ascii', 'replace').strip()
print(group, flush=True)
while True: time.sleep(.1)
'''


def _exited(pidfd: int, timeout_ms: int) -> bool:
    """The pidfd tracks the exact process, not a potentially recycled PID."""
    poller = select.poll()
    poller.register(pidfd, select.POLLIN | select.POLLHUP)
    return bool(poller.poll(timeout_ms))


def run_negative_control(*, breakaway: bool = True) -> dict:
    """Run fixed reference processes only, ensure child cleanup on all paths.

    boundary_gap_observed is expected True only for breakaway=True.
    That is a *negative* control, never a positive containment assurance.
    """
    if not sys.platform.startswith('linux') or not Path('/proc').is_dir():
        raise RuntimeError('Linux /proc required')
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Linux pidfd support required for this negative control')
    _subreaper()
    proc = None
    pidfd = None
    child_pid = 0
    observed = False
    exited_after_group_kill = False
    cleaned = False
    reaped_child = False
    child_group_matches = None
    try:
        proc = subprocess.Popen(
            [sys.executable, '-u', '-c', SUPERVISOR, CHILD,
             'breakaway' if breakaway else 'ingroup'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, bufsize=0,
        )
        first = _line(proc)
        if not first.startswith('CHILD ') or not first[6:].isdigit():
            raise RuntimeError('Supervisor failed to report child PID')
        child_pid = int(first[6:])
        pidfd = os.pidfd_open(child_pid)
        if _line(proc) != 'BARRIER':
            raise RuntimeError('Supervisor/child readiness barrier failed')
        if proc.stdin is None:
            raise RuntimeError('Supervisor handshake stdin missing')
        proc.stdin.write(b'G')
        proc.stdin.flush()
        result = _line(proc)
        if not result.startswith('GROUP ') or not result[6:].isdigit():
            raise RuntimeError('Child never announced group transition')
        child_group_matches = (os.getpgid(child_pid) == proc.pid)
        if child_group_matches == breakaway:
            raise RuntimeError('Unexpected child process-group identity')
        observed = True
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)
        # Wait for group-kill fallout. A breakaway child is expected to remain
        # runnable; an in-group child should exit and become waitable.
        exited_after_group_kill = _exited(pidfd, 350)
        if exited_after_group_kill:
            waited, _ = _reap(child_pid, 3)
            reaped_child = waited
    finally:
        # Do not rely on a bare PID for kill: a PID can be recycled. The pidfd
        # pins the identity of the exact observed child throughout cleanup.
        if pidfd is not None:
            if not _exited(pidfd, 0):
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            if not reaped_child:
                reaped_child, _ = _reap(child_pid, 3)
            cleaned = reaped_child and _exited(pidfd, 100)
            os.close(pidfd)
        if proc is not None:
            if proc.poll() is None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=3)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
    gap = bool(observed and breakaway and not exited_after_group_kill)
    return {
        'schema': SCHEMA,
        'platform': 'linux',
        'probe': 'breakaway-setsid-group-kill-negative-control',
        'expected_breakaway': breakaway,
        'child_group_matches_supervisor': child_group_matches,
        'observed': observed,
        'child_survived_group_kill': bool(observed and not exited_after_group_kill),
        'boundary_gap_observed': gap,
        'explicit_cleanup_reaped_child': cleaned,
        'qualification': 'local fixed-fixture negative control; NOT a sandbox or P46 test',
    }


if __name__ == '__main__':
    result = run_negative_control()
    print(json.dumps(result, sort_keys=True, indent=2))
    sys.exit(0 if result['boundary_gap_observed'] and result['explicit_cleanup_reaped_child'] else 1)
