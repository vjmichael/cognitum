"""CIFAR-10 follow-up to E2E: exact assets, original split, RGB FP32/PTQ.
Research only; no network unless --acquire. No fallback to random weights in real mode.
"""
import argparse
import hashlib
import io
import json
import pickle
import tarfile
import time
from pathlib import Path
import numpy as np
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from cognitum.research.hdc_uncertain_visual import LevelEncoder, VisualBank, hamming
from cognitum.research.hdc_visual_closeout import FeatureQuantizer
from cognitum.research.hdc_cifar_fast import FastVisualBank, encode_rows, distance
from tools.cog03e2e_closeout import acquire, PTQ_URL

CIFAR_URL='https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz'
CIFAR_SHA='6d958be074577803d12ecdefd02955f39262c83c16fe9348329d7fe0b5c001ce'
WEIGHT_SHA='7ebf99e03e254b273379b23edca7ec0da9f48273b23a332b93c1c99d49e86e8f'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def verify_asset(path,expected,cap):
    p=Path(path)
    if not p.is_file() or not 0<p.stat().st_size<=cap:raise ValueError('asset absent or size outside bound')
    actual=digest(p)
    if actual!=expected:raise ValueError(f'asset SHA256 mismatch: {actual}')
    return actual

def cifar_arrays(path):
    # Only deserialize exact published archive (Keras SHA256); no extraction.
    verify_asset(path,CIFAR_SHA,200<<20)
    def read(z,name):
        member=z.getmember('cifar-10-batches-py/'+name)
        if not member.isfile() or not 0<member.size<40<<20:raise ValueError('invalid batch member')
        a=pickle.loads(z.extractfile(member).read(),encoding='bytes')
        x=np.asarray(a[b'data']); y=np.asarray(a[b'labels'],np.int64)
        if x.shape!=(10000,3072) or x.dtype!=np.uint8 or y.shape!=(10000,) or not np.isin(y,range(10)).all():raise ValueError('invalid CIFAR batch')
        return x.reshape(-1,3,32,32),y
    with tarfile.open(path,'r:gz') as z:
        train=[read(z,f'data_batch_{i}') for i in range(1,6)];test=read(z,'test_batch')
    x=np.concatenate([a for a,_ in train]);y=np.concatenate([b for _,b in train]); t,ty=test
    if not np.array_equal(np.bincount(y),np.full(10,5000)) or not np.array_equal(np.bincount(ty),np.full(10,1000)):raise ValueError('class counts')
    return x,y,t,ty

def split(y,ty,seed,per_class=100,cal_per_class=32):
    rng=np.random.default_rng(seed); phases=np.array_split(rng.permutation(10),5)
    train=[];cal=[];test=[]
    for k in range(10):
        ii=rng.permutation(np.flatnonzero(y==k));jj=rng.permutation(np.flatnonzero(ty==k)); c=cal_per_class if k in phases[0] else 0
        if len(ii)<c+per_class or len(jj)<per_class:raise ValueError('insufficient class data')
        cal.extend(ii[:c]);train.extend(ii[c:c+per_class]);test.extend(jj[:per_class])
    return np.array(train),np.array(cal),np.array(test),phases

def rgb(a):
    a=np.asarray(a)
    if a.ndim!=4 or a.shape[1]!=3 or not len(a) or a.dtype!=np.uint8:raise ValueError('NCHW uint8 RGB required')
    return a

class RGBMobileNet:
    def __init__(self,path,variant,cal=None,*,random_fixture=False):
        if variant not in ('fp32','ptq'):raise ValueError('variant')
        if random_fixture:
            if path is not None:raise ValueError('fixture cannot load checkpoint')
        else:verify_asset(path,WEIGHT_SHA,30<<20)
        import torch
        from torchvision.models import MobileNet_V2_Weights
        from torchvision.models.quantization import mobilenet_v2
        torch.manual_seed(313);self.variant=variant;self.pretrained=not random_fixture
        self.transform=MobileNet_V2_Weights.IMAGENET1K_V2.transforms()
        self.model=mobilenet_v2(weights=None,quantize=False).eval()
        if not random_fixture:self.model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True)
        if variant=='ptq':
            if 'qnnpack' not in torch.backends.quantized.supported_engines:raise RuntimeError('QNNPACK unavailable')
            torch.backends.quantized.engine='qnnpack';self.model.fuse_model(is_qat=False)
            self.model.qconfig=torch.ao.quantization.get_default_qconfig('qnnpack');torch.ao.quantization.prepare(self.model,inplace=True)
            with torch.inference_mode():
                for i in range(0,len(rgb(cal)),16):self.model(self.input(cal[i:i+16]))
            torch.ao.quantization.convert(self.model,inplace=True)
        for p in self.model.parameters():p.requires_grad_(False)
    def input(self,a):
        import torch
        return self.transform(torch.from_numpy(rgb(a).copy()))
    def extract(self,a):
        import torch
        from torch.nn.functional import adaptive_avg_pool2d
        with torch.inference_mode():
            z=self.model.features(self.model.quant(self.input(a)))
            z=adaptive_avg_pool2d(z,(1,1)).flatten(1)
            if z.shape[1]!=1280 or z.is_quantized!=(self.variant=='ptq'):raise RuntimeError('feature contract')
            if z.is_quantized:return z.int_repr().cpu().numpy(),[float(z.q_scale()),int(z.q_zero_point())]
            return z.cpu().numpy(),None
    def batch(self,a,progress=None):
        xs=[];qp=None
        for i in range(0,len(rgb(a)),16):
            f,q=self.extract(a[i:i+16]);xs.append(f)
            if i and q!=qp:raise RuntimeError('quantization parameters changed')
            qp=q
            if progress and ((i//16+1)%32==0 or i+16>=len(a)):progress(min(i+16,len(a)),len(a))
        return np.concatenate(xs),qp

class RawBank:
    """Matched retained numerical budget, train-prefix threshold; unsupervised."""
    def __init__(self,width,cap,threshold,centroid):
        self.centroid=centroid;self.threshold=threshold;self.n=0
        self.a=np.zeros((cap,width),np.float32 if centroid else np.uint8);self.count=np.zeros(cap,np.int64)
    @property
    def numeric_bytes(self):return self.a.nbytes+self.count.nbytes
    def nearest(self,x):
        if not self.n:return -1,np.inf
        d=np.mean((self.a[:self.n].astype(np.float32)-x.astype(np.float32))**2,axis=1);j=int(d.argmin());return j,float(d[j])
    def predict(self,x):return self.nearest(x)[0]
    def observe(self,x):
        j,d=self.nearest(x)
        if self.n<len(self.a) and d>self.threshold:self.a[self.n]=x;self.count[self.n]=1;self.n+=1
        elif j>=0:
            self.count[j]+=1
            if self.centroid:self.a[j]+=(x-self.a[j])/self.count[j]

def nearest_threshold(a):
    z=a.astype(np.float32);d=((z[:,None]-z[None,:])**2).mean(2);np.fill_diagonal(d,np.inf);return float(np.quantile(d.min(1),.9))

def compare(features,labels,test_features,test_labels,cal,phases,seed,budget,width,kind,d=512):
    q=FeatureQuantizer().fit(cal,width);z=q.transform(features);t=q.transform(test_features);c=q.transform(cal)
    enc=LevelEncoder(width,d,16,seed);cp=encode_rows(enc,c);dist=distance(cp[:,None,:],cp[None,:,:],d).astype(float);np.fill_diagonal(dist,np.inf)
    floor=float(np.clip(1-np.quantile(dist.min(1)/d,.9),.5,.98)); threshold=nearest_threshold(c)
    start_encoding=time.perf_counter();zp=encode_rows(enc,z);tp=encode_rows(enc,t);encoding_seconds=time.perf_counter()-start_encoding
    rows=[]
    for arm in ('merge','fixed','replace','centroid','exemplar'):
        cap=budget-q.numeric_bytes
        if arm in ('centroid','exemplar'):
            bank=RawBank(width,cap//((4 if arm=='centroid' else 1)*width+8),threshold,arm=='centroid');train_view,test_view=z,t;pred=bank.predict;used=q.numeric_bytes+bank.numeric_bytes
        else:
            bank=FastVisualBank(d,min(128,(cap-enc.numeric_bytes)//((d+7)//8+24)),seed=seed,novelty_floor=floor,mode=arm);train_view,test_view=zp,tp;pred=lambda x:bank.predict(x)[0];used=q.numeric_bytes+enc.numeric_bytes+bank.numeric_bytes
        if used>budget:raise RuntimeError('budget violation')
        result=[];best={};seen=[];start=time.perf_counter()
        for ph,classes in enumerate(phases):
            ii=np.flatnonzero(np.isin(labels,classes));ii=np.random.default_rng(seed+100+ph).permutation(ii)
            for i in ii:bank.observe(train_view[i])
            seen.extend(classes); ti=np.flatnonzero(np.isin(test_labels,seen));truth=test_labels[ti]; p=np.array([pred(test_view[i]) for i in ti]);per={}
            for j,cl in enumerate(phases[:ph+1]):
                mask=np.isin(truth,cl);per[j]=float(adjusted_rand_score(truth[mask],p[mask]));best[j]=max(best.get(j,-1),per[j])
            result.append(dict(phase=ph,n=len(ti),ari=float(adjusted_rand_score(truth,p)),nmi=float(normalized_mutual_info_score(truth,p)),forgetting=float(np.mean([best[j]-per[j] for j in range(ph)])) if ph else 0.,new_pair_ari=per[ph],clusters=bank.n))
        rows.append(dict(seed=seed,feature=kind,width=width,method=arm,budget=budget,numeric_bytes=used,phases=result,seconds=time.perf_counter()-start,merges=getattr(bank,'merges',0),offline_packed_cache_bytes=zp.nbytes+tp.nbytes,shared_encoding_seconds=encoding_seconds))
    return rows

def run(path,weight,fixture=False,full=False,progress=None):
    if fixture:
        rng=np.random.default_rng(321);y=np.repeat(np.arange(10),8);ty=np.repeat(np.arange(10),4);x=rng.integers(0,256,(len(y),3,32,32),dtype=np.uint8);t=rng.integers(0,256,(len(ty),3,32,32),dtype=np.uint8)
    else:
        print("Verifying exact CIFAR-10 archive and pretrained MobileNetV2 weights",flush=True)
        verify_asset(weight,WEIGHT_SHA,30<<20);x,y,t,ty=cifar_arrays(path)
        print("Verified CIFAR-10 official train/test arrays",flush=True)
    seeds=[2301] if fixture else [2301,2309];rows=[];records=[];probes=[]
    for seed in seeds:
        i,c,j,phases=split(y,ty,seed,4 if fixture else 100,2 if fixture else 32);a,ca,b=x[i],x[c],t[j];labels,truth=y[i],ty[j];imgs=np.concatenate([ca,a,b]);views={'pixels':imgs.reshape(len(imgs),-1)}
        records.append(dict(seed=seed,train_indices=i.tolist(),calibration_indices=c.tolist(),test_indices=j.tolist(),phase_classes=[p.tolist() for p in phases]))
        if not fixture or full:
            import torch
            torch.set_num_threads(1)
            for variant in ('fp32','ptq'):
                print(f'seed {seed} {variant} preparing model',flush=True)
                start=time.perf_counter();m=RGBMobileNet(weight,variant,ca,random_fixture=fixture);prepared=time.perf_counter()-start;start=time.perf_counter();f,qp=m.batch(imgs,lambda done,total:print(f'seed {seed} {variant} feature progress {done}/{total}',flush=True));elapsed=time.perf_counter()-start
                if not fixture and not np.any(f.var(0)>0):raise RuntimeError('degenerate feature values')
                print(f"seed {seed} {variant} features: {elapsed:.3f}s",flush=True);views[variant]=f;records.append(dict(seed=seed,variant=variant,pretrained=m.pretrained,shape=list(f.shape),dtype=str(f.dtype),qparams=qp,sha256=hashlib.sha256(f.tobytes()).hexdigest(),seconds=elapsed,prepare_seconds=prepared,checkpoint_bytes=Path(weight).stat().st_size if weight else None))
        for kind,f in views.items():
            fc,fa,fb=f[:len(c)],f[len(c):len(c)+len(i)],f[-len(j):]
            # Supervised representation sanity control, not the unsupervised memory contest.
            scaler=StandardScaler().fit(fa.astype(np.float32));model=LogisticRegression(max_iter=400,C=1).fit(scaler.transform(fa.astype(np.float32)),labels)
            probes.append(dict(seed=seed,feature=kind,accuracy=float(model.score(scaler.transform(fb.astype(np.float32)),truth)),numeric_bytes=sum(v.nbytes for v in (model.coef_,model.intercept_,scaler.mean_,scaler.var_,scaler.scale_))))
            for width in ([64] if fixture else [64,256]):
                for budget in ([32768] if fixture else [32768,65536]):
                    rows.extend(compare(fa,labels,fb,truth,fc,phases,seed,budget,width,kind))
                    print(f'seed {seed} {kind} width {width} budget {budget}: {len(rows)} rows',flush=True)
                    if progress:Path(progress).write_text(json.dumps(dict(complete=False,fixture=fixture,rows=rows,records=records,supervised_probes=probes),indent=2)+'\n',encoding='utf8')
    return dict(complete=True,fixture=fixture,cifar_sha256=None if fixture else CIFAR_SHA,checkpoint_sha256=None if fixture else WEIGHT_SHA,rows=rows,records=records,supervised_probes=probes,scope='100/class train and official test; 32/class disjoint first-increment calibration; FP32 and independently verified QNNPACK PTQ (not QAT); unsupervised learner caps exclude frozen CNN, feature cache, scratch and framework; probes separate supervised controls; no CORe50 or physical FPGA claim')

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--data',required=True);p.add_argument('--acquire',action='store_true');p.add_argument('--fixture',action='store_true');p.add_argument('--native-fixture',action='store_true');a=p.parse_args();root=Path(a.data);root.mkdir(parents=True,exist_ok=True)
    if a.acquire and (a.fixture or a.native_fixture):raise ValueError('fixture acquisition forbidden')
    if a.native_fixture and not a.fixture:raise ValueError('native-fixture requires fixture')
    cf=root/'cifar-10-python.tar.gz';w=root/'mobilenet_v2-7ebf99e0.pth'
    if a.acquire:
        for url,path,cap,expected in [(CIFAR_URL,cf,200<<20,CIFAR_SHA),(PTQ_URL,w,30<<20,WEIGHT_SHA)]:
            print(f"Acquiring {path.name} (verified content required)",flush=True)
            for attempt in range(2):
                try:acquire(url,path,cap);verify_asset(path,expected,cap);print(f"Verified {path.name}",flush=True);break
                except (ValueError,OSError) as e:
                    print(f'acquisition attempt {attempt+1}: {e}',flush=True);path.unlink(missing_ok=True)
                    if attempt:raise
    result=run(None if a.fixture else cf,None if a.fixture else w,a.fixture,a.native_fixture,Path(a.out).with_suffix('.partial.json'))
    Path(a.out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
