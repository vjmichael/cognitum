"""Opt-in Linux OS namespace execution for reviewed pure Cognitum operations.

This is a fail-closed research containment milestone, NOT arbitrary untrusted
plugin execution. Supported only on Linux with working user, mount, PID, net,
IPC and UTS namespaces. No unsandboxed fallback, even on launch failure.
Never pass user input as executable arguments, module names, mount paths or
shell text. Data crosses the boundary as size-limited JSON over stdio.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

MAX_FRAME_BYTES = 262144
MAX_RESPONSE_BYTES = 65536
MAX_STDERR_BYTES = 4096
MAX_REQUEST_MS = 15000
_UNSHARE = '/usr/bin/unshare'
_SHELL = '/bin/sh'


class ContainmentUnavailable(RuntimeError):
    pass


class LinuxNamespaceExecutor:
    """Standalone one-shot namespace worker, no permission authority.

    Runtime does all schema, identity and grant checks before invoking this
    backend. Passing a factory by name is never sufficient: the trusted host
    must choose a concrete supported class and operation before execution.
    """

    def __init__(self, *, source_dir=None, approved_kan_sha256=None):
        if not sys.platform.startswith('linux'):
            raise ContainmentUnavailable('LINUX_ONLY')
        # source_dir is only allowed in test setups with explicitly trusted
        # host code. Production does not accept model-supplied filesystem paths.
        import re
        if approved_kan_sha256 is not None and (type(approved_kan_sha256) is not str or
                re.fullmatch(r'[0-9a-f]{64}', approved_kan_sha256) is None):
            raise ValueError('INVALID_TRUSTED_KAN_PIN')
        self.approved_kan_sha256 = approved_kan_sha256
        self.source_dir = Path(source_dir).resolve() if source_dir is not None else Path(__file__).resolve().parent
        # The trusted host chooses the Python installation/venv. Do not
        # hardcode a developer-machine path in the shipped worker.
        self.python_prefix = Path(sys.prefix).resolve()
        if not (self.python_prefix/'bin'/'python3').exists():
            raise ContainmentUnavailable('HOST_PYTHON_RUNTIME_UNAVAILABLE')
        self._entry = self.source_dir / 'sandbox_entry_linux.sh'
        self._child = self.source_dir / 'sandbox_child.py'
        if not self._entry.is_file() or not self._child.is_file():
            raise ContainmentUnavailable('SANDBOX_FILES_MISSING')
        if not os.path.isfile(_UNSHARE) or not os.path.isfile(_SHELL):
            raise ContainmentUnavailable('UNSHARE_NOT_AVAILABLE')

    def execute(self, factory, operation, payload, timeout_ms):
        # Only reviewed pure factory operations: no user-supplied Python code,
        # no generic importlib or arbitrary startup arguments.
        from .plugins.calculator import Calculator
        from .plugins.specialists import Specialists
        # Exact trusted Python objects, not attacker-forged __name__/__module__.
        approved = ((factory is Calculator and operation == 'calc.rational') or
                    (factory is Specialists and operation in
                     ('specialist.hdc','specialist.ssm','specialist.kan')))
        if not approved or (operation == 'specialist.kan' and self.approved_kan_sha256 is None):
            return 'unavailable', None
        # This accounts for Linux sandbox launches under the same host-wide
        # eight-cold-worker budget as P6. Never allow unbounded overflow.
        from .worker_budget import reserve_cold, release_cold
        if not reserve_cold():
            return 'overloaded', None
        try:
            return self._invoke('cognitum', operation, payload, timeout_ms)
        finally:
            release_cold()

    def test_probe(self, operation, *, timeout_ms=5000):
        """Trusted test harness only; never registered as a Cognitum tool."""
        if operation not in ('probe.isolation', 'probe.stall', 'probe.child', 'probe.flood'):
            raise ValueError('INVALID_PROBE')
        return self._invoke('test_probe', operation, {}, timeout_ms)

    @staticmethod
    def _terminate_group(process):
        try:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    @staticmethod
    def _exchange(process, request, timeout_s):
        """Bound both response and stderr; no unbounded communicate() use."""
        selector = selectors.DefaultSelector()
        outgoing = memoryview(request)
        stdout = bytearray()
        stderr = bytearray()
        deadline = time.monotonic() + timeout_s
        try:
            for name, fd in [('stdout', process.stdout), ('stderr', process.stderr)]:
                os.set_blocking(fd.fileno(), False)
                selector.register(fd, selectors.EVENT_READ, name)
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
            while selector.get_map():
                remain = deadline - time.monotonic()
                if remain <= 0:
                    return 'timed_out', None
                for key, _ in selector.select(min(remain, 0.25)):
                    fd, name = key.fileobj, key.data
                    try:
                        if name == 'stdin':
                            sent = os.write(fd.fileno(), outgoing[:8192])
                            outgoing = outgoing[sent:]
                            if not outgoing:
                                selector.unregister(fd)
                                fd.close()
                        else:
                            b = os.read(fd.fileno(), 8192)
                            if not b:
                                selector.unregister(fd)
                            elif name == 'stdout':
                                stdout.extend(b)
                                if len(stdout) > MAX_RESPONSE_BYTES:
                                    return 'error', None
                            else:
                                stderr.extend(b)
                                if len(stderr) > MAX_STDERR_BYTES:
                                    return 'error', None
                    except (BrokenPipeError, OSError, ValueError):
                        # A child that exits early without reading stdin must
                        # not block further drain of its error/exit data.
                        selector.unregister(fd)
                if process.poll() is not None and not selector.get_map():
                    break
            if process.wait(timeout=max(0.001, deadline-time.monotonic())) != 0:
                return 'unavailable', None
            try:
                def no_duplicates(pairs):
                    value = dict(pairs)
                    if len(value) != len(pairs):
                        raise ValueError('DUPLICATE_RESPONSE_FIELD')
                    return value
                obj = json.loads(stdout, object_pairs_hook=no_duplicates,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_RESPONSE')))
                if (type(obj) is not dict or set(obj) != {'status','result'} or
                    obj['status'] not in ('ok','invalid_input','error','unavailable')):
                    return 'error', None
                return obj['status'], obj['result']
            except (UnicodeDecodeError, ValueError, TypeError):
                return 'error', None
        except subprocess.TimeoutExpired:
            return 'timed_out', None
        finally:
            selector.close()

    def _invoke(self, kind, operation, payload, timeout_ms):
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= MAX_REQUEST_MS:
            return 'unavailable', None
        try:
            raw = json.dumps({'kind':kind,'operation':operation,'payload':payload},
                             allow_nan=False,separators=(',',':')).encode('ascii')
        except (TypeError, ValueError, OverflowError, UnicodeEncodeError):
            return 'invalid_input', None
        if len(raw) > MAX_FRAME_BYTES:
            return 'invalid_input', None
        tmp = tempfile.mkdtemp(prefix='cognitum-isolate-')
        proc = None
        try:
            os.chmod(tmp, 0o700)
            argv = [_UNSHARE,
                    '--user','--map-root-user','--mount','--pid','--ipc',
                    '--uts','--net','--fork','--kill-child',
                    _SHELL,str(self._entry), tmp, str(self.source_dir),
                    str(self.python_prefix)]
            # Deliberately scrub secrets, proxy settings, ambient PYTHONPATH,
            # imported key material and session env from the child.
            env = {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
                   'PYTHONDONTWRITEBYTECODE':'1','HOME':'/nonexistent'}
            if kind == 'cognitum' and operation == 'specialist.kan' and self.approved_kan_sha256:
                env['COGNITUM_TRUSTED_KAN_SHA256'] = self.approved_kan_sha256
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    close_fds=True, start_new_session=True, env=env)
            status, result = self._exchange(proc, raw, timeout_ms/1000)
            return status, result
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return 'unavailable', None
        finally:
            if proc is not None:
                self._terminate_group(proc)
                for file in (proc.stdin, proc.stdout, proc.stderr):
                    if file is not None:
                        file.close()
            shutil.rmtree(tmp, ignore_errors=True)
