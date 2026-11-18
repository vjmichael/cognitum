import os, subprocess, shutil
from pathlib import Path
import zlib,struct
import numpy as np
import pytest
from cognitum.research.hdc_hardware import *
from cognitum.research.hdc_shared import Shared
ROOT=Path(__file__).resolve().parents[2]
@pytest.fixture(scope='module')
def native(tmp_path_factory):
    p=tmp_path_factory.mktemp('native')/('packed.dll' if os.name=='nt' else 'packed.so')
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:raise RuntimeError('native compiler required')
    subprocess.run([cc,'-std=c11','-O3','-Wall','-Wextra','-Werror','-shared',*(['-fPIC'] if os.name!='nt' else []),str(ROOT/'hardware/hdc/packed.c'),'-o',str(p)],check=True)
    return Native(p)
@pytest.mark.parametrize('d',[1,7,63,64,65,127,256,1024,4097,65536])
def test_scores(d,native):
    r=np.random.default_rng(d);a=r.integers(0,2,(3,d),dtype=np.uint8);b=r.integers(0,2,(5,d),dtype=np.uint8)
    q,p=pack(a),pack(b);oracle=(1-2*a.astype(np.int32))@(1-2*b.astype(np.int32)).T
    if d%64:q[:,-1]|=np.uint64(((1<<64)-1)^((1<<(d%64))-1))
    assert np.array_equal(scores(q,p,d),oracle) and np.array_equal(native.scores(q,p,d),oracle)
@pytest.mark.parametrize('n',[1,255,65536])
def test_int8(n,native):
    r=np.random.default_rng(n);a=r.integers(-128,128,n,dtype=np.int8);b=r.integers(-128,128,n,dtype=np.int8)
    assert native.dot(a,b)==int(a.astype(np.int64)@b.astype(np.int64));a.fill(-128);b.fill(-128);assert native.dot(a,b)==n*16384

def test_quant(native):
    rng=np.random.default_rng(1)
    for a,m,s in [(2**31-1,2**31-1,62),(-2**31,2**31-1,0),(-1,1,1),(1,1,1)]+[(int(rng.integers(-2**31,2**31)),int(rng.integers(0,2**31)),int(rng.integers(0,63))) for _ in range(1000)]:
        assert native.requantize(a,m,s)==requantize(a,m,s)
    assert requantize(-1,1,1)==-1 and requantize(1,1,1)==1

def test_protocol(native):
    rng=np.random.default_rng(2);q=pack(rng.integers(0,2,(1,65)));p=pack(rng.integers(0,2,(3,65)));f=frame(q,p,65,123)
    assert endpoint(f,native)==endpoint(f);a=endpoint(f);assert struct.unpack_from('<4sQI',a)==(b'HDR1',123,3);assert zlib.crc32(a[:-4])==int.from_bytes(a[-4:],'little')
    for bad in (f[:-1],f+b'\0',b'X'+f[1:],f[:HDR.size]+bytes([f[HDR.size]^1])+f[HDR.size+1:]):
        with pytest.raises(ValueError):decode(bad)
    bad=bytearray(f[:-4]);bad[HDR.size+15]=255;bad+=struct.pack('<I',zlib.crc32(bad))
    with pytest.raises(ValueError):decode(bytes(bad))

def test_prefix():
    r=np.random.default_rng(4);b=r.integers(0,2,(10,512));p=pack(b);q=pack(np.concatenate([b,r.integers(0,2,(10,512))]));a,ok=safe_prefix(q,p,512,7)
    assert np.array_equal(a,scores(q,p,512).argmax(1)) and ok[:10].all()
    a,ok=safe_prefix(q,np.repeat(p[:1],2,axis=0),512,8);assert not ok.any() and not a.any()

def test_resources():
    assert resources(256,256,4)['bram36_total']==8
    assert resources(16384,256,1)['bram36_model']==128

def test_shared():
    r=np.random.default_rng(0);x=r.normal(size=(30,6));y=np.tile(np.arange(3),10);a=Shared(6,128,3,3,1).fit(x,y,2)
    v=x.reshape(10,3,6);s,n=a.predict(v,'sequential');p,m=a.predict(v,'batch');f,k=a.predict(v,'shared',1.)
    assert np.array_equal(s,p) and np.array_equal(p,f) and (n,m,k)==(30,30,40)
    assert a.predict(v,'shared')[1]==10

def test_reject():
    for d in (0,65537):
        with pytest.raises(ValueError):scores(np.zeros((1,1),np.uint64),np.zeros((1,1),np.uint64),d)
    with pytest.raises(ValueError):pack([[2]])
    with pytest.raises(ValueError):requantize(0,0,63)
@pytest.mark.parametrize('bitorder',['little','big'])
def test_prior_layout(bitorder):
    r=np.random.default_rng(7);b=r.integers(0,2,(5,259),dtype=np.uint8);a=np.packbits(b,axis=1,bitorder=bitorder)
    assert np.array_equal(from_byte_rows(a,259,bitorder),pack(b))
@pytest.mark.parametrize('d',[1,65,256,10000])
def test_bind_bundle(d,native):
    r=np.random.default_rng(d);b=r.integers(0,2,(6,d),dtype=np.uint8);p=pack(b)
    assert np.array_equal(native.bind(p[:1],p[1:2],d),pack(b[:1]^b[1:2]))
    assert np.array_equal(native.bind(native.bind(p[:1],p[1:2],d),p[1:2],d),p[:1])
    assert np.array_equal(native.majority(p,d),pack((b.sum(0)*2>=len(b))[None,:]))

def test_response():
    q=pack([[1,1,0]]);p=pack([[0,0,1],[1,1,0]])
    result=endpoint(frame(q,p,3,9));assert decode_response(result,9,2,3).tolist()==[-3,3]
    with pytest.raises(ValueError):decode_response(result,8,2,3)
    bad=struct.pack('<4sQIii',b'HDR1',9,2,4,3);bad+=struct.pack('<I',zlib.crc32(bad))
    with pytest.raises(ValueError):decode_response(bad,9,2,3)
