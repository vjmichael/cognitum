"""Development-only extraction of user-supplied source archives; never writes uploads."""
from pathlib import Path
import zipfile, tarfile, re, hashlib
base=Path('/mnt/data')
out=base/'Cognitum_C14_P4E_G5_actual'/'vendor_build'
out.mkdir(parents=True,exist_ok=True)
manifest={}
for archive in ['EconML-main.zip','causal-learn-main.zip','sparse-main.zip']:
    p=base/archive
    with zipfile.ZipFile(p) as z:
        for f in z.infolist():
            name=f.filename
            if name.startswith('/') or '..' in Path(name).parts or (f.external_attr>>16 & 0o170000)==0o120000:
                raise ValueError(f'unsafe entry {name}')
        z.extractall(out)
    manifest[archive]=hashlib.sha256(p.read_bytes()).hexdigest()
# generated file deliberately excluded from upstream zip; local source provenance note
sparse=out/'sparse-main'/'sparse'/'_version.py'
sparse.write_text("__version__ = '0+uploaded'\n__version_tuple__ = (0,)\n")
# pip install development metadata without claiming an upstream release pin
(out/'sparse-main'/'setup.py').write_text("from setuptools import setup,find_packages\nsetup(name='sparse', version='0+uploaded', packages=find_packages(), zip_safe=False)\n")
# Patch source build only. Upstream setup.py incorrectly joins multiple pyx into a single wildcard extension.
econ=out/'EconML-main'/'setup.py'
s=econ.read_text()
needle='pyx_extensions = cythonize([Extension("*",\n                                          pyx_files,\n                                          include_dirs=[np.get_include()])],\n                               language_level="3")'
replacement='pyx_extensions = cythonize([Extension(os.path.splitext(file)[0].replace(os.sep, "."),\n                                          [file],\n                                          include_dirs=[np.get_include()]) for file in pyx_files],\n                               language_level="3")'
if needle not in s:raise ValueError('EconML source unexpected')
econ.write_text(s.replace(needle,replacement))
# momentchi2 tar.gz extraction handles regular files only
p=base/'momentchi2-0.1.8.tar.gz'
with tarfile.open(p) as tar:
    for m in tar.getmembers():
        if not(m.isfile() or m.isdir()) or m.name.startswith('/') or '..' in Path(m.name).parts: raise ValueError('unsafe tar member')
    tar.extractall(out,filter='data')
manifest[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
import json
(out/'user_source_sha256.json').write_text(json.dumps(manifest,indent=2))
print('prepared',out)
