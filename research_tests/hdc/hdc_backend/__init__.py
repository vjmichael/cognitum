"""HDC Backend — interchangeable implementation layer for C1-C6 tests.

Usage:
    from hdc_backend import make_backend
    backend = make_backend("zogzoo")    # or "torchhd"
    values = backend.generate(100, 1024)
    bound = backend.bind(role, value)
    ...
"""
from __future__ import annotations
import numpy as np
from abc import ABC, abstractmethod


class HDCBackend(ABC):
    """Abstract HDC backend. All methods operate on 1-D or 2-D numpy arrays.

    Conventions:
      - Hypervectors are 1-D arrays of length D
      - Banks/codebooks are 2-D arrays of shape (n, D)
      - All methods are pure functions of their inputs (deterministic given rng)
    """

    name: str = "base"

    @abstractmethod
    def generate(self, n: int, D: int, seed: int = 0) -> np.ndarray:
        """Generate n random hypervectors of dimension D. Returns (n, D)."""
        ...

    @abstractmethod
    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Bind two hypervectors. Returns (D,)."""
        ...

    @abstractmethod
    def unbind(self, a: np.ndarray, bound: np.ndarray) -> np.ndarray:
        """Unbind a from bound. Returns (D,)."""
        ...

    @abstractmethod
    def bundle(self, vectors: np.ndarray) -> np.ndarray:
        """Bundle (superpose) a set of vectors. Input (n, D), returns (D,)."""
        ...

    @abstractmethod
    def score(self, bank: np.ndarray, query: np.ndarray) -> np.ndarray:
        """Score query against each row of bank. Input bank (n, D), query (D,).
        Returns (n,) similarity scores."""
        ...

    @abstractmethod
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Pairwise similarity between two hypervectors. Returns scalar in [0,1] or [-1,1]."""
        ...

    @abstractmethod
    def perturb(self, hv: np.ndarray, kind: str, alpha: float,
                rng: np.random.Generator) -> np.ndarray:
        """Apply noise to a hypervector. kind: 'bitflip'|'gaussian'|'jitter'|'clean'.
        alpha: noise strength (0.0-1.0). Returns same shape as hv."""
        ...

    @property
    @abstractmethod
    def dtype(self) -> np.dtype:
        """Element dtype of generated hypervectors."""
        ...


def make_backend(backend_name: str, D: int, vsa: str = "FHRR", seed: int = 0) -> HDCBackend:
    """Factory: create a named backend for a given VSA and dimensionality.

    Args:
        backend_name: "zogzoo" or "torchhd"
        D: hypervector dimensionality
        vsa: "BSC" | "MAP" | "HRR" | "FHRR"
        seed: master seed for reproducibility
    """
    name = backend_name.lower().replace("-", "").replace("_", "")
    if name == "zogzoo":
        from .zogzoo import ZogZooBackend
        return ZogZooBackend(D=D, vsa=vsa, seed=seed)
    elif name == "torchhd" or name == "torch":
        from .torchhd import TorchHDBackend
        return TorchHDBackend(D=D, vsa=vsa, seed=seed)
    else:
        raise ValueError(f"Unknown backend: {backend_name!r}. Use 'zogzoo' or 'torchhd'.")
