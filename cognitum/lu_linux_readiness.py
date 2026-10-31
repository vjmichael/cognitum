"""P46R7: read-only Lu-Linux development-host integration readiness probe.

No connection, token, tool call, permission grant or worker spawn is attempted.
Even a plausible socket cannot prove an authenticated Lu host.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

SCHEMA = 'cognitum.p46r7-lu-host-readiness.v1'


def inspect(source_root: Path, socket_path: Path) -> dict:
    root = Path(source_root)
    sock = Path(socket_path)
    missing = []
    cargo = root / 'src-tauri' / 'Cargo.toml'
    mod = root / 'src-tauri' / 'src' / 'core' / 'lu_native_test_host.rs'
    if not cargo.is_file() or cargo.is_symlink():
        missing.append('LU_TAURI_CARGO_NOT_PRESENT')
    else:
        try:
            if 'lu-native-test-host' not in cargo.read_text(encoding='utf-8'):
                missing.append('LU_FEATURE_NOT_REGISTERED')
        except OSError:
            missing.append('LU_CARGO_UNREADABLE')
    if not mod.is_file() or mod.is_symlink():
        missing.append('LU_HOST_SOURCE_NOT_PRESENT')
    if sock.is_symlink() or not sock.is_absolute():
        missing.append('LU_SOCKET_PATH_UNTRUSTED')
    else:
        try:
            info = sock.lstat()
            if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077):
                missing.append('LU_SOCKET_UNTRUSTED')
        except OSError:
            missing.append('LU_SOCKET_UNAVAILABLE')
    return {
        'schema': SCHEMA,
        'status': 'BLOCKED_SOURCE_OR_SOCKET' if missing else 'SOURCE_SOCKET_PRESENT_UNVERIFIED',
        'missing': missing,
        'authenticated_lu_roundtrip_observed': False,
        'cognitum_worker_dispatched_by_lu': False,
        'production_authorized': False,
        'note': 'Does not establish native host identity, owner TURN scope, or tool execution',
    }


def main(argv=None):
    p = argparse.ArgumentParser(description='Read-only Lu Linux native host readiness; no tool invocation')
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--socket', type=Path, required=True)
    args = p.parse_args(argv)
    outcome = inspect(args.source_root, args.socket)
    print(json.dumps(outcome, sort_keys=True))
    return 2 if outcome['status'] == 'BLOCKED_SOURCE_OR_SOCKET' else 3


if __name__ == '__main__':
    raise SystemExit(main())
