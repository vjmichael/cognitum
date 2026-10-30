"""Offline wheelhouse verification negative cases; not a true DoWhy runtime test."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from tools.c14_p2b_wheelhouse_gate import verify


class WheelGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.wheels=self.root/'wheelhouse'
        self.wheels.mkdir()
        self.lock=self.root/'lock.json'
        self.specs=[]

    def wheel(self,name='dowhy',version='0.14',tag='py3-none-any',dependencies=(),bad_member=None,requires_python=None):
        fn=f'{name}-{version}-{tag}.whl'
        p=self.wheels/fn
        metadata='Metadata-Version: 2.1\nName: '+name+'\nVersion: '+version+'\n'
        metadata+=''.join('Requires-Dist: '+r+'\n' for r in dependencies)
        if requires_python:metadata+='Requires-Python: '+requires_python+'\n'
        with ZipFile(p,'w',ZIP_DEFLATED) as z:
            z.writestr(f'{name}-{version}.dist-info/METADATA',metadata)
            if bad_member:z.writestr(bad_member,'x')
        self.specs.append({'filename':fn,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        return p

    def write_lock(self):
        self.lock.write_text(json.dumps({'schema_version':1,'target':{'python_version':'3.13','platform':'win_amd64'},'packages':self.specs}))
        return self.lock

    def test_complete_synthetic_closure(self):
        self.wheel(dependencies=['example>=1.0','optdep>=1.0; extra == "plotting"'])
        self.wheel(name='example',version='1.2.0')
        r=verify(self.write_lock(),self.wheels)
        self.assertEqual(r['result'],'PASS')
        self.assertEqual(r['required_edges'],1)

    def test_hash_mismatch(self):
        p=self.wheel();self.write_lock();p.write_bytes(p.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'WHEEL_HASH_MISMATCH'):
            verify(self.lock,self.wheels)

    def test_missing_dependency(self):
        self.wheel(dependencies=['notpresent>=1.0'])
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_NOT_LOCKED'):
            verify(self.write_lock(),self.wheels)

    def test_incompatible_version(self):
        self.wheel(dependencies=['example>=2.0']);self.wheel(name='example',version='1.0')
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_VERSION_MISMATCH'):
            verify(self.write_lock(),self.wheels)

    def test_platform_mismatch(self):
        self.wheel(tag='cp311-cp311-manylinux_x86_64')
        with self.assertRaisesRegex(ValueError,'WHEEL_TARGET_INCOMPATIBLE'):
            verify(self.write_lock(),self.wheels)

    def test_wrong_dowhy_version(self):
        self.wheel(version='0.13')
        with self.assertRaisesRegex(ValueError,'DOWHY_0_14_REQUIRED'):
            verify(self.write_lock(),self.wheels)

    def test_duplicate_entry(self):
        self.wheel();self.specs.append(dict(self.specs[0]))
        with self.assertRaisesRegex(ValueError,'LOCK_DUPLICATE_WHEEL'):
            verify(self.write_lock(),self.wheels)

    def test_symlink_untrusted(self):
        p=self.wheel();self.write_lock();target=self.root/'target.whl';p.replace(target);p.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'WHEEL_MISSING_OR_SYMLINK'):
            verify(self.lock,self.wheels)

    def test_member_traversal(self):
        self.wheel(bad_member='../exploit.py')
        with self.assertRaisesRegex(ValueError,'WHEEL_UNSAFE_MEMBER'):
            verify(self.write_lock(),self.wheels)

    def test_unexpected_file(self):
        self.wheel();(self.wheels/'extra.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'WHEELHOUSE_UNEXPECTED_OR_MISSING_FILES'):
            verify(self.write_lock(),self.wheels)

    def test_python_requires_mismatch(self):
        self.wheel(requires_python='<3.13')
        with self.assertRaisesRegex(ValueError,'WHEEL_PYTHON_INCOMPATIBLE'):
            verify(self.write_lock(),self.wheels)

    def test_target_version_rejected(self):
        self.wheel();self.write_lock()
        obj=json.loads(self.lock.read_text());obj['target']['python_version']='3.10';self.lock.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,'TARGET_NOT_SUPPORTED'):
            verify(self.lock,self.wheels)


if __name__=='__main__':unittest.main()
