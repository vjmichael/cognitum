"""Research-only feature/uncertainty adapters; no network at import."""
import hashlib
from pathlib import Path
import numpy as np
from .hdc_uncertain_visual import LevelEncoder, Mondrian, scores, nonconformity, hamming


def group_partition(train_subjects,test_subjects,seed):
    a=np.unique(train_subjects);b=np.unique(test_subjects)
    if len(a)<12 or np.intersect1d(a,b).size:raise ValueError('subject leakage or insufficient calibration subjects')
    a=np.random.default_rng(seed).permutation(a);cal=a[:max(10,len(a)//2)];fit=a[len(cal):]
    if len(fit)<2:raise ValueError('insufficient fit subjects')
    return fit,cal,b


def perturb(x,kind):
    x=np.asarray(x,dtype=np.float64)
    if x.ndim!=3 or x.shape[1:]!=(128,9) or not np.isfinite(x).all():raise ValueError('IMU shape')
    if kind=='clean':return x.copy()
    if kind=='gain':return x*1.25+.10
    if kind=='offset':return x*.8-.12
    if kind=='unseen':return x[:,:,np.array([1,2,0,4,5,3,7,8,6])]*1.6+.3
    raise ValueError('unknown condition')

class IMUEncoder:
    def __init__(self,dimension=256,seed=0):self.dimension=dimension;self.level=LevelEncoder(18,dimension,16,seed)
    @staticmethod
    def features(x):
        x=perturb(x,'clean').reshape(-1,8,16,9)
        return np.concatenate([x.mean(2),x.std(2)],axis=-1)
    def fit(self,x):
        f=self.features(x).reshape(-1,18);self.lo=np.quantile(f,.02,axis=0);self.span=np.maximum(np.quantile(f,.98,axis=0)-self.lo,1e-6);return self
    def encode(self,x):
        f=self.features(x);q=np.rint(np.clip((f-self.lo)/self.span,0,1)*15).astype(np.uint8)
        b=np.stack([np.unpackbits(self.level.encode(row),count=self.dimension) for row in q.reshape(-1,18)]).reshape(-1,8,self.dimension)
        pairs=np.roll(b[:,:-1],1,axis=-1)^b[:,1:]
        return (1-2*np.concatenate([b,pairs],axis=1).astype(np.int8))


def robust_calibration(cal_scores,y,groups,alpha=.1):
    a=np.asarray(cal_scores,dtype=np.float64)
    if a.ndim!=3 or not np.isfinite(a).all():raise ValueError('conditions x observations x classes')
    return Mondrian(alpha).fit(a.max(0),y,groups)


class FeatureQuantizer:
    """Fit selection and scaling on a separate prefix only, never held-out images."""
    def fit(self,x,features=64):
        x=np.asarray(x,dtype=np.float64)
        if x.ndim!=2 or len(x)<2 or not 1<=features<=x.shape[1] or not np.isfinite(x).all():raise ValueError('feature fit')
        self.width=x.shape[1];self.indices=np.argsort(-x.var(0),kind='stable')[:features].astype(np.int32)
        v=x[:,self.indices];self.lo=v.min(0).astype(np.float32);self.span=np.maximum(v.max(0)-v.min(0),1e-6).astype(np.float32);return self
    @property
    def numeric_bytes(self):return self.indices.nbytes+self.lo.nbytes+self.span.nbytes
    def transform(self,x):
        a=np.asarray(x,dtype=np.float32)
        if a.shape[-1]!=self.width or not np.isfinite(a).all():raise ValueError('feature input')
        return np.rint(np.clip((a[...,self.indices]-self.lo)/self.span,0,1)*15).astype(np.uint8)


class FrozenMobileNet:
    """Native torch quantized QNNPACK convolution path. Random smoke is explicit.
    Official weights are hash-checked before torch.load; no silent random fallback.
    """
    PREFIX='37f702c5'
    def __init__(self,path=None,*,random_smoke=False):
        if (path is None)==(not random_smoke):raise ValueError('choose verified checkpoint or explicit random smoke')
        self.digest=None;self.file_bytes=None;self.pretrained=not random_smoke
        if path is not None:
            p=Path(path);self.digest=hashlib.sha256(p.read_bytes()).hexdigest();self.file_bytes=p.stat().st_size
            if not self.digest.startswith(self.PREFIX):raise ValueError('unexpected official checkpoint hash prefix')
        import torch
        from torchvision.models.quantization import mobilenet_v2,MobileNet_V2_QuantizedWeights
        if 'qnnpack' not in torch.backends.quantized.supported_engines:raise RuntimeError('qnnpack unavailable')
        torch.manual_seed(313);self.model=mobilenet_v2(weights=None,quantize=True,backend='qnnpack').eval()
        if path is not None:self.model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True)
        for p in self.model.parameters():p.requires_grad_(False)
        self.transform=MobileNet_V2_QuantizedWeights.IMAGENET1K_QNNPACK_V1.transforms()
    def features(self,images):
        import torch
        import torch.nn.functional as F
        a=np.asarray(images)
        if a.ndim!=3 or a.dtype!=np.uint8 or not len(a):raise ValueError('N x H x W uint8 grayscale')
        with torch.inference_mode():
            x=self.transform(torch.from_numpy(a.copy())[:,None].expand(-1,3,-1,-1));q=self.model.features(self.model.quant(x))
            if not q.is_quantized:raise RuntimeError('nonquantized feature path')
            q=F.adaptive_avg_pool2d(q,(1,1)).flatten(1)
            if q.shape[1]!=1280 or not q.is_quantized:raise RuntimeError('unexpected feature tensor')
            return q.int_repr().cpu().numpy(),float(q.q_scale()),int(q.q_zero_point())
