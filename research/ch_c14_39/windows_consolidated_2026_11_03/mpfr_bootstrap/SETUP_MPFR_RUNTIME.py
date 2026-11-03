#!/usr/bin/env python3
"""Download SHA-256-pinned official MSYS2 UCRT64 MPFR/GMP runtime DLLs.

Runtime only: writes next to the Cognitum regression kit, does not install
MSYS2 or modify PATH, registry, Python, Lu, or Cognitum source. Requires
Python 3.14 for built-in compression.zstd. See README_MPFR.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

PACKAGES = (
    {
        'name': 'MPFR 4.2.2-3',
        'filename': 'mingw-w64-ucrt-x86_64-mpfr-4.2.2-3-any.pkg.tar.zst',
        'sha256': '6b70a275d2ec75c70aa50a236c218e6b7ee9a5ab4c6d52cb0b580267b7d200fe',
        'member': 'ucrt64/bin/libmpfr-6.dll',
        'dll': 'libmpfr-6.dll',
        'source_page': 'https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-mpfr',
    },
    {
        'name': 'GMP 6.3.0-2',
        'filename': 'mingw-w64-ucrt-x86_64-gmp-6.3.0-2-any.pkg.tar.zst',
        'sha256': 'e82a75968a556484a50084578238a84eb60fb93e34986fd6695c537975bd39ea',
        'member': 'ucrt64/bin/libgmp-10.dll',
        'dll': 'libgmp-10.dll',
        'source_page': 'https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-gmp',
    },
)
MAX_PACKAGE_BYTES = 12 * 1024 * 1024
MAX_UNPACKED_BYTES = 80 * 1024 * 1024
MAX_DLL_BYTES = 24 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_package(package: dict, cache_dir: Path | None) -> bytes:
    if cache_dir is not None:
        cache_file = cache_dir / package['filename']
        if cache_file.is_file():
            data = cache_file.read_bytes()
            if sha256(data) != package['sha256']:
                raise RuntimeError('Offline package failed SHA-256: ' + str(cache_file))
            print('Verified local official package:', cache_file.name)
            return data
    urls = (
        'https://mirror.msys2.org/mingw/ucrt64/' + package['filename'],
        'https://repo.msys2.org/mingw/ucrt64/' + package['filename'],
    )
    failures = []
    for url in urls:
        print('Downloading official package:', package['name'])
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Cognitum-CH39-MPFR-Runtime-Setup/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read(MAX_PACKAGE_BYTES + 1)
            if len(data) > MAX_PACKAGE_BYTES:
                raise RuntimeError('Package size exceeds limit')
            found = sha256(data)
            if found != package['sha256']:
                raise RuntimeError('SHA-256 mismatch; expected ' + package['sha256'] + ', got ' + found)
            print('PASS: official package SHA-256', found)
            return data
        except Exception as exc:
            failures.append(f'{type(exc).__name__}: {exc}')
    raise RuntimeError('Could not fetch official ' + package['name'] + '.\n'
                       + '\n'.join(failures) + '\n'
                       + 'Download from ' + package['source_page']
                       + ' and put the .pkg.tar.zst file beside this script, then rerun.')


def extract_dll(package: dict, package_bytes: bytes) -> bytes:
    from compression import zstd
    unpacked = zstd.decompress(package_bytes)
    if len(unpacked) > MAX_UNPACKED_BYTES:
        raise RuntimeError('Decompressed package exceeds maximum size')
    with tarfile.open(fileobj=io.BytesIO(unpacked), mode='r:') as tf:
        matches = [m for m in tf.getmembers() if m.name.removeprefix('./') == package['member']]
        if len(matches) != 1 or not matches[0].isreg():
            raise RuntimeError('Expected one regular-file DLL in verified package: ' + package['member'])
        member = matches[0]
        if not 1024 < member.size < MAX_DLL_BYTES:
            raise RuntimeError('Unexpected DLL size: ' + str(member.size))
        source = tf.extractfile(member)
        if source is None:
            raise RuntimeError('Could not read DLL member')
        dll = source.read()
        if len(dll) != member.size or not dll.startswith(b'MZ'):
            raise RuntimeError('DLL missing bytes or Windows PE signature')
        return dll


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path(__file__).resolve().parent / 'MPFR_Runtime')
    parser.add_argument('--offline-dir', type=Path, default=Path(__file__).resolve().parent,
                        help='If downloaded packages are in this directory, use and SHA256-check them')
    args = parser.parse_args()
    if sys.version_info < (3, 14):
        print('BLOCKED: Python 3.14 or newer required to read .tar.zst using the standard library.')
        return 2
    if os.name != 'nt':
        print('BLOCKED: this setup is intended for Windows UCRT64 runtimes.')
        return 2
    try:
        from compression import zstd  # noqa: F401
    except ImportError:
        print('BLOCKED: Python compression.zstd missing; use a standard Python 3.14 build.')
        return 2
    dest = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    provenance = {'created_utc': datetime.now(timezone.utc).isoformat(),
                  'source': 'SHA-256-pinned MSYS2 UCRT64 official package archives',
                  'python': sys.version.split()[0], 'files': {}}
    try:
        dlls = []
        for package in PACKAGES:
            pkg_bytes = download_package(package, args.offline_dir)
            dll_bytes = extract_dll(package, pkg_bytes)
            dlls.append((package, dll_bytes))
            provenance['files'][package['dll']] = {
                'source_package': package['filename'],
                'package_sha256': package['sha256'],
                'dll_sha256': sha256(dll_bytes),
                'source_page': package['source_page'],
            }
        # Nothing is published until both pinned source archives verify.
        for package, dll_bytes in dlls:
            path = dest / package['dll']
            tmp = dest / (package['dll'] + '.tmp')
            tmp.write_bytes(dll_bytes)
            os.replace(tmp, path)
            print('PASS: extracted', path.name, 'SHA-256:', sha256(dll_bytes))
        record = dest / 'MPFR_RUNTIME_PROVENANCE.json'
        record.write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print('PASS: native DLLs extracted into', dest)
        print('DLL:', dest / 'libmpfr-6.dll')
        print('GMP dependency:', dest / 'libgmp-10.dll')
        return 0
    except Exception as exc:
        print('BLOCKED: ' + type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        print('No changes to Python, PATH, registry or existing evidence.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
