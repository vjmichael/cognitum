"""NeuralHD — adaptive dimension elimination.

Literature:
  Zou, Y., et al. (2021) — "NeuralHD" (adaptive dimensionality).
  Salik, A., et al. (2026) — "HDC architectures for AI applications"
    (Results in Engineering, §3.8: dimension elimination).
  Thomas, M., Dasgupta, I., Rosing, T. (2021) — "A theoretical
    perspective on HDC" (JAIR).

Key insight:
  Not all D dimensions carry equal information. After encoding a corpus,
  many dimensions contribute near-zero variance. Eliminating these:
    - Reduces storage: D_eff < D
    - Reduces compute: shorter dot products
    - Preserves accuracy: eliminated dims had no signal
    - FPGA: fewer LUTs, shorter adder trees, lower power

Algorithm:
  1. Encode the full corpus (N x D).
  2. Compute per-dimension information content (column variance).
  3. Zero out the bottom-k% dimensions.
  4. Search on the reduced bank.

Hardware policy: CPU-only (NumPy). Target: CPU now; FPGA/ASIC later. Never GPU.
"""
from __future__ import annotations

import numpy as np

from .models import Model


def eliminate_dimensions(
    bank: np.ndarray,
    threshold: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Eliminate low-variance dimensions from a bank of HVs.

    Parameters
    ----------
    bank : np.ndarray
        The encoded bank, shape (N, D).
    threshold : float
        Keep dimensions whose normalized variance exceeds this value (0-1).

    Returns
    -------
    (reduced_bank, keep_mask, stats)
    """
    N, D = bank.shape
    # Variance is real-valued even for complex FHRR features. Preserve the
    # original bank dtype and only slice the chosen coordinates.
    col_var = np.var(np.asarray(bank), axis=0)
    max_var = float(col_var.max()) if col_var.max() > 0 else 1.0
    scores = col_var / max_var
    keep_mask = scores > threshold

    # Safety: keep at least 50% of dimensions
    n_keep = int(keep_mask.sum())
    if n_keep < D // 2:
        keep_idx = np.argsort(-scores)[:D // 2]
        keep_mask = np.zeros(D, dtype=bool)
        keep_mask[keep_idx] = True
        n_keep = D // 2

    # Materialize true (N, D_eff) bank without changing the original dtype.
    reduced = np.ascontiguousarray(bank[:, keep_mask])

    stats = {
        "D_original": D,
        "D_effective": int(n_keep),
        "elimination_rate": round(1.0 - n_keep / D, 4),
        "method": "variance",
        "threshold": threshold,
        "original_bytes": int(bank.nbytes),
        "resident_bytes": int(reduced.nbytes),
    }
    return reduced, keep_mask, stats


def eliminate_by_ablation(
    model: Model,
    bank: np.ndarray,
    queries: np.ndarray,
    golds: list,
    n_queries_eval: int = 100,
    elimination_fraction: float = 0.3,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Ablation-based dimension elimination (task-specific).

    For each dimension d, zero it and measure the drop in top-1 accuracy.
    Keep dimensions whose removal causes significant degradation.
    """
    N, D = bank.shape
    bank_f = np.asarray(bank)
    qn = min(n_queries_eval, len(queries))
    queries = np.asarray(queries)[:qn]
    golds = golds[:qn]

    base_top1 = _top1_accuracy(model, bank_f, queries, golds)

    dim_scores = np.zeros(D)
    step = max(1, D // 200)
    for d in range(0, D, step):
        bank_ablated = bank_f.copy()
        bank_ablated[:, d] = 0
        acc = _top1_accuracy(model, bank_ablated, queries[:10], golds[:10])
        dim_scores[d] = base_top1 - acc
        for dd in range(d + 1, min(d + step, D)):
            dim_scores[dd] = dim_scores[d]

    n_keep = int(D * (1.0 - elimination_fraction))
    keep_idx = np.argsort(-dim_scores)[:n_keep]
    keep_mask = np.zeros(D, dtype=bool)
    keep_mask[keep_idx] = True

    reduced = np.ascontiguousarray(bank[:, keep_mask])
    final_top1 = _top1_accuracy(model, reduced, queries[:, keep_mask], golds)

    stats = {
        "D_original": D,
        "D_effective": int(n_keep),
        "elimination_rate": round(1.0 - n_keep / D, 4),
        "method": "ablation",
        "baseline_top1": round(base_top1, 4),
        "reduced_top1": round(final_top1, 4),
        "accuracy_delta": round(final_top1 - base_top1, 4),
    }
    return reduced, keep_mask, stats


def _top1_accuracy(model, bank, queries, golds) -> float:
    correct = 0
    for j in range(len(queries)):
        s = model.dot_row(bank, queries[j])
        top = int(np.argmax(s))
        if top in golds[j]:
            correct += 1
    return correct / max(len(queries), 1)


class NeuralHDPipeline:
    """NeuralHD: encode -> eliminate -> search.

    Usage:
        pipe = NeuralHDPipeline(model, threshold=0.5)
        pipe.encode_and_reduce(bank_matrix)
        top, scores = pipe.search(query_hv, k=10)
    """

    def __init__(self, model: Model, threshold: float = 0.5):
        self.model = model
        self.threshold = threshold
        self.bank: np.ndarray | None = None
        self.keep_mask: np.ndarray | None = None
        self.stats: dict | None = None

    def encode_and_reduce(self, bank: np.ndarray) -> dict:
        self.bank, self.keep_mask, self.stats = eliminate_dimensions(
            bank, threshold=self.threshold)
        return self.stats

    def search(self, query: np.ndarray, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
        if self.bank is None:
            raise ValueError("Call encode_and_reduce first.")
        query = np.asarray(query)
        if query.shape[-1] != self.keep_mask.size:
            raise ValueError("query dimension does not match training input")
        q_reduced = np.ascontiguousarray(query[self.keep_mask])
        s = self.model.dot_row(self.bank, q_reduced)
        k = min(k, len(s))
        if k < len(s):
            part = np.argpartition(-s, k - 1)[:k]
            order = np.argsort(-s[part], kind="stable")
            top = part[order]
        else:
            top = np.argsort(-s, kind="stable")
        return top, s[top]
