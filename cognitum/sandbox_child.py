"""Fixed, JSON-only Cognitum Linux namespace worker. No dynamic imports from input.

The host selects a reviewed operation; caller-supplied Python class names or
paths are NEVER interpreted. This process has an ephemeral rootfs, no host
network, and no access to private user folders. It serves exactly ONE request.
"""
from __future__ import annotations

import json
import os
import sys

MAX_FRAME = 262144
MAX_OUTPUT = 65536


def respond(status: str, result=None) -> None:
    payload = json.dumps({'status': status, 'result': result},
                         ensure_ascii=True, allow_nan=False,
                         separators=(',', ':')).encode('ascii')
    if len(payload) > MAX_OUTPUT:
        payload = b'{"status":"error","result":null}'
    sys.stdout.buffer.write(payload + b'\n')
    sys.stdout.buffer.flush()


def _security_state() -> dict:
    """Kernel-state checks from inside the restricted process."""
    import ctypes
    class CapHeader(ctypes.Structure):
        _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int32)]
    class CapData(ctypes.Structure):
        _fields_ = [('effective', ctypes.c_uint32),
                    ('permitted', ctypes.c_uint32),
                    ('inheritable', ctypes.c_uint32)]
    header = CapHeader(0x20080522, 0)
    values = (CapData * 2)()
    libc = ctypes.CDLL(None)
    cap_ok = libc.capget(ctypes.byref(header), ctypes.byref(values)) == 0
    no_caps = cap_ok and all(x.effective == 0 and x.permitted == 0 and
                             x.inheritable == 0 for x in values)
    nnp = libc.prctl(39, 0, 0, 0, 0) == 1  # PR_GET_NO_NEW_PRIVS
    return {'no_capabilities': no_caps, 'no_new_privileges': nnp,
            'code_read_only': bool(os.statvfs('/app/cognitum').f_flag & os.ST_RDONLY),
            'stdlib_read_only': bool(os.statvfs('/usr').f_flag & os.ST_RDONLY)}


def _jail_preflight() -> bool:
    try:
        state = _security_state()
        return (sys.platform == 'linux' and os.getpid() == 1
                and os.path.isdir('/app/cognitum')
                and not os.path.exists('/root')
                and not os.path.exists('/etc/passwd')
                and not os.path.exists('/proc/1/root')
                and not os.path.exists('/mnt/data')
                and all(state.values()))
    except (OSError, ValueError, AttributeError):
        return False


def dispatch(message):
    if type(message) is not dict or set(message) != {'kind', 'operation', 'payload'}:
        raise ValueError('bad request shape')
    operation = message['operation']
    if type(operation) is not str or type(message['payload']) is not dict:
        raise ValueError('bad operation')
    if message['kind'] == 'cognitum':
        sys.path.insert(0, '/app')
        if operation == 'calc.rational':
            from cognitum.plugins.calculator import Calculator
            return Calculator().handle(operation, message['payload'])
        if operation in ('specialist.hdc','specialist.ssm','specialist.kan'):
            from cognitum.plugins.specialists import Specialists
            return Specialists().handle(operation, message['payload'])
    if message['kind'] == 'test_probe' and operation == 'probe.isolation':
        # The probe is INVOKED ONLY through a dedicated trusted test API;
        # it is absent from the production-facing operation allowlist.
        import socket
        isolated = not os.path.exists('/root')
        read_hosts = os.path.exists('/etc/hosts')
        try:
            with open('/app/cognitum/sandbox_child.py', 'a'):
                writable = True
        except (OSError, PermissionError):
            writable = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            network = s.connect_ex(('1.1.1.1', 80)) == 0
            s.close()
        except OSError:
            network = False
        # A preflight proof is necessary but not sufficient for future
        # arbitrary untrusted code acceptance.
        return {'isolation_preflight': isolated and _jail_preflight(),
                'host_etc_visible': read_hosts, 'code_writable': writable,
                'network_reachable': network, 'inside_pid': os.getpid(),
                'host_mnt_visible': os.path.exists('/mnt/data'),
                **_security_state(),
                'aws_key_visible': bool(os.environ.get('AWS_ACCESS_KEY_ID'))}
    if message['kind'] == 'test_probe' and operation == 'probe.flood':
        # Deliberately break protocol to validate parent bounded-stdout kill.
        sys.stdout.buffer.write(b'X' * (MAX_OUTPUT + 4096))
        sys.stdout.buffer.flush()
        import time
        time.sleep(60)
        return {'unexpected': True}
    if message['kind'] == 'test_probe' and operation == 'probe.stall':
        import time
        time.sleep(60.0)
        return {'unexpected': True}
    if message['kind'] == 'test_probe' and operation == 'probe.child':
        import subprocess
        # Fixed command, with recognizable unique marker, to prove that
        # cancellation of sandbox PID1 also kills a grandchild.
        subprocess.Popen(['/runtime/bin/python3', '-I', '-c',
                          'import time;time.sleep(60)',
                          '--cognitum-p7-grandchild-containment-probe'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         start_new_session=True,close_fds=True)
        import time
        time.sleep(60)
        return {'unexpected': True}
    raise ValueError('unregistered operation')


def main():
    if not _jail_preflight():
        respond('unavailable')
        return
    try:
        raw = sys.stdin.buffer.read(MAX_FRAME + 1)
        if not raw or len(raw) > MAX_FRAME:
            respond('invalid_input')
            return
        message = json.loads(raw)
        answer = dispatch(message)
        respond('ok', answer)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        respond('invalid_input')
    except BaseException:
        respond('error')


if __name__ == '__main__':
    main()
