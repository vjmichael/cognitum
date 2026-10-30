"""Native acceptance preflight; never reports a Windows pass on non-Windows."""
from __future__ import annotations
import argparse
import json
import os
import platform
from pathlib import Path
import struct
import sys
from .platform_io import windows_require_ntfs, reject_reparse


def preflight(scratch_dir: Path) -> dict:
    if os.name != 'nt' or sys.platform != 'win32':
        raise RuntimeError('NATIVE_WINDOWS_REQUIRED')
    if struct.calcsize('P') != 8 or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('WINDOWS_X86_64_PYTHON_REQUIRED')
    path = scratch_dir.resolve(strict=True)
    if not path.is_dir():
        raise RuntimeError('SCRATCH_DIRECTORY_REQUIRED')
    reject_reparse(path)
    fs = windows_require_ntfs(path)
    return {'native_windows': True, 'machine': platform.machine(),
            'platform': sys.platform, 'python_version': platform.python_version(),
            'python_pointer_bits': 64, 'filesystem': fs,
            'dedicated_scratch': True,
            'power_loss_tested': False, 'independent_host_tested': False,
            'lu_integration_tested': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = preflight(args.scratch)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
