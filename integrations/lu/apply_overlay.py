"""Opt-in C06 P7 overlay installer for an exact, clean Lu checkout.

Dry-run by default; --apply stages 3 new files and minimally edits two files.
No GitHub writes. Production host registration is deliberately NOT performed.
"""
import argparse
from pathlib import Path
import subprocess
import sys

PINNED_LU_COMMIT = 'bf2334a7d68f72265c37711de9bb5eda1f611d13'
MODULES = ('ansf_memory_gate', 'ansf_memory_proto')
PROTO = 'cognitum/memory/v1/evidence.proto'
LU_PROTO = 'proto/lu/v1/core.proto'
BUILD_ANCHOR = f'.compile_protos(&["{LU_PROTO}"], &["proto"])'


def checked_git(root, *args):
    return subprocess.check_output(
        ['git', '-C', str(root), *args], text=True, stderr=subprocess.STDOUT
    ).strip()


def prepare(root: Path, src: Path):
    crate = root / 'src-tauri' / 'lu-core'
    lib = crate / 'src' / 'lib.rs'
    build = crate / 'build.rs'
    manifest = crate / 'Cargo.toml'
    targets = {crate / 'src' / f'{module}.rs': src / 'src-tauri' / 'lu-core' / 'src' / f'{module}.rs'
               for module in MODULES}
    targets[crate / 'proto' / PROTO] = src / 'src-tauri' / 'lu-core' / 'proto' / PROTO
    if not (root / '.git').exists() or not all(x.is_file() for x in (lib, build, manifest)):
        raise ValueError('missing full pinned Lu checkout (lib.rs, build.rs or manifest absent)')
    if not all(x.is_file() for x in targets.values()):
        raise ValueError('Cognitum P7 overlay is incomplete')
    if checked_git(root, 'rev-parse', 'HEAD') != PINNED_LU_COMMIT:
        raise ValueError('Lu checkout is not at audited C06 source pin; rebase required')
    if checked_git(root, 'status', '--porcelain'):
        raise ValueError('Lu checkout is not clean; preserve existing modifications')
    if any(path.exists() or path.is_symlink() for path in targets):
        raise ValueError('one or more overlay destinations already exist; no overwrite permitted')
    dependencies = manifest.read_text(encoding='utf-8')
    if not all(token in dependencies for token in ('rusqlite', 'sha2', 'prost', 'prost-build')):
        raise ValueError('expected Lu crate dependencies absent')
    original_lib = lib.read_text(encoding='utf-8')
    if original_lib.count('pub mod ansf;\n') != 1 or any(f'pub mod {module};' in original_lib for module in MODULES):
        raise ValueError('Lu module anchor changed; rebase required')
    original_build = build.read_text(encoding='utf-8')
    if original_build.count(BUILD_ANCHOR) != 1:
        raise ValueError('Lu Protobuf build anchor changed; rebase required')
    # Important: original Lu build uses vendored protoc for both schemas.
    changes = {path: source.read_bytes() for path, source in targets.items()}
    changes[lib] = original_lib.replace(
        'pub mod ansf;\n',
        'pub mod ansf;\n' + ''.join(f'pub mod {module};\n' for module in MODULES), 1
    ).encode('utf-8')
    changes[build] = original_build.replace(
        BUILD_ANCHOR,
        f'.compile_protos(&["{LU_PROTO}", "proto/{PROTO}"], &["proto"])', 1
    ).encode('utf-8')
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lu-root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.lu_root.resolve()
    src = Path(__file__).resolve().parent
    try:
        changes = prepare(root, src)
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(f'Preflight passed: {root} (Lu {PINNED_LU_COMMIT})')
    print('Target changes (no host registration):')
    for path in changes:
        print('  ', path.relative_to(root))
    if not args.apply:
        print('Dry-run only; supply --apply to modify this clean local checkout.')
        return 0
    # Source paths are checked to be absent. Existing tracked files are only
    # rewritten after all prerequisites have been checked. This is an opt-in
    # local overlay, not a GitHub operation; do not silently rebase conflicts.
    created = []
    originals = {path: path.read_bytes() for path in changes if path.exists()}
    try:
        for path, data in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if path not in originals:
                with path.open('xb') as handle:
                    handle.write(data)
                created.append(path)
            else:
                path.write_bytes(data)
    except OSError:
        # Roll back only files this installer created/overwrote. Never clean
        # user changes or other Git-managed resources.
        for path, data in originals.items():
            path.write_bytes(data)
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    print('P7 overlay applied locally. Run cargo test in lu-core; GitHub untouched.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
