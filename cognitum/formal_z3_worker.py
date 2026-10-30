"""Isolated optional Z3 C-API worker. Receives validated SMT-LIB from host adapter.

This worker is not a security sandbox; Lu must own process permissions and quotas.
"""
import ctypes
from pathlib import Path
import sys


def main():
    if len(sys.argv)!=2 or not Path(sys.argv[1]).is_absolute():return 2
    data=sys.stdin.buffer.read(65537)
    if not 0<len(data)<=65536:return 2
    z=ctypes.CDLL(sys.argv[1])
    z.Z3_mk_config.restype=ctypes.c_void_p
    z.Z3_mk_context.argtypes=[ctypes.c_void_p];z.Z3_mk_context.restype=ctypes.c_void_p
    z.Z3_del_config.argtypes=[ctypes.c_void_p]
    z.Z3_del_context.argtypes=[ctypes.c_void_p]
    z.Z3_eval_smtlib2_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
    z.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
    c=z.Z3_mk_config();ctx=z.Z3_mk_context(c);z.Z3_del_config(c)
    try:
        out=z.Z3_eval_smtlib2_string(ctx,data)
        if not out or len(out)>65536:return 3
        sys.stdout.buffer.write(out)
    finally:z.Z3_del_context(ctx)
    return 0

if __name__=='__main__':sys.exit(main())
