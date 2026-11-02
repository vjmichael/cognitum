"""P8 one-shot prewarmed specialist inside the SAME P7 namespace jail.

Starts with NO user request; imports only an allowlisted trusted provider, emits
READY after the P7 kernel preflight, processes exactly ONE bounded JSON line,
then exits. The host owns authorization and validation. Not a general plugin.
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/cognitum')

from sandbox_child import (_jail_preflight, _security_state, dispatch,
                           MAX_FRAME, MAX_OUTPUT, respond)


def main():
    if not _jail_preflight():
        respond('unavailable')
        return
    provider = os.environ.get('COGNITUM_WARM_PROVIDER', '')
    if provider == 'calculator':
        from cognitum.plugins.calculator import Calculator
        Calculator()  # trusted import/initialization, no caller data
        operations = frozenset(('calc.rational',))
    elif provider == 'specialists':
        from cognitum.plugins.specialists import Specialists
        Specialists()
        # Import computational dependencies before READY when possible.
        import numpy  # noqa: F401
        import google.protobuf  # noqa: F401
        operations = frozenset(('specialist.hdc', 'specialist.ssm', 'specialist.kan'))
    else:
        respond('unavailable')
        return
    # No caller task crosses the boundary until the parent receives READY.
    ready = json.dumps({'status':'ready', 'result':{
        'isolation_preflight': True, 'inside_pid':os.getpid(),
        'read_only_code':_security_state()['code_read_only'],
    }}, separators=(',',':')).encode('ascii')
    sys.stdout.buffer.write(ready + b'\n')
    sys.stdout.buffer.flush()
    try:
        raw = sys.stdin.buffer.readline(MAX_FRAME + 1)
        if not raw or len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
            respond('invalid_input')
            return
        def closed(pairs):
            obj = dict(pairs)
            if len(obj) != len(pairs):
                raise ValueError('DUPLICATE_REQUEST_KEY')
            return obj
        msg = json.loads(raw, object_pairs_hook=closed,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_REQUEST')))
        # Dedicated regression probes are reachable ONLY to a trusted host
        # launching this private worker protocol, never Cognitum Runtime tools.
        if (type(msg) is dict and set(msg) == {'kind','operation','payload'}
                and msg['kind'] == 'test_probe' and
                msg['operation'] in ('probe.isolation','probe.child','probe.stall')):
            respond('ok', dispatch(msg))
            return
        if (type(msg) is not dict or set(msg) != {'kind','operation','payload'}
                or msg['kind'] != 'cognitum' or msg['operation'] not in operations):
            respond('invalid_input')
            return
        if msg['operation'] == 'specialist.kan' and not os.environ.get('COGNITUM_TRUSTED_KAN_SHA256'):
            respond('unavailable')
            return
        respond('ok', dispatch(msg))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        respond('invalid_input')
    except BaseException:
        respond('error')


if __name__ == '__main__':
    main()
