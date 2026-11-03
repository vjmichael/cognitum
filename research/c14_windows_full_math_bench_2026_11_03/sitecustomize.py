"""Per-process Windows MPFR resolver. Historical source code remains untouched."""
import ctypes,ctypes.util,os,sys,pathlib
p=os.environ.get('C14_BENCH_MPFR_DLL')
if p:
 path=pathlib.Path(p).resolve()
 if not path.is_file():raise RuntimeError('MPFR missing: '+str(path))
 if sys.platform=='win32':
  if ctypes.sizeof(ctypes.c_void_p)!=8:raise RuntimeError('64-bit Python required')
  _mpfr_dll_directory=os.add_dll_directory(str(path.parent))
 _find_library_original=ctypes.util.find_library
 def _find_library_c14(name):return str(path) if name=='mpfr' else _find_library_original(name)
 ctypes.util.find_library=_find_library_c14
