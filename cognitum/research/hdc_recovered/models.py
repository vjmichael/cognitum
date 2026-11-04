"""HDC model families — survey Part I §2.3, Table 2 (Kleyko et al.).

CPU-only, fully vectorized. FPGA mapping (see README):
  bind     = 2-input elementwise LUT (BSC/MAP/FHRR) or FFT block (HRR)
  bundle   = adder tree + sign/phase comparator (majority rule)
  unbind   = same LUT as bind (self-inverse) or conjugate multiply (FHRR)
  cleanup  = comparator tree / content-addressable match

Model notes:
  BSC  — Binary Spatter Codes (Kanerva 1997). ±1; XOR bind (self-inverse);
         majority-rule bundling with deterministic tie-break; Hamming/dot.
         A special case of FHRR restricted to 0/π phases (Plate 1997).
  MAP  — Multiply-Add-Permute (Gayler 1998), bipolar variant. ±1;
         componentwise multiply bind; sign bundling (ties -> +1).
  FHRR — Fourier HRR (Plate 2003). Complex unitary HVs; Hadamard bind;
         unbind = multiply by conjugate (angle subtraction) — near-exact,
         no deconvolution. The standard "unbinds almost exactly" family.
  HRR  — Holographic Reduced Representations (Plate 1995). Real unit HVs;
         circular-convolution bind. Known weakness: heavy-tailed
         deconvolution noise (we measured 0.77 mean / 0.17 min unbind).
"""
from __future__ import annotations

import numpy as np

BIP1 = np.array([-1, 1], dtype=np.int8)


def bipolar_perturb(hv: np.ndarray, kind: str, a: float, rng) -> np.ndarray:
    """Noise for ±1 (BSC/MAP) and float-unit (HRR) models.

    clean    : unchanged
    bitflip  : flip exactly round(a*D) coordinates (sign flip)
    mixture  : (1-a)*hv + a*u in float space, NEVER re-signed. (Re-signing a
               ±1 vector for a<=0.5 is a no-op — a latent bug fixed 2026-10-20.)
    """
    hv = np.asarray(hv)
    D = hv.shape[0]
    if kind == "clean":
        return hv
    if kind == "bitflip":
        k = max(1, int(round(a * D)))
        idx = rng.choice(D, size=k, replace=False)
        out = hv.astype(np.float32).copy()
        out[idx] = -out[idx]
        return out
    if kind == "mixture":
        u = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=D)
        return (1.0 - a) * hv.astype(np.float32) + a * u
    raise ValueError(f"unknown noise kind: {kind!r}")


class Model:
    """Base contract shared by all families. Every primitive is a pure,
    vectorized function of its inputs — the property that makes the algebra
    LUT-mappable on FPGA/ASIC."""

    name = "base"
    itemsize = 1

    def __init__(self, D: int, seed: int = 0):
        self.D = int(D)
        self.seed = int(seed)

    # -- primitives (override) ------------------------------------------------
    def atomic(self, n: int, rng) -> np.ndarray:
        raise NotImplementedError

    def neutral(self) -> np.ndarray:
        """HV for the empty text (corner case; must be a valid member of the space)."""
        raise NotImplementedError

    def bundle(self, hvs: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def bundle_weighted(self, hvs: np.ndarray, weights: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def unbind(self, a: np.ndarray, bound: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def dot_row(self, bank: np.ndarray, q: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        raise NotImplementedError

    def perturb(self, hv: np.ndarray, kind: str, a: float, rng) -> np.ndarray:
        raise NotImplementedError

    # -- introspection --------------------------------------------------------
    def bytes_per_hv(self) -> int:
        return self.D * self.itemsize


class BSC(Model):
    name = "bsc"
    itemsize = 1  # int8

    def __init__(self, D: int, seed: int = 0, multi_bit: int = 1, tie=None):
        super().__init__(D, seed)
        # multi_bit=1: sign (1 bit/dim).  multi_bit=2: levels {-3,-1,+1,+3}
        # (2 bits/dim); multi_bit=4: odd levels up to +-15 (4 bits/dim).
        # Used for the equal-memory comparison (survey §4.1 / checklist F.15):
        # "2-bit/4-bit @ small D vs 1-bit @ 10k".
        if multi_bit not in (1, 2, 4):
            raise ValueError("multi_bit must be 1, 2, or 4")
        self.multi_bit = multi_bit
        if tie is None:
            g = np.random.Generator(np.random.PCG64(0x5EED ^ (seed & 0xFFFF)))
            tie = g.choice(BIP1, size=D)
        self.tie = np.asarray(tie, dtype=np.int8)

    def atomic(self, n, rng):
        return rng.choice(BIP1, size=(n, self.D))

    def neutral(self):
        return np.ones(self.D, dtype=np.int8)

    def _binarize(self, s: np.ndarray) -> np.ndarray:
        if self.multi_bit == 1:
            out = np.where(s > 0, np.int8(1), np.where(s < 0, np.int8(-1), self.tie))
        else:  # multi-bit: keep coarse magnitude (equal-memory comparison)
            lo = -(2 ** (self.multi_bit - 1)) + 1
            c = np.clip(np.round(s), lo, -lo).astype(np.int8)
            c = np.where(c == 0, self.tie, c)
            return c
        return out.astype(np.int8)

    def bundle(self, hvs):
        return self._binarize(np.sum(hvs, axis=0, dtype=np.int32))

    def bundle_weighted(self, hvs, weights):
        w = np.asarray(weights, dtype=np.float32).reshape(-1, 1)
        return self._binarize(np.sum(hvs.astype(np.float32) * w, axis=0,
                                     dtype=np.float32))

    def bind(self, a, b):
        return (a.astype(np.int16) * b.astype(np.int16)).astype(np.int8)

    def unbind(self, a, bound):
        return self.bind(a, bound)  # XOR is self-inverse

    def dot_row(self, bank, q):
        return bank.astype(np.int32) @ q.astype(np.int32)

    def similarity(self, a, b):
        # Cast to int32: NumPy 2.x np.dot on two int8 arrays stays int8 and
        # overflows (e.g. dot of identical ±1 vectors of length D wraps mod 256).
        return float(np.dot(a.astype(np.int32), b.astype(np.int32))) / self.D

    def perturb(self, hv, kind, a, rng):
        out = bipolar_perturb(hv, kind, a, rng)
        return out if kind == "clean" or kind == "mixture" else out.astype(np.int8)


class MAP(Model):
    name = "map"
    itemsize = 1  # int8

    def __init__(self, D: int, seed: int = 0):
        super().__init__(D, seed)

    def atomic(self, n, rng):
        return rng.choice(BIP1, size=(n, self.D))

    def neutral(self):
        return np.ones(self.D, dtype=np.int8)

    def bundle(self, hvs):
        s = np.sum(hvs, axis=0, dtype=np.int32)
        return np.where(s >= 0, np.int8(1), np.int8(-1))

    def bundle_weighted(self, hvs, weights):
        w = np.asarray(weights, dtype=np.float32).reshape(-1, 1)
        s = np.sum(hvs.astype(np.float32) * w, axis=0, dtype=np.float32)
        return np.where(s >= 0, np.int8(1), np.int8(-1))

    def bind(self, a, b):
        return (a.astype(np.int16) * b.astype(np.int16)).astype(np.int8)

    def unbind(self, a, bound):
        return self.bind(a, bound)

    def dot_row(self, bank, q):
        return bank.astype(np.int32) @ q.astype(np.int32)

    def similarity(self, a, b):
        return float(np.dot(a.astype(np.int32), b.astype(np.int32))) / self.D

    def perturb(self, hv, kind, a, rng):
        out = bipolar_perturb(hv, kind, a, rng)
        return out if kind == "clean" or kind == "mixture" else out.astype(np.int8)


class FHRR(Model):
    name = "fhrr"
    itemsize = 8  # complex64

    def __init__(self, D: int, seed: int = 0):
        super().__init__(D, seed)

    def atomic(self, n, rng):
        ph = rng.uniform(0.0, 2.0 * np.pi, size=(n, self.D)).astype(np.float32)
        return (np.cos(ph) + 1j * np.sin(ph)).astype(np.complex64)

    def neutral(self):
        return np.ones(self.D, dtype=np.complex64)

    def _phase_normalize(self, s: np.ndarray) -> np.ndarray:
        m = np.abs(s)
        out = np.where(m > 0, s / np.maximum(m, 1e-9), 1.0 + 0j)
        return out.astype(np.complex64)

    def bundle(self, hvs):
        return self._phase_normalize(np.sum(hvs, axis=0, dtype=np.complex64))

    def bundle_weighted(self, hvs, weights):
        w = np.asarray(weights, dtype=np.float32).reshape(-1, 1)
        s = np.sum(hvs.astype(np.complex64) * w, axis=0, dtype=np.complex64)
        return self._phase_normalize(s)

    def bind(self, a, b):
        return (a.astype(np.complex64) * b.astype(np.complex64))

    def unbind(self, a, bound):
        # conjugate multiply = angle subtraction: near-exact, no deconvolution
        return (bound.astype(np.complex64) * np.conjugate(a.astype(np.complex64)))

    def dot_row(self, bank, q):
        return np.real(bank.astype(np.complex64) @ np.conjugate(q.astype(np.complex64)))

    def similarity(self, a, b):
        return float(np.real(np.vdot(a, b))) / self.D

    def perturb(self, hv, kind, a, rng):
        hv = np.asarray(hv, dtype=np.complex64)
        D = self.D
        if kind == "clean":
            return hv
        if kind == "bitflip":
            # bit-flip analogue for phases: rotate exactly round(a*D) components
            k = max(1, int(round(a * D)))
            idx = rng.choice(D, size=k, replace=False)
            ang = rng.uniform(0.0, 2.0 * np.pi, size=k).astype(np.float32)
            out = hv.copy()
            out[idx] = out[idx] * (np.cos(ang) + 1j * np.sin(ang)).astype(np.complex64)
            return out
        if kind == "mixture":
            ph = rng.uniform(0.0, 2.0 * np.pi, size=D).astype(np.float32)
            u = (np.cos(ph) + 1j * np.sin(ph)).astype(np.complex64)
            return self._phase_normalize((1.0 - a) * hv + a * u)
        raise ValueError(f"unknown noise kind: {kind!r}")


class HRR(Model):
    name = "hrr"
    itemsize = 4  # float32

    def __init__(self, D: int, seed: int = 0):
        super().__init__(D, seed)

    def atomic(self, n, rng):
        v = rng.standard_normal((n, self.D)).astype(np.float32)
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
        return v

    def neutral(self):
        v = np.zeros(self.D, dtype=np.float32)
        v[0] = 1.0
        return v

    def bundle(self, hvs):
        s = np.sum(hvs, axis=0, dtype=np.float32)
        return (s / max(float(np.linalg.norm(s)), 1e-9)).astype(np.float32)

    def bundle_weighted(self, hvs, weights):
        w = np.asarray(weights, dtype=np.float32).reshape(-1, 1)
        s = np.sum(hvs.astype(np.float32) * w, axis=0, dtype=np.float32)
        return (s / max(float(np.linalg.norm(s)), 1e-9)).astype(np.float32)

    def bind(self, a, b):
        # circular convolution via FFT (projects the outer product back to D)
        return np.fft.irfft(np.fft.fft(a) * np.fft.fft(b), self.D).astype(np.float32)

    def unbind(self, a, bound):
        # circular correlation — noisy (heavy-tailed deconvolution: known weakness)
        return np.fft.irfft(
            np.fft.fft(bound) * np.conjugate(np.fft.fft(a)), self.D).astype(np.float32)

    def dot_row(self, bank, q):
        qb = q.astype(np.float32)
        nq = max(float(np.linalg.norm(qb)), 1e-9)
        qb = qb / nq
        norms = np.linalg.norm(bank, axis=1)
        norms[norms == 0] = 1.0
        return (bank @ qb) / norms

    def similarity(self, a, b):
        denom = max(float(np.linalg.norm(a)) * float(np.linalg.norm(b)), 1e-9)
        return float(np.dot(a, b)) / denom

    def perturb(self, hv, kind, a, rng):
        hv = np.asarray(hv, dtype=np.float32)
        D = self.D
        if kind == "clean":
            return hv
        if kind == "bitflip":
            k = max(1, int(round(a * D)))
            idx = rng.choice(D, size=k, replace=False)
            out = hv.copy()
            out[idx] = -out[idx]
            return out
        if kind == "mixture":
            u = rng.standard_normal(D).astype(np.float32)
            u = u / max(float(np.linalg.norm(u)), 1e-9) * max(
                float(np.linalg.norm(hv)), 1e-9)
            return (1.0 - a) * hv + a * u
        raise ValueError(f"unknown noise kind: {kind!r}")


MODEL_REGISTRY = {
    "bsc": BSC,
    "map": MAP,
    "fhrr": FHRR,
    "hrr": HRR,
}
