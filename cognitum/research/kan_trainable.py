"""COG-04A: newly reconstructed, bounded CPU research KAN, not recovered K4.

Fixed knots; edge coefficient/bias learning; independent float64 calculus.
No registry, execution grants, model-visible tools or automatic approval.
Portable export is a lossy binary32 candidate for the existing reviewed profile.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import numpy as np
from numpy.polynomial import chebyshev as cheb
from numpy.polynomial.legendre import leggauss

MAX_ROWS = 2048
MAX_WIDTH = 8
MAX_LAYERS = 2
MAX_ABS = 1000.


def _need(ok, msg):
    if not ok:
        raise ValueError(msg)


def _array(x):
    a = np.asarray(x)
    _need(a.dtype.kind in 'fiu' and a.size <= MAX_ROWS * MAX_WIDTH,
          'numeric bounded array required')
    a = np.asarray(a, dtype=np.float64)
    _need(np.all(np.isfinite(a)) and np.all(np.abs(a) <= MAX_ABS), 'array range')
    return a


def _frozen(x):
    a = _array(x)
    return np.frombuffer(a.tobytes(order='C'), dtype=np.float64).reshape(a.shape)


@dataclass(frozen=True, slots=True)
class Layer:
    kind: str
    degree: int
    grid: np.ndarray
    coefficients: np.ndarray
    mask: np.ndarray
    bias: np.ndarray

    def __post_init__(self):
        _need(self.kind in ('spline', 'spline_clamped', 'rbf', 'chebyshev') and type(self.degree) is int, 'basis')
        for name in ('grid', 'coefficients', 'mask', 'bias'):
            object.__setattr__(self, name, _frozen(getattr(self, name)))
        g, w, m, b = self.grid, self.coefficients, self.mask, self.bias
        _need(g.ndim == 2 and w.ndim == 3 and 1 <= g.shape[0] <= MAX_WIDTH and
              1 <= w.shape[0] <= MAX_WIDTH and w.shape[1] == g.shape[0], 'layer shape')
        k = g.shape[1]
        if self.kind == 'spline_clamped':
            p=self.degree
            _need(1<=p<=3 and 2*(p+1)<=k<=12, 'clamped spline profile')
            _need(np.all(g[:,:p+1]==g[:,0,None]) and np.all(g[:,-p-1:]==g[:,-1,None]) and
                  np.all(np.diff(g[:,p:k-p],axis=1)>=1e-4), 'clamped knot multiplicities')
        else:
            _need(np.all(np.diff(g, axis=1) >= 1e-4), 'separated knots')
        if self.kind == 'chebyshev':
            _need(k == 2 and 0 <= self.degree <= 8, 'chebyshev profile'); n = self.degree + 1
        elif self.kind == 'rbf':
            _need(3 <= k <= 12 and self.degree == 0, 'rbf profile'); n = k
        else:
            _need(3 <= k <= 12 and 0 <= self.degree <= 3 and k > self.degree + 1, 'spline profile')
            n = k - self.degree - 1
        _need(w.shape[2] == n and m.shape == w.shape[:2] and b.shape == (w.shape[0],), 'parameter shape')
        _need(np.all((m == 0) | (m == 1)), 'binary mask')

    @property
    def inputs(self): return self.grid.shape[0]
    @property
    def outputs(self): return self.coefficients.shape[0]

    def updated(self, coefficients, bias):
        return Layer(self.kind, self.degree, self.grid, coefficients, self.mask, bias)

    def basis(self, x, order=0):
        """Values and analytic derivatives w.r.t. input, not basis parameters.

        Splines have the interior one-sided value at the upper endpoint.
        Nonsmooth knots and endpoint derivatives are refused, not guessed.
        """
        x = _array(x)
        _need(type(order) is int and 0 <= order <= 2, 'derivative order')
        _need(x.ndim == 2 and 1 <= len(x) <= MAX_ROWS and x.shape[1] == self.inputs, 'input shape')
        g = self.grid
        _need(np.all(x >= g[:, 0]) and np.all(x <= g[:, -1]), 'outside layer domain')
        if self.kind == 'rbf':
            s = (g[:, -1] - g[:, 0]) / (g.shape[1] - 1)
            z = (x[:, :, None] - g) / s[:, None]
            b = np.exp(-z*z)
            d = -2*z/s[:, None]*b
            h = (4*z*z-2)/s[:, None]**2*b
        elif self.kind == 'chebyshev':
            scale = 2/(g[:, 1]-g[:, 0]); z = (x-g[:, 0])*scale-1
            b, d, h = [np.zeros((*x.shape, self.degree+1)) for _ in range(3)]
            for j in range(self.degree+1):
                c = np.zeros(j+1); c[j] = 1
                b[:, :, j] = cheb.chebval(z, c)
                d[:, :, j] = cheb.chebval(z, cheb.chebder(c))*scale
                h[:, :, j] = cheb.chebval(z, cheb.chebder(c, m=2))*scale**2
        else:
            if order:
                _need(not np.any((x == g[:, 0]) | (x == g[:, -1])), 'endpoint derivative undefined in this profile')
                if self.degree <= order:
                    _need(not np.any(x[:, :, None] == g[None, :, 1:-1]), 'nonsmooth spline knot')
            xx = x[:, :, None]
            b = ((xx >= g[:, :-1]) & (xx < g[:, 1:])).astype(float)
            for i in range(self.inputs):
                last=np.flatnonzero(np.diff(g[i])>0)[-1]
                b[:,i,last]=np.where(x[:,i]==g[i,-1],1.,b[:,i,last])
            d = np.zeros_like(b); h = np.zeros_like(b)
            for k in range(1, self.degree+1):
                dl = g[:, k:-1] - g[:, :-(k+1)]; dr = g[:, k+1:] - g[:, 1:-k]
                il=np.divide(1.,dl,out=np.zeros_like(dl),where=dl>0)
                ir=np.divide(1.,dr,out=np.zeros_like(dr),where=dr>0)
                u = (xx-g[:, :-(k+1)])*il; v = (g[:, k+1:]-xx)*ir
                b, d, h = (u*b[:, :, :-1]+v*b[:, :, 1:],
                           u*d[:, :, :-1]+v*d[:, :, 1:]+b[:, :, :-1]*il-b[:, :, 1:]*ir,
                           u*h[:, :, :-1]+v*h[:, :, 1:]+2*d[:, :, :-1]*il-2*d[:, :, 1:]*ir)
        return (b, d, h)[:order+1]

    def edge_integrals(self, low, high):
        """Per-edge integrals over independent coordinate intervals.

        Gaussian erf and piecewise polynomial Gauss-Legendre formulas;
        float64 estimates of represented functions, no interval certificate.
        Bias is excluded; integral of a composed multidimensional network is separate.
        """
        lo, hi = _array(low), _array(high)
        _need(lo.shape == hi.shape == (self.inputs,) and np.all(lo <= hi) and
              np.all(lo >= self.grid[:, 0]) and np.all(hi <= self.grid[:, -1]), 'integral bounds')
        out = np.zeros((self.outputs,self.inputs))
        for i, (a,b) in enumerate(zip(lo,hi)):
            if a == b: continue
            g = self.grid[i]
            if self.kind == 'rbf':
                s=(g[-1]-g[0])/(len(g)-1)
                v=np.array([s*math.sqrt(math.pi)/2*(math.erf((b-c)/s)-math.erf((a-c)/s)) for c in g])
            else:
                nodes, weights = leggauss(5)  # integrates polynomial degree <=9 exactly in exact arithmetic
                cuts = [a]+[t for t in g if a<t<b]+[b]
                v=np.zeros(self.coefficients.shape[2])
                for l,r in zip(cuts,cuts[1:]):
                    pts=np.tile((self.grid[:,0]+self.grid[:,-1])/2,(5,1))
                    pts[:,i]=(l+r)/2+(r-l)/2*nodes
                    v += (r-l)/2*(weights @ self.basis(pts)[0][:,i,:])
            out[:,i]=(self.coefficients[:,i,:] @ v)*self.mask[:,i]
        return out


@dataclass(frozen=True, slots=True)
class Network:
    layers: tuple

    def __post_init__(self):
        _need(type(self.layers) is tuple and 1 <= len(self.layers) <= MAX_LAYERS and
              all(type(l) is Layer for l in self.layers), 'layer count')
        _need(all(a.outputs == b.inputs for a,b in zip(self.layers,self.layers[1:])), 'composition shape')

    def evaluate(self, x, order=0):
        x = _array(x)
        _need(type(order) is int and 0<=order<=2 and x.ndim==2 and 1<=len(x)<=MAX_ROWS and x.shape[1]==self.layers[0].inputs, 'evaluation shape/order')
        n = x.shape[1]; j = np.broadcast_to(np.eye(n),(len(x),n,n)).copy() if order else None
        h = np.zeros((len(x),n,n,n)) if order==2 else None; z=x
        for l in self.layers:
            basis=l.basis(z,order); w=l.coefficients*l.mask[:,:,None]
            z=np.einsum('nik,oik->no',basis[0],w)+l.bias
            if order:
                local=np.einsum('nik,oik->noi',basis[1],w)
                if order==2:
                    second=np.einsum('nik,oik->noi',basis[2],w)
                    h=np.einsum('noi,niab->noab',local,h)+np.einsum('noi,nia,nib->noab',second,j,j)
                j=np.einsum('noi,nia->noa',local,j)
        _need(np.isfinite(z).all() and (not order or np.isfinite(j).all()) and
              (order!=2 or np.isfinite(h).all()), 'nonfinite result')
        return (z,j,h)[:order+1]

    def loss_gradient(self,x,y,ridge=0.):
        """Backpropagate through edge coefficients and biases; fixed grids/masks."""
        _need(type(ridge) in (int,float) and 0<=ridge<=1, 'ridge')
        x,y=_array(x),_array(y); z=x; records=[]
        for i,l in enumerate(self.layers):
            bs=l.basis(z,int(i>0)); w=l.coefficients*l.mask[:,:,None]
            records.append((l,bs,w));z=np.einsum('nik,oik->no',bs[0],w)+l.bias
        _need(y.shape==z.shape,'target shape')
        loss=float(np.mean((z-y)**2)+ridge*sum(np.sum(w*w) for _,_,w in records))
        delta=2*(z-y)/z.size; grads=[]
        for l,bs,w in reversed(records):
            dw=(np.einsum('no,nik->oik',delta,bs[0])+2*ridge*w)*l.mask[:,:,None]
            grads.append((dw,delta.sum(axis=0)))
            if len(bs)==2:delta=np.einsum('no,noi->ni',delta,np.einsum('nik,oik->noi',bs[1],w))
        _need(math.isfinite(loss) and all(np.isfinite(v).all() for pair in grads for v in pair), 'nonfinite gradient')
        return loss,tuple(reversed(grads))

    def fit(self,x,y,steps=100,rate=.1,ridge=0.):
        """Bounded deterministic full-batch gradient descent with monotone line search.

        Reject domain-violating updates, never silently extrapolate. Training is local research.
        """
        _need(type(steps) is int and 1<=steps<=500 and type(rate) in (int,float) and 0<rate<=1, 'training budget')
        model=self; loss,grad=model.loss_gradient(x,y,ridge); history=[loss]
        for _ in range(steps):
            alpha=rate
            for _ in range(12):
                try:
                    trial=Network(tuple(l.updated(l.coefficients-alpha*dw,l.bias-alpha*db) for l,(dw,db) in zip(model.layers,grad)))
                    new,ng=trial.loss_gradient(x,y,ridge)
                except ValueError:alpha*=.5;continue
                if new < loss-1e-15:
                    model,loss,grad=trial,new,ng;history.append(loss);break
                alpha*=.5
            else:break
        return model,tuple(history)

    def fit_linear(self,x,y,ridge=1e-8):
        """One-layer fixed-basis least squares, per output, with masked edges.

        QR/SVD least squares on augmented ridge design, no normal equations.
        """
        _need(len(self.layers)==1 and type(ridge) in (int,float) and 0<=ridge<=1,'linear fit profile')
        l=self.layers[0]; b=l.basis(x)[0];y=_array(y)
        _need(y.shape==(len(b),l.outputs),'target shape')
        w=np.zeros_like(l.coefficients);bias=np.zeros(l.outputs)
        for o in range(l.outputs):
            active=np.broadcast_to(l.mask[o,:,None].astype(bool),l.coefficients[o].shape).ravel()
            design=np.column_stack((b.reshape(len(b),-1)[:,active],np.ones(len(b))))
            penalty=np.eye(design.shape[1])*math.sqrt(ridge);penalty[-1,-1]=0
            coef=np.linalg.lstsq(np.vstack((design,penalty)),np.r_[y[:,o],np.zeros(len(penalty))],rcond=None)[0]
            w[o].flat[active]=coef[:-1];bias[o]=coef[-1]
        return Network((l.updated(w,bias),))

    def research_snapshot(self):
        """Canonical binary64 research snapshot; never a MEL approval.

        Preserve alternative basis parameters without pretending that the
        existing worker supports them. Caller retains split/fit evidence separately.
        """
        data={'schema':'cognitum.cog04a.kan.v1','layers':[
            dict(kind=l.kind,degree=l.degree,grid=l.grid.tolist(),coefficients=l.coefficients.tolist(),
                 mask=l.mask.tolist(),bias=l.bias.tolist()) for l in self.layers]}
        raw=json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')
        _need(0<len(raw)<=65536,'snapshot size')
        return raw,hashlib.sha256(raw).hexdigest()

    def checkpoint_candidate(self):
        """Existing layers-only MEL KanInput profile; never an approval or grant.

        Alternate bases and nonportable grids are refused. The caller must
        independently inspect the float32 candidate and approve it externally.
        """
        from cognitum.mel import engines_pb2 as pb
        frames=[]
        for l in self.layers:
            _need(l.kind in ('rbf','spline'),'basis has no existing wire profile')
            grid=l.grid.astype(np.float32)
            _need(np.all(np.diff(grid,axis=1)>=1e-4),'binary32 knot separation')
            frames.append(pb.KanLayer(inputs=l.inputs,outputs=l.outputs,knots=grid.shape[1],
                                     basis=pb.RBF if l.kind=='rbf' else pb.BSPLINE,degree=l.degree,
                                     grid=grid.ravel(),coefficients=l.coefficients.astype(np.float32).ravel(),
                                     mask=l.mask.astype(np.float32).ravel(),bias=l.bias.astype(np.float32)))
        raw=pb.KanInput(layers=frames).SerializeToString(deterministic=True)
        _need(0<len(raw)<=16384,'checkpoint byte budget')
        return raw,hashlib.sha256(raw).hexdigest()


def load_candidate(raw,expected_sha256):
    """Decode pinned layers-only binary32 bytes, no authority and no implicit promotion."""
    from cognitum.mel import engines_pb2 as pb
    from google.protobuf.message import DecodeError
    _need(type(raw) is bytes and 0<len(raw)<=16384 and hashlib.sha256(raw).hexdigest()==expected_sha256,'checkpoint pin')
    try:m=pb.KanInput.FromString(raw)
    except DecodeError as exc:raise ValueError('checkpoint wire') from exc
    clean=pb.KanInput();clean.CopyFrom(m);clean.DiscardUnknownFields()
    _need(clean.SerializeToString(deterministic=True)==raw and m.rows==0 and not m.coordinates and 1<=len(m.layers)<=MAX_LAYERS,'checkpoint profile')
    layers=[]
    for v in m.layers:
        i,o,k,p=v.inputs,v.outputs,v.knots,v.degree
        _need(1<=i<=8 and 1<=o<=8 and 3<=k<=12 and not v.base and v.basis in (pb.RBF,pb.BSPLINE),'unsupported checkpoint')
        kind='rbf' if v.basis==pb.RBF else 'spline';n=k if kind=='rbf' else k-p-1
        _need(1<=n<=12 and len(v.grid)==i*k and len(v.coefficients)==o*i*n and len(v.mask)==o*i and len(v.bias)==o,'checkpoint shape')
        layers.append(Layer(kind,p,np.array(v.grid).reshape(i,k),np.array(v.coefficients).reshape(o,i,n),np.array(v.mask).reshape(o,i),np.array(v.bias)))
    return Network(tuple(layers))


def load_snapshot(raw,expected_sha256):
    _need(type(raw) is bytes and 0<len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==expected_sha256,'snapshot pin')
    try:data=json.loads(raw.decode('ascii'))
    except (ValueError,UnicodeDecodeError,RecursionError) as exc:raise ValueError('snapshot JSON') from exc
    _need(type(data) is dict and set(data)=={'schema','layers'} and data['schema']=='cognitum.cog04a.kan.v1' and
          type(data['layers']) is list and 1<=len(data['layers'])<=MAX_LAYERS,'snapshot schema')
    layers=[]
    for v in data['layers']:
        _need(type(v) is dict and set(v)=={'kind','degree','grid','coefficients','mask','bias'},'snapshot layer schema')
        layers.append(Layer(**v))
    model=Network(tuple(layers));_need(model.research_snapshot()[0]==raw,'noncanonical snapshot')
    return model
