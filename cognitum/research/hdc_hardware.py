"""Research-only CPU and FPGA transport reference. No hardware access or authority."""
import ctypes as ct
import hashlib, struct, zlib
import numpy as np
MAX_D=65536

def pack(bits):
    a=np.asarray(bits)
    if a.ndim!=2 or not 1<=a.shape[1]<=MAX_D or not np.isin(a,[0,1]).all():raise ValueError('binary rows')
    b=np.packbits(a.astype(np.uint8),axis=1,bitorder='little')
    b=np.pad(b,((0,0),(0,(-b.shape[1])%8)))
    return b.copy().view('<u8')

def validate(a,d):
    a=np.asarray(a)
    if type(d)!=int or not 1<=d<=MAX_D or a.ndim!=2 or not len(a) or a.dtype!=np.dtype('<u8') or a.shape[1]!=(d+63)//64:raise ValueError('packed shape')
    return np.ascontiguousarray(a)

def scores(q,p,d):
    q,p=validate(q,d),validate(p,d);out=np.empty((len(q),len(p)),np.int32)
    mask=np.uint64((1<<(d%64))-1 if d%64 else (1<<64)-1)
    for i,v in enumerate(q):
        x=v^p;x[:,-1]&=mask
        out[i]=d-2*np.bitwise_count(x).sum(axis=1,dtype=np.int32)
    return out

class Native:
    def __init__(self,path):
        self.lib=ct.CDLL(str(path));u=ct.POINTER(ct.c_uint64);i=ct.POINTER(ct.c_int32);b=ct.POINTER(ct.c_int8)
        self.lib.hdc_scores.argtypes=[u,u,i,ct.c_size_t,ct.c_size_t,ct.c_uint];self.lib.hdc_scores.restype=ct.c_int
        self.lib.hdc_capabilities.argtypes=[];self.lib.hdc_capabilities.restype=ct.c_uint
        self.lib.hdc_dispatch.argtypes=[ct.c_uint,ct.c_uint];self.lib.hdc_dispatch.restype=ct.c_int
        self.lib.hdc_scores_mode.argtypes=[u,u,i,ct.c_size_t,ct.c_size_t,ct.c_uint,ct.c_uint];self.lib.hdc_scores_mode.restype=ct.c_int
        self.lib.hdc_i8dot.argtypes=[b,b,ct.c_size_t,i];self.lib.hdc_i8dot.restype=ct.c_int
        self.lib.hdc_requantize.argtypes=[ct.c_int32,ct.c_int32,ct.c_uint,b];self.lib.hdc_requantize.restype=ct.c_int
        self.lib.hdc_bind.argtypes=[u,u,u,ct.c_uint];self.lib.hdc_bind.restype=ct.c_int
        self.lib.hdc_majority.argtypes=[u,u,ct.c_size_t,ct.c_uint];self.lib.hdc_majority.restype=ct.c_int
    @property
    def capabilities(self):return self.lib.hdc_capabilities()
    def selected(self,d,mode=3):
        if type(d)!=int or not 1<=d<=MAX_D or mode not in (0,1,2,3):raise ValueError("dispatch arguments")
        return self.lib.hdc_dispatch(d,mode)
    def scores(self,q,p,d,mode=3):
        q,p=validate(q,d),validate(p,d);out=np.empty((len(q),len(p)),np.int32)
        if mode not in (0,1,2,3):raise ValueError("dispatch mode")
        if self.lib.hdc_scores_mode(q.ctypes.data_as(ct.POINTER(ct.c_uint64)),p.ctypes.data_as(ct.POINTER(ct.c_uint64)),out.ctypes.data_as(ct.POINTER(ct.c_int32)),len(q),len(p),d,mode):raise RuntimeError('native mode unavailable or failure')
        return out
    def dot(self,a,b):
        a,b=np.asarray(a),np.asarray(b)
        if a.dtype!=np.int8 or b.dtype!=np.int8 or a.ndim!=1 or a.shape!=b.shape or not 1<=len(a)<=MAX_D:raise ValueError('int8 dot')
        a,b=np.ascontiguousarray(a),np.ascontiguousarray(b);out=ct.c_int32();p=ct.POINTER(ct.c_int8)
        if self.lib.hdc_i8dot(a.ctypes.data_as(p),b.ctypes.data_as(p),len(a),ct.byref(out)):raise RuntimeError('native failure')
        return out.value

    def bind(self,a,b,d):
        a,b=validate(a,d),validate(b,d)
        if len(a)!=1 or len(b)!=1:raise ValueError('single operands')
        out=np.empty_like(a);u=ct.POINTER(ct.c_uint64)
        if self.lib.hdc_bind(a.ctypes.data_as(u),b.ctypes.data_as(u),out.ctypes.data_as(u),d):raise RuntimeError('native failure')
        return out
    def majority(self,a,d):
        a=validate(a,d)
        if len(a)>65536:raise ValueError('bundle budget')
        out=np.empty_like(a[:1]);u=ct.POINTER(ct.c_uint64)
        if self.lib.hdc_majority(a.ctypes.data_as(u),out.ctypes.data_as(u),len(a),d):raise RuntimeError('native failure')
        return out

    def requantize(self,acc,mult,shift):
        requantize(acc,mult,shift) # shared validation, not shared numerical result
        out=ct.c_int8()
        if self.lib.hdc_requantize(acc,mult,shift,ct.byref(out)):raise RuntimeError("native failure")
        return out.value

def requantize(acc,mult,shift):
    """Integer ties-away-from-zero, signed saturation; no floating point."""
    if not all(type(i)==int for i in (acc,mult,shift)) or not -(1<<31)<=acc<(1<<31) or not 0<=mult<(1<<31) or not 0<=shift<=62:raise ValueError('fixed point range')
    x=acc*mult;y=(abs(x)+(1<<(shift-1)))>>shift if shift else abs(x)
    return max(-128,min(127,-y if x<0 else y))

def safe_prefix(q,p,d,words):
    """Exact early decision: omitted +/-1 coordinates bound every score. Stable ties via full fallback."""
    q,p=validate(q,d),validate(p,d)
    if len(p)<2 or not 1<=words<=q.shape[1]:raise ValueError('prefix')
    k=min(words*64,d);part=scores(q[:,:words],p[:,:words],k);best=part.argmax(1);sorted_=np.sort(part,axis=1)
    certified=sorted_[:,-1]-sorted_[:,-2]>2*(d-k)
    if (~certified).any() and k<d:
        best[~certified]=(part[~certified]+scores(q[~certified,words:],p[:,words:],d-k)).argmax(1)
    return best,certified

# Canonical request body: one query then prototype bank as little-endian u64;
# tail padding zero, CRC over header+payload; request ID echoed by software endpoint.
HDR=struct.Struct('<4sBBHQII'); MAGIC=b'HDC1'; MAX_CLASSES=256

def frame(q,p,d,request_id):
    q,p=validate(q,d),validate(p,d)
    if len(q)!=1 or not 1<=len(p)<=MAX_CLASSES or not 0<=request_id<2**64:raise ValueError('request bounds')
    a=np.concatenate((q,p));mask=(1<<(d%64))-1 if d%64 else (1<<64)-1
    if np.any(a[:,-1]&np.uint64(((1<<64)-1)^mask)):raise ValueError('nonzero padding')
    body=a.astype('<u8',copy=False).tobytes();h=HDR.pack(MAGIC,1,1,0,request_id,d,len(p));return h+body+struct.pack('<I',zlib.crc32(h+body))

def decode(data):
    if not isinstance(data,bytes) or len(data)<HDR.size+4:raise ValueError('truncated')
    magic,v,op,res,r,d,n=HDR.unpack_from(data)
    if (magic,v,op,res)!=(MAGIC,1,1,0) or not 1<=d<=MAX_D or not 1<=n<=MAX_CLASSES:raise ValueError('invalid header')
    size=(1+n)*((d+63)//64)*8
    if len(data)!=HDR.size+size+4 or zlib.crc32(data[:-4])!=struct.unpack_from('<I',data,len(data)-4)[0]:raise ValueError('length or CRC')
    a=np.frombuffer(data,dtype='<u8',offset=HDR.size,count=size//8).reshape(n+1,-1)
    if d%64 and np.any(a[:,-1]>>np.uint64(d%64)):raise ValueError('padding')
    return r,d,a[:1],a[1:]

def endpoint(data,native=None):
    r,d,q,p=decode(data);s=(native.scores(q,p,d) if native else scores(q,p,d))[0]
    body=struct.pack('<4sQI',b'HDR1',r,len(s))+s.astype('<i4').tobytes();return body+struct.pack('<I',zlib.crc32(body))

def resources(d,classes,lanes):
    """Analytical 64-bit banks, 512 rows per RAMB36, no parity bits used."""
    if not 1<=d<=MAX_D or not 1<=classes<=MAX_CLASSES or lanes not in (1,2,4,8,16):raise ValueError('resource bounds')
    words=(d+63)//64;rows=(words+lanes-1)//lanes
    model=lanes*((classes*rows+511)//512);query=lanes*((rows+511)//512)
    return dict(d=d,classes=classes,lanes=lanes,model_bytes=classes*words*8,bram36_model=model,bram36_query=query,bram36_total=model+query,ideal_word_steps=classes*rows,margin_bram36=445-model-query)

def from_byte_rows(a,d,bitorder):
    """Explicit conversion from earlier MSB-first or little-endian byte-packed rows."""
    a=np.asarray(a)
    if a.ndim!=2 or a.dtype!=np.uint8 or not 1<=d<=MAX_D or a.shape[1]!=(d+7)//8 or bitorder not in ('big','little'):raise ValueError('byte packing contract')
    return pack(np.unpackbits(a,axis=1,count=d,bitorder=bitorder))

def decode_response(data,request_id,classes,d):
    if not isinstance(data,bytes) or not 1<=classes<=MAX_CLASSES or not 1<=d<=MAX_D or len(data)!=16+classes*4+4:raise ValueError('response length')
    if struct.unpack_from('<4sQI',data)!=(b'HDR1',request_id,classes) or zlib.crc32(data[:-4])!=struct.unpack_from('<I',data,len(data)-4)[0]:raise ValueError('response identity or CRC')
    r=np.frombuffer(data,dtype='<i4',count=classes,offset=16)
    if np.any(np.abs(r.astype(np.int64))>d) or np.any((d-r)%2):raise ValueError('impossible binary scores')
    return r.copy()
