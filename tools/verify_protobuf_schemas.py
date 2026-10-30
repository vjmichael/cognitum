"""Compile all Cognitum Protobuf schemas independently and compare bindings.

Usage: PYTHONPATH=. python tools/verify_protobuf_schemas.py [--require]
Finds protoc on PATH or Torch's vendored libprotoc executable if installed.
No network is used, and descriptor outputs stay in a temporary directory.
If --require is set, absence of a compiler is a test failure.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from google.protobuf.descriptor_pb2 import FileDescriptorSet, FileDescriptorProto
from tools.check_proto_descriptors import EXPECTED, normalized_file

ROOT = Path(__file__).resolve().parents[1]


def find_protoc():
    executable = shutil.which('protoc')
    if executable: return executable
    try:
        import torch
        candidate = Path(torch.__file__).parent / 'bin' / 'protoc'
        if candidate.is_file(): return str(candidate)
    except (ImportError, OSError):
        pass
    return None


def verify_all(protoc):
    with tempfile.TemporaryDirectory(prefix='cognitum-proto-') as temp:
        for name, expected in sorted(EXPECTED.items()):
            out = Path(temp) / 'descriptor.pb'
            subprocess.run([protoc, '--experimental_allow_proto3_optional',
                            '-I' + str(ROOT / 'proto'), '--descriptor_set_out=' + str(out), name],
                           check=True, capture_output=True)
            produced = FileDescriptorSet.FromString(out.read_bytes())
            if len(produced.file) != 1 or produced.file[0].name != name:
                raise ValueError('unexpected compiler descriptor: ' + name)
            if normalized_file(produced.file[0]) != normalized_file(
                FileDescriptorProto.FromString(expected.serialized_pb)
            ):
                raise ValueError('Protobuf source/binding mismatch: ' + name)
    return len(EXPECTED)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require', action='store_true')
    args = parser.parse_args()
    protoc = find_protoc()
    if not protoc:
        if args.require: parser.error('independent protoc compiler unavailable')
        print('SKIPPED: no independent protoc compiler; use --require to gate')
        return 0
    count = verify_all(protoc)
    print(f'PASS: independently compiled {count} .proto files; Python binding wire shapes match ({protoc})')
    return 0

if __name__ == '__main__': sys.exit(main())
