"""ZogZooBackend — wraps zogzoo_hdc models for the unified test harness."""
from __future__ import annotations
import numpy as np

from . import HDCBackend
from cognitum.research.hdc_recovered.models import MODEL_REGISTRY


class ZogZooBackend(HDCBackend):
    """HDC backend using the zogzoo_hdc package (pure NumPy, CPU-only)."""

    name = "zogzoo"

    def __init__(self, D: int, vsa: str = "FHRR", seed: int = 0):
        self.D = D
        self.vsa = vsa.upper()
        self.seed = seed
        self._model = MODEL_REGISTRY[vsa.lower()](D=D, seed=seed)

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(self._model.itemsize)

    def generate(self, n: int, D: int | None = None, seed: int | None = None) -> np.ndarray:
        D = D or self.D
        s = seed if seed is not None else self.seed
        rng = np.random.Generator(np.random.PCG64(s))
        if D != self.D:
            # Create a temporary model with the requested D
            model = MODEL_REGISTRY[self.vsa.lower()](D=D, seed=s)
            return model.atomic(n, rng)
        return self._model.atomic(n, rng)

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return self._model.bind(a, b)

    def unbind(self, a: np.ndarray, bound: np.ndarray) -> np.ndarray:
        return self._model.unbind(a, bound)

    def bundle(self, vectors: np.ndarray) -> np.ndarray:
        vectors = np.asarray(vectors)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        return self._model.bundle(vectors)

    def score(self, bank: np.ndarray, query: np.ndarray) -> np.ndarray:
        bank = np.asarray(bank)
        query = np.asarray(query)
        return self._model.dot_row(bank, query)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return self._model.similarity(np.asarray(a), np.asarray(b))

    def perturb(self, hv: np.ndarray, kind: str, alpha: float,
                rng: np.random.Generator | None = None) -> np.ndarray:
        if rng is None:
            rng = np.random.Generator(np.random.PCG64(42))
        # Map generic noise types to model-specific
        kind_map = {
            "bitflip": "bitflip",
            "signflip": "bitflip",
            "gaussian": "mixture",
            "jitter": "bitflip",  # FHRR: phase rotation ≈ bitflip analogue
        }
        mapped = kind_map.get(kind.lower(), kind.lower())
        return self._model.perturb(np.asarray(hv), mapped, alpha, rng)
