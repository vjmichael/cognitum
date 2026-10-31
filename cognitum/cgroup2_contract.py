"""Experimental Cognitum test-host cgroup v2 scope, NOT an authorization system.

Host-owned cgroup scopes can kill an entire cgroup, including descendants that
call setsid(). This contract must fail closed where delegation is unavailable.
Never treat successful scope creation as proof of filesystem/network isolation,
permission authorization, or a complete sandbox for untrusted extensions.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import stat
import time


class ContainmentUnavailable(RuntimeError):
    """No demonstrably usable cgroup v2 scope: no worker execution allowed."""


@dataclass(frozen=True)
class CgroupPreflight:
    admitted_for_fixture: bool
    reason: str
    root: str
    kernel_cgroup2: bool
    writable: bool
    scope_kill_supported: bool


def _mount_entries():
    with open('/proc/self/mountinfo', encoding='utf-8') as src:
        for line in src:
            pre, marker, post = line.partition(' - ')
            if marker and post.split()[0] == 'cgroup2':
                parts = pre.split()
                if len(parts) >= 5:
                    yield Path(parts[4]).resolve()


def preflight(root: str | Path = '/sys/fs/cgroup') -> CgroupPreflight:
    """Reject read-only, fake/symlinked, and undelegated cgroup hierarchies.

    A PASS here only permits a *fixed trusted fixture* to attempt a cgroup
    test; it never approves arbitrary code or an untrusted plugin.
    """
    p = Path(root)
    displayed = str(p)
    if os.name != 'posix' or not Path('/proc/self/mountinfo').exists():
        return CgroupPreflight(False, 'NOT_LINUX', displayed, False, False, False)
    if p.is_symlink():
        return CgroupPreflight(False, 'SYMLINK_ROOT', displayed, False, False, False)
    try:
        resolved = p.resolve(strict=True)
        mounts = list(_mount_entries())
        native = any(resolved == m or m in resolved.parents for m in mounts)
        if not native:
            return CgroupPreflight(False, 'NOT_CGROUP2', displayed, False, False, False)
        if not (resolved / 'cgroup.procs').is_file():
            return CgroupPreflight(False, 'NO_CGROUP_PROCS', displayed, True, False, False)
        kill_file = resolved / 'cgroup.kill'
        kill_supported = kill_file.is_file()
        writable = not bool(os.statvfs(resolved).f_flag & getattr(os, 'ST_RDONLY', 1))
        if not writable:
            reason = 'CGROUP2_READ_ONLY'
        elif not (os.access(resolved, os.W_OK | os.X_OK)):
            reason = 'NO_DELEGATION'
        elif not kill_supported:
            reason = 'NO_CGROUP_KILL'
        else:
            reason = 'FIXTURE_SCOPE_POSSIBLE_NOT_OS_SANDBOX'
        return CgroupPreflight(reason.startswith('FIXTURE_'), reason, displayed,
                               True, writable, kill_supported)
    except OSError:
        return CgroupPreflight(False, 'CGROUP_PREFLIGHT_ERROR', displayed, False, False, False)


class FixtureCgroupScope:
    """Host-only Linux cgroup v2 scope; restrict to fixed test executables.

    This class owns no authority to run arbitrary worker code. The caller MUST
    use a launch barrier and attach a PID before releasing the fixed worker.
    A production supervisor additionally needs native host identity, reserved
    delegation and worker inability to migrate out or modify the cgroup mount.
    """

    def __init__(self, root: str | Path = '/sys/fs/cgroup'):
        self.root = Path(root).resolve()
        self.path: Path | None = None

    def create(self) -> None:
        check = preflight(self.root)
        if not check.admitted_for_fixture:
            raise ContainmentUnavailable(check.reason)
        if self.path is not None:
            raise RuntimeError('SCOPE_ALREADY_CREATED')
        # Only the trusted host generates scope names. Never accept a model path.
        scope = self.root / ('cognitum-fixture-' + secrets.token_hex(12))
        try:
            os.mkdir(scope, 0o700)
        except OSError as exc:
            raise ContainmentUnavailable('SCOPE_CREATE_FAILED') from exc
        self.path = scope
        try:
            if not (scope / 'cgroup.kill').is_file():
                raise ContainmentUnavailable('SCOPE_KILL_MISSING')
        except BaseException:
            try: os.rmdir(scope)
            except OSError: pass
            self.path = None
            raise

    def attach_before_release(self, pid: int) -> None:
        if self.path is None:
            raise ContainmentUnavailable('NO_SCOPE')
        if type(pid) is not int or pid <= 1:
            raise ContainmentUnavailable('INVALID_PID')
        # No shell, no cgroup.procs path from a model, no admission on an
        # apparently successful write alone: read back membership from kernel.
        flags = os.O_WRONLY | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
        try:
            fd = os.open(self.path / 'cgroup.procs', flags)
            try: os.write(fd, str(pid).encode('ascii'))
            finally: os.close(fd)
            if pid not in self.members():
                raise ContainmentUnavailable('ATTACH_NOT_OBSERVED')
        except OSError as exc:
            raise ContainmentUnavailable('CGROUP_ATTACH_FAILED') from exc

    def members(self) -> set[int]:
        if self.path is None:
            return set()
        data = (self.path / 'cgroup.procs').read_text(encoding='ascii')
        return {int(s) for s in data.split()}

    def kill_and_verify_empty(self, timeout: float = 5.0) -> bool:
        """Kernel cgroup.kill catches descendant setsid breakaways in scope.

        Returns False, never success, if populated never reaches zero. Caller
        must independently reap its own direct worker process with waitpid.
        """
        if self.path is None:
            raise ContainmentUnavailable('NO_SCOPE')
        try:
            with open(self.path / 'cgroup.kill', 'w', encoding='ascii') as f:
                f.write('1')
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                fields = dict(line.split() for line in
                              (self.path / 'cgroup.events').read_text().splitlines())
                if fields.get('populated') == '0' and not self.members():
                    return True
                time.sleep(.02)
            return False
        except OSError:
            return False

    def remove_empty(self) -> None:
        if self.path is not None:
            os.rmdir(self.path)   # Refuse to hide still-populated scopes.
            self.path = None

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, typ, val, tb):
        if self.path is not None:
            self.kill_and_verify_empty()
            try: self.remove_empty()
            except OSError: pass
