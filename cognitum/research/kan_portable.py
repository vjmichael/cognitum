"""Safe, pure NumPy CPU inference for advanced Zog Zoo KAN. No pickle.

Uses only NumPy and portable array operations, suited to software reference
for LUT approximations on FPGA/ASIC. Not a synthesized hardware design.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np


def _silu(z):
    return z/(1+np.exp(-np.clip(z,-70,70)))


def _basis(x,grid,degree,kind):
    xx=x[:,:,None]
    if kind=='rbf':
        scale=np.maximum((grid[:,-1]-grid[:,0])/ (grid.shape[1]-1),1e-4)
        return np.exp(-((xx-grid[None,:,:])/scale[None,:,None])**2)
    b=((xx>=grid[None,:,:-1])&(xx<grid[None,:,1:])).astype(x.dtype)
    for k in range(1,degree+1):
        dl=grid[:,k:-1]-grid[:,:-(k+1)]
        dr=grid[:,k+1:]-grid[:,1:-k]
        b=((xx-grid[None,:,:-(k+1)])/dl[None,:,:]*b[:,:,:-1]
          +(grid[None,:,k+1:]-xx)/dr[None,:,:]*b[:,:,1:])
    return b


class PortableKAN:
    def __init__(self,layers):
        if not layers: raise ValueError('empty layers')
        self.layers=layers
        self.refresh_parameters()

    def refresh_parameters(self):
        """Compile masked matrices once for repeat inference.

        Call this after directly changing the public layer weights/masks.
        Saved checkpoints and NumPy computation remain unchanged.
        """
        self._matrices = []
        for lay in self.layers:
            spl = lay['spline']; mask=lay['mask']
            w = (spl * mask[:,:,None]).reshape(spl.shape[0], -1).T.copy()
            base = ((lay['base']*mask).T.copy() if lay['base'] is not None else None)
            self._matrices.append((w, base))
    @classmethod
    def from_model(cls,model):
        layers=[]
        for layer in model.layers:
            layers.append(dict(grid=layer.grid.detach().cpu().numpy().copy(),
             spline=layer.spline_weight.detach().cpu().numpy().copy(),
             base=layer.base_weight.detach().cpu().numpy().copy() if layer.base_weight is not None else None,
             bias=layer.bias.detach().cpu().numpy().copy() if layer.bias is not None else None,
             mask=layer.edge_mask.detach().cpu().numpy().copy(),
             kind=layer.basis_kind,degree=layer.degree))
        return cls(layers)
    def __call__(self,x):
        x=np.asarray(x,dtype=np.float32)
        if x.ndim<2: raise ValueError('input needs batch dimension')
        if not np.isfinite(x).all(): raise ValueError('nonfinite inputs')
        shape=x.shape[:-1]; z=x.reshape(-1,x.shape[-1])
        for layer, (spline_matrix, base_matrix) in zip(self.layers,self._matrices):
            grid=layer['grid']
            if z.shape[-1]!=grid.shape[0]:raise ValueError('bad input shape')
            b=_basis(z,grid,layer['degree'],layer['kind'])
            znew=b.reshape(z.shape[0],-1) @ spline_matrix
            if base_matrix is not None: znew += _silu(z) @ base_matrix
            if layer['bias'] is not None:znew+=layer['bias']
            z=znew
        return z.reshape(*shape,-1)
    def save(self,path):
        path=Path(path)
        arrays={};meta={'format':'zogzoo-kan-v3-npz','version':1,'layers':[]}
        for i,lay in enumerate(self.layers):
            md={'kind':lay['kind'],'degree':lay['degree'],'base':lay['base'] is not None,'bias':lay['bias'] is not None}
            meta['layers'].append(md)
            for k in ('grid','spline','base','bias','mask'):
                if lay[k] is not None: arrays[f'l{i}_{k}']=lay[k]
        arrays['__meta_json__']=np.asarray(json.dumps(meta))
        with path.open('wb') as f:np.savez_compressed(f,**arrays)
    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as f:
            m=json.loads(f['__meta_json__'].item())
            if m.get('format')!='zogzoo-kan-v3-npz' or m.get('version')!=1:
                raise ValueError('unsupported portable checkpoint')
            ls=[]
            for i,info in enumerate(m['layers']):
                ls.append(dict(kind=info['kind'],degree=info['degree'],
                     grid=f[f'l{i}_grid'].copy(),spline=f[f'l{i}_spline'].copy(),
                     base=f[f'l{i}_base'].copy() if info['base'] else None,
                     bias=f[f'l{i}_bias'].copy() if info['bias'] else None,
                     mask=f[f'l{i}_mask'].copy()))
        return cls(ls)
