"""C14 P2B offline DoWhy wheel closure and hash verification (candidate gate).

This checks *untrusted inputs* against a separately approved lock. It is not
signature verification, OS sandboxing, dynamic ABI validation, or a proof of
DoWhy correctness. Do not use the output to self-attest Lu's security boundary.

Usage:
  python tools/c14_p2b_wheelhouse_gate.py --lock path/lock.json --wheels path/wheelhouse
"""
from __future__ import annotations

import argparse
from collections import Counter
import email
import hashlib
import json
from pathlib import Path
import sys
import zipfile

try:
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.utils import canonicalize_name, parse_wheel_filename
    from packaging.tags import Tag
except ImportError as exc:
    raise SystemExit('GATE_UNAVAILABLE: packaging module required in gate runner') from exc


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def compatible_tags(py_ver: str, platform: str) -> set[Tag]:
    if py_ver != '3.13' or platform != 'win_amd64':
        raise ValueError('TARGET_NOT_SUPPORTED: only audited CPython 3.13 Windows x86-64')
    # Accepted tags are deliberately bounded; a later ABI audit may expand this.
    tags = {Tag('py3','none','any'), Tag('py313','none','any'), Tag('cp313','none','win_amd64')}
    tags |= {Tag('cp313','abi3','win_amd64'), Tag('cp312','abi3','win_amd64'),
             Tag('cp311','abi3','win_amd64'), Tag('cp310','abi3','win_amd64'),
             Tag('cp39','abi3','win_amd64'), Tag('cp38','abi3','win_amd64')}
    return tags


def verify(lock_path: Path, wheel_dir: Path) -> dict:
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if set(lock) != {'schema_version', 'target', 'packages'} or lock['schema_version'] != 1:
        raise ValueError('LOCK_SCHEMA_INVALID')
    if not isinstance(lock['target'], dict) or set(lock['target']) != {'python_version','platform'}:
        raise ValueError('LOCK_TARGET_INVALID')
    target = lock['target']
    compatible = compatible_tags(target['python_version'], target['platform'])
    packages = lock['packages']
    if not isinstance(packages,list) or not packages or len(packages) > 400:
        raise ValueError('LOCK_PACKAGES_INVALID')
    wheel_dir = wheel_dir.resolve(strict=True)
    if not wheel_dir.is_dir():
        raise ValueError('WHEELHOUSE_NOT_DIRECTORY')
    actual_files = {p.name for p in wheel_dir.iterdir() if p.is_file()}
    expected_files = set()
    installed = {}
    dependencies = {}
    for entry in packages:
        if not isinstance(entry,dict) or set(entry) != {'filename','sha256'}:
            raise ValueError('LOCK_ENTRY_INVALID')
        name, expected = entry['filename'], entry['sha256']
        if (not isinstance(name,str) or not name.endswith('.whl') or
            name in {'.','..'} or '/' in name or '\\' in name or
            not isinstance(expected,str) or len(expected)!=64 or
            any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('LOCK_ENTRY_UNSAFE')
        if name in expected_files:
            raise ValueError('LOCK_DUPLICATE_WHEEL')
        expected_files.add(name)
        path=wheel_dir/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('WHEEL_MISSING_OR_SYMLINK: '+name)
        if digest(path) != expected:
            raise ValueError('WHEEL_HASH_MISMATCH: '+name)
        project,version,build,tags = parse_wheel_filename(name)
        if not tags.intersection(compatible):
            raise ValueError('WHEEL_TARGET_INCOMPATIBLE: '+name)
        key=str(project)
        if key in installed:
            raise ValueError('WHEEL_PROJECT_DUPLICATE: '+key)
        with zipfile.ZipFile(path) as wheel:
            info=wheel.infolist()
            if (len(info)>50000 or sum(i.file_size for i in info)>1_000_000_000 or
                any(i.file_size>200_000_000 for i in info)):
                raise ValueError('WHEEL_EXPANSION_LIMIT: '+name)
            if wheel.testzip():
                raise ValueError('WHEEL_CORRUPTED: '+name)
            names=wheel.namelist()
            if (len(names) != len(set(names)) or
                any(n.startswith('/') or '\\' in n or any(x in ('..','.') for x in n.split('/')) for n in names)):
                raise ValueError('WHEEL_UNSAFE_MEMBER: '+name)
            mets=[n for n in names if n.endswith('.dist-info/METADATA')]
            if len(mets)!=1:
                raise ValueError('WHEEL_METADATA_MISSING: '+name)
            meta=email.message_from_bytes(wheel.read(mets[0]))
            if (canonicalize_name(meta.get('Name','')) != key or
                meta.get('Version','') != str(version)):
                raise ValueError('WHEEL_METADATA_DISAGREES: '+name)
            python_required = meta.get('Requires-Python')
            if python_required and '3.13.0' not in SpecifierSet(python_required):
                raise ValueError('WHEEL_PYTHON_INCOMPATIBLE: '+name)
            dependencies[key] = meta.get_all('Requires-Dist',[])
        installed[key] = version
    if actual_files != expected_files:
        raise ValueError('WHEELHOUSE_UNEXPECTED_OR_MISSING_FILES')
    if 'dowhy' not in installed or str(installed['dowhy']) != '0.14':
        raise ValueError('DOWHY_0_14_REQUIRED')
    env={'python_version':'3.13','python_full_version':'3.13.0','os_name':'nt',
         'sys_platform':'win32','platform_system':'Windows','platform_machine':'AMD64',
         'platform_python_implementation':'CPython','implementation_name':'cpython',
         'implementation_version':'3.13.0','extra':''}
    req_count=0
    for package, reqs in dependencies.items():
        for raw in reqs:
            req=Requirement(raw)
            # Packages with extra markers are excluded unless explicitly selected.
            if req.marker and not req.marker.evaluate(environment=env):
                continue
            requirement_name=canonicalize_name(req.name)
            if requirement_name not in installed:
                raise ValueError('DEPENDENCY_NOT_LOCKED: '+package+' requires '+requirement_name)
            if req.specifier and installed[requirement_name] not in req.specifier:
                raise ValueError('DEPENDENCY_VERSION_MISMATCH: '+requirement_name)
            req_count+=1
    return {'gate':'WHEELHOUSE_CLOSURE_ONLY','result':'PASS',
            'target':target,'wheel_count':len(installed),'required_edges':req_count,
            'total_wheel_bytes':sum((wheel_dir/f).stat().st_size for f in expected_files),
            'lock_sha256':digest(lock_path),
            'limitations':['lock authenticity must be verified by trusted Lu installer',
               'Windows ABI/import, VC runtime and DLL dependency not tested',
               'DoWhy runtime, OS sandbox and host authentication not tested']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lock',type=Path,required=True)
    p.add_argument('--wheels',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=verify(args.lock,args.wheels)
    except Exception as exc:
        result={'gate':'WHEELHOUSE_CLOSURE_ONLY','result':'FAIL',
                'reason':str(exc).splitlines()[0][:200]}
        print(json.dumps(result,sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    sys.exit(main())
