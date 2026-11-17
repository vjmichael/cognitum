"""Bounded, CPU-only research algebra. Not a registered production capability."""
from dataclasses import dataclass
from math import isqrt
import numpy as np

FAMILIES = ('BSC', 'MAP', 'HRR', 'FHRR', 'BSBC', 'CGR', 'MCR', 'VTB')
MODULAR = ('BSBC', 'CGR', 'MCR')

@dataclass(frozen=True)
class Spec:
    family: str
    dimension: int
    block_size: int = 0

    def __post_init__(self):
        if self.family not in FAMILIES or type(self.dimension) is not int or not 1 <= self.dimension <= 65536:
            raise ValueError('invalid family or dimension')
        if type(self.block_size) is not int or (self.family in MODULAR and not 2 <= self.block_size <= 65536) or (self.family not in MODULAR and self.block_size != 0):
            raise ValueError('invalid block size')
        if self.family == 'VTB' and isqrt(self.dimension)**2 != self.dimension:
            raise ValueError('VTB requires a square dimension')

    @property
    def dtype(self):
        return np.dtype(np.bool_ if self.family == 'BSC' else np.int64 if self.family in MODULAR else np.complex64 if self.family == 'FHRR' else np.float32)

    def checked(self, a):
        a = np.asarray(a)
        if a.shape != (self.dimension,) or a.dtype != self.dtype or not np.isfinite(a).all():
            raise ValueError('invalid shape, dtype or finite values')
        if self.family in MODULAR and ((a < 0).any() or (a >= self.block_size).any()):
            raise ValueError('invalid modular symbol')
        return a

    def bind(self, a, b):
        a, b = self.checked(a), self.checked(b)
        if self.family == 'BSC': return a ^ b
        if self.family in MODULAR: return (a + b) % self.block_size
        if self.family in ('MAP', 'FHRR'): out = a * b
        elif self.family == 'HRR': out = np.fft.ifft(np.fft.fft(a) * np.fft.fft(b)).real
        else:
            n = isqrt(self.dimension)
            out = (np.sqrt(n) * (a.reshape(n, n) @ b.reshape(n, n).T)).reshape(-1)
        return self.checked(out.astype(self.dtype))

    def inverse(self, a):
        a = self.checked(a)
        if self.family in ('BSC', 'MAP'): return a.copy()
        if self.family in MODULAR: return (-a) % self.block_size
        if self.family == 'FHRR': return a.conj()
        if self.family == 'HRR': return np.roll(a[::-1], 1)
        n = isqrt(self.dimension)
        return a.reshape(n, n).T.copy().reshape(-1)

    def unbind(self, role, bound):
        # VTB binds value on the left, role on the right. HRR and VTB
        # use approximate inverses; arbitrary MAP/FHRR accumulators are not units.
        return self.bind(bound, self.inverse(role))

    def permute(self, a, shift):
        if type(shift) is not int: raise ValueError('invalid shift')
        return np.roll(self.checked(a), shift % self.dimension)

    def bundle(self, rows, *, tie=None):
        """Additive real/phase accumulator; binary majority; modular mode/phasor.

        BSC ties require a supplied Boolean tie vector. Mode ties pick the
        smallest symbol. MCR zero resultant uses rounded arithmetic mean.
        """
        rows = np.asarray(rows)
        if rows.ndim != 2 or rows.shape[1] != self.dimension or not 1 <= len(rows) <= 4096:
            raise ValueError('invalid bundle dimensions')
        for row in rows: self.checked(row)
        if self.family == 'BSC':
            votes = rows.sum(axis=0, dtype=np.int64) * 2 - len(rows)
            if (votes == 0).any() and tie is None: raise ValueError('explicit BSC tie vector required')
            return np.where(votes == 0, self.checked(tie) if tie is not None else False, votes > 0)
        if tie is not None: raise ValueError('tie vector only defined for BSC')
        if self.family in ('BSBC', 'CGR'):
            def mode(col):
                values, counts = np.unique(col, return_counts=True)
                return values[np.argmax(counts)]
            return np.asarray([mode(col) for col in rows.T], dtype=self.dtype)
        if self.family == 'MCR':
            ph = np.exp(2j*np.pi*rows/self.block_size).sum(axis=0)
            symbols = np.where(np.abs(ph) <= 1e-8, rows.mean(axis=0), np.angle(ph)*self.block_size/(2*np.pi))
            return (np.rint(symbols).astype(np.int64) % self.block_size)
        return self.checked(rows.sum(axis=0, dtype=self.dtype))

    def similarity(self, a, b):
        a,b = self.checked(a),self.checked(b)
        if self.family == 'BSC': return float(1-2*np.mean(a!=b))
        if self.family == 'BSBC': return float(np.mean(a==b))
        if self.family in ('MCR','CGR'):
            diff=(a-b)%self.block_size
            return float(1-4*np.mean(np.minimum(diff,self.block_size-diff))/self.block_size)
        x,y=a.astype(np.complex128),b.astype(np.complex128)
        denom=np.linalg.norm(x)*np.linalg.norm(y)
        if denom==0: raise ValueError('undefined zero-vector cosine')
        return float(np.vdot(x,y).real/denom)

    def native(self, operation, a, b=None, *, shift=1):
        """Use actual pinned TorchHD subclass; missing dependency must fail explicitly."""
        from importlib.metadata import version
        import torch
        import torchhd as hd
        if version('torch-hd') != '5.8.4': raise RuntimeError('unreviewed TorchHD version')
        def tensor(x):
            t = hd.ensure_vsa_tensor(torch.from_numpy(self.checked(x).copy()), vsa=self.family)
            if self.family in MODULAR: t.block_size = self.block_size
            return t
        if operation == 'bundle':
            rows = np.asarray(a)
            self.bundle(rows)  # same shape/type validation; no ambiguous BSC ties
            source = hd.ensure_vsa_tensor(torch.from_numpy(rows.copy()), vsa=self.family)
            if self.family in MODULAR: source.block_size = self.block_size
            result = hd.multibundle(source)
            return self.checked(result.detach().cpu().numpy().copy())
        x = tensor(a)
        if operation == 'similarity': return float(hd.cos(x,tensor(b)).item())
        if operation == 'bind': result = hd.bind(x, tensor(b))
        elif operation == 'inverse': result = hd.inverse(x)
        elif operation == 'permute':
            if type(shift) is not int: raise ValueError('invalid shift')
            result = hd.permute(x, shifts=shift % self.dimension)
        else: raise ValueError('unsupported operation')
        return self.checked(result.detach().cpu().numpy().copy())
