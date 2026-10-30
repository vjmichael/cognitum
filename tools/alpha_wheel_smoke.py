"""Independently install a built Cognitum wheel and exercise its default-off CLI.

Developer-alpha packaging smoke only; not Lu integration, OS sandbox proof,
a signed report, or an approved Windows installer.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def _command(args, cwd):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=90)
    if done.returncode:
        raise ValueError('ISOLATED_CHILD_FAILED')
    if len(done.stdout) > 65536:
        raise ValueError('OUTPUT_BUDGET_EXCEEDED')
    return json.loads(done.stdout.decode('utf-8'))


def smoke(wheel):
    wheel = Path(wheel).resolve()
    if not wheel.is_file() or not wheel.name.endswith('-py3-none-any.whl'):
        raise ValueError('EXPECTED_PORTABLE_WHEEL')
    with tempfile.TemporaryDirectory(prefix='cognitum-alpha-wheel-') as folder:
        temp = Path(folder)
        venvdir = temp / 'venv'
        venv.EnvBuilder(with_pip=True).create(venvdir)
        python = venvdir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        installed = subprocess.run(
            [str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)],
            cwd=temp, env=env, capture_output=True, timeout=90
        )
        if installed.returncode:
            raise ValueError('ISOLATED_WHEEL_INSTALL_FAILED')
        registry = _command([str(python), '-m', 'cognitum', 'registry'], temp)
        if registry != {'plugins': [], 'champions': {}}:
            raise ValueError('DEFAULT_REGISTRY_NOT_EMPTY')
        result = _command([str(python), '-m', 'cognitum', '--calculator', 'calc', '1/3+1/6'], temp)
        if (result.get('execution_status') != 'completed'
                or result.get('result') != {'value': '1/2'}
                or result.get('assurance') != 'exact_arithmetic'
                or result.get('interpretation', {}).get('level') != 'assumption_bound'):
            raise ValueError('WHEEL_CALCULATOR_SMOKE_FAILED')
    return {'status': 'FRESH_WHEEL_SMOKE_PASS_UNATTESTED',
            'wheel': wheel.name, 'python': sys.version.split()[0],
            'standalone': True, 'lu_integrated': False,
            'os_sandbox_verified': False, 'alpha_release_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel-dir', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    options = parser.parse_args(argv)
    wheels = sorted(options.wheel_dir.glob('cognitum_core-*.whl'))
    if len(wheels) != 1:
        parser.error('require exactly one Cognitum wheel')
    result = smoke(wheels[0])
    output = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8')
    if options.out:
        with options.out.open('xb') as file:
            file.write(output)
    else:
        sys.stdout.buffer.write(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
