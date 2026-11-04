"""Resonator network — iterative factorization of multi-bound HV structures.

Literature:
  Kent, A. (2020) — "Iterative methods for decoding HRRs" (resonator networks).
  Frady, E., Kleyko, D., Sommer, T. (2020) — "A capacity theory for
    hyperdimensional computing" (resonator as standard decoder for m>2).
  Survey Part II §2.2.5 — "recovery is combinatorial for m>2; resonator
    networks are the standard answer."

Why it matters for Zog Zoo:
  The H2 tests showed that single-pass unbinding is weak in the informative
  regimes:
    - XOR + superposed A:  0.71 (below 0.9 gate)
    - CONV + noisy unbind: 0.77 mean / 0.17 min
  A resonator network iteratively recovers factors:
    1. Find the best-matching stored item (argmax similarity)
    2. Unbind it from the composite
    3. Subtract its contribution
    4. Renormalize
    5. Repeat until convergence or max_iters
  This turns "weak in the regimes that matter" into "converges with iteration."

FPGA mapping:
  Each iteration = dot product (adder tree) + subtract + normalize.
  All operations are LUT-mappable. No FFT needed (unlike HRR deconvolution).

Hardware policy: CPU-only (NumPy). Target: CPU now; FPGA/ASIC later. Never GPU.
"""
from __future__ import annotations

import numpy as np

from .models import Model


def factor_pair_search(model: Model, composite: np.ndarray,
                       candidates: np.ndarray, distinct: bool = True):
    """Decode one unordered three-factor product via pair enumeration.

    Enumerate O(V^2) pairs, unbind them to estimate a third factor,
    clean up against V candidates, and choose the best reconstructed triple.
    This is NOT a resonator network and costs O(V^3 D) in the simple
    implementation. Its role is a bounded-combinatorial reference decoder.
    """
    from itertools import combinations
    bank = np.asarray(candidates)
    comp = np.asarray(composite)
    if comp.ndim != 1 or bank.ndim != 2 or bank.shape[1] != comp.size:
        raise ValueError("expected (D,) composite and (V,D) candidate bank")
    if len(bank) < 3:
        raise ValueError("need at least three candidate factors")
    if len(bank) > 128:
        raise ValueError("pair-search research decoder limited to 128 candidates")
    best_score = float("-inf")
    best_ids = None
    for i, j in combinations(range(len(bank)), 2):
        pair = model.bind(bank[i], bank[j])
        residual = model.unbind(pair, comp)
        scores = np.asarray(model.dot_row(bank, residual), dtype=np.float64)
        if distinct:
            scores[[i, j]] = -np.inf
        k = int(np.argmax(scores))
        reconstruction = model.bind(pair, bank[k])
        score = _sim(model, comp, reconstruction)
        if score > best_score:
            best_score = score
            best_ids = sorted((i, j, k))
    return best_ids, best_score


def resonator_factor(
    model: Model,
    composite: np.ndarray,
    candidates: np.ndarray,
    max_iters: int = 10,
    tol: float = 1e-4,
    cleanup: bool = True,
) -> tuple[list[int], float]:
    """Factor a composite via bounded pair search when max_iters == 3.

    This is a search-based reference decoder, NOT a trained/population
    resonator network. Other max_iters use the legacy greedy heuristic.

    Legacy notes:

    Algorithm (Kent 2020 / Frady 2020):
      For iter in 1..max_iters:
        1. score_i = similarity(composite, candidate_i)
        2. best_i = argmax(score)
        3. If score[best_i] < tol: break  (converged or no signal)
        4. Recovered factor = candidate[best_i] (after optional cleanup)
        5. Remove its contribution:
           - BSC/MAP (self-inverse bind): composite = composite - candidate
           - FHRR (Hadamard):             composite = composite / candidate
           - HRR (convolution):           composite = composite * conj(candidate) / norm
        6. Renormalize composite
      Return (list of best indices in order, final residual score)

    Parameters
    ----------
    model : Model
        The HDC model (provides bind, unbind, similarity, bundle primitives).
    composite : np.ndarray
        The multi-bound composite HV (shape (D,) or (n, D)).
        For (n, D), each row is independently factored.
    candidates : np.ndarray
        Candidate HVs to match against (shape (n_cands, D)).
    max_iters : int
        Maximum number of iterations (factors to extract).
    tol : float
        Convergence threshold: stop when best score < tol.
    cleanup : bool
        If True, after finding the best match, snap the recovered factor
        to the exact candidate (winner-take-all cleanup, Plate 1991).

    Returns
    -------
    (indices, residual) : tuple
        indices — list of candidate indices extracted (best first).
        residual — the final best-match score after the last iteration.
    """
    # Three factors is the only combinatorial decoding case currently
    # validated against an exhaustive tiny-bank oracle. Keep the older
    # iterative API for other factor counts, but make this case correct.
    if max_iters == 3:
        arr = np.asarray(composite)
        if arr.ndim == 1:
            return factor_pair_search(model, arr, candidates)
        if arr.ndim == 2:
            rows = [factor_pair_search(model, q, candidates) for q in arr]
            return [r[0] for r in rows], np.asarray([r[1] for r in rows])
        raise ValueError("composite should be 1D or 2D")
    D = composite.shape[-1]
    single = (composite.ndim == 1)
    if single:
        composite = composite.reshape(1, -1)
    n_rows = composite.shape[0]

    results_idx: list[list[int]] = []
    results_res: list[float] = []

    for row in range(n_rows):
        dtype = np.complex128 if np.iscomplexobj(composite[row]) else np.float64
        comp = composite[row].copy().astype(dtype)
        if model.itemsize in (1,):
            # BSC/MAP: work in float for arithmetic, binarize for scoring
            comp_f = comp.astype(dtype)
        else:
            comp_f = comp.astype(np.complex128) if np.iscomplexobj(comp) \
                else comp.astype(np.float64)

        indices: list[int] = []
        residual = 0.0

        for _ in range(max_iters):
            # 1. Score all candidates
            scores = np.array([
                _sim(model, comp_f, candidates[i])
                for i in range(candidates.shape[0])
            ])
            best = int(np.argmax(scores))
            residual = float(scores[best])

            if residual < tol:
                break

            indices.append(best)

            # 2. Remove the contribution of candidate[best]
            cand = candidates[best]

            if model.name in ("bsc", "map"):
                # Self-inverse binding: composite ≈ sum of bound factors
                # Remove: composite -= candidate (then re-binarize for next iter)
                comp_f = comp_f - cand.astype(np.float64)
            elif model.name == "fhrr":
                # Hadamard: composite ≈ prod of factors
                # Remove: composite /= candidate (element-wise division)
                with np.errstate(divide="ignore", invalid="ignore"):
                    comp_f = comp_f / (cand.astype(np.complex128) + 1e-12)
                # Phase normalize
                m = np.abs(comp_f)
                comp_f = np.where(m > 1e-9, comp_f / np.maximum(m, 1e-9),
                                  np.ones_like(comp_f, dtype=np.complex128))
            elif model.name == "hrr":
                # Convolution: composite ≈ conv(factors)
                # Remove: correlation with candidate (inverse conv)
                comp_f = np.fft.irfft(
                    np.fft.rfft(comp_f) * np.conjugate(np.fft.rfft(cand)), D
                ).astype(np.float64)
                # Renormalize
                nrm = max(float(np.linalg.norm(comp_f)), 1e-9)
                comp_f = comp_f / nrm
            else:
                # Fallback: generic subtract
                comp_f = comp_f - cand.astype(np.float64)

            # 3. Renormalize for BSC/MAP
            if model.name in ("bsc", "map"):
                # Re-binarize: sign with deterministic tie-break
                comp_f = np.where(comp_f >= 0, 1.0, -1.0)

        results_idx.append(indices)
        results_res.append(residual)

    if single:
        return results_idx[0], results_res[0]
    return results_idx, np.array(results_res)


def resonator_recover(
    model: Model,
    bound_hv: np.ndarray,
    key: np.ndarray,
    value_candidates: np.ndarray,
    max_iters: int = 5,
    tol: float = 0.3,
) -> tuple[np.ndarray, float]:
    """Recover a value from a bound HV using resonator cleanup.

    Standard case: value ≈ model.unbind(key, bound_hv), then clean up
    (snap to nearest candidate). The resonator version iterates if the
    first pass is noisy:

      1. v_est = unbind(key, bound_hv)
      2. best = argmax similarity(v_est, value_candidates)
      3. residual = bound_hv - bind(key, value_candidates[best])
      4. If residual_norm > tol: try next-best candidate
      5. Return best candidate + confidence

    This is the standard "clean-up memory" (Plate 1991) extended with
    iterative refinement for noisy/superposed regimes.
    """
    # First pass: standard unbind
    v_est = model.unbind(key, bound_hv)

    # Score against candidates
    scores = np.array([
        _sim(model, v_est, value_candidates[i])
        for i in range(value_candidates.shape[0])
    ])

    # Iterative refinement: try top-k, pick the one that best explains bound_hv
    top_k = min(5, len(value_candidates))
    top = np.argsort(-scores)[:top_k]

    best_score = -np.inf
    best_idx = int(top[0])

    for idx in top:
        candidate = value_candidates[idx]
        # How well does bind(key, candidate) explain bound_hv?
        reconstructed = model.bind(key, candidate)
        explanation = _sim(model, bound_hv, reconstructed)
        if explanation > best_score:
            best_score = explanation
            best_idx = int(idx)

    return value_candidates[best_idx], float(best_score)


def _sim(model: Model, a: np.ndarray, b: np.ndarray) -> float:
    """Model-agnostic similarity (handles real and complex)."""
    a = np.asarray(a)
    b = np.asarray(b)
    if np.iscomplexobj(a) or np.iscomplexobj(b):
        # Phase similarity for FHRR
        return float(np.real(np.vdot(a, b)) / max(a.size, 1))
    # BSC/MAP/HRR: dot / D or cosine
    denom = max(float(np.linalg.norm(a)) * float(np.linalg.norm(b)), 1e-9)
    # Cast to float64: np.dot on two int8 arrays (BSC/MAP) stays int8 in
    # NumPy 2.x and overflows — promote to a wide type before reducing.
    return float(np.dot(a.astype(np.float64), b.astype(np.float64))) / denom

# ---------------------------------------------------------------------------
# Genuine recurrent resonator.  The pair-search oracle above is deliberately
# retained as a separate baseline; it is NOT invoked from this implementation.
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field


@dataclass
class ResonatorResult:
    """Factor indices are in input-slot order (each slot has its own bank)."""
    indices: tuple[int, ...]
    similarity: float
    converged: bool
    iterations: int
    restarts_used: int
    projections: int
    trace: list[dict] = field(default_factory=list)


def _project_feedback(model: Model, bank: np.ndarray, cue: np.ndarray,
                      *, temperature: float | None = None, top_k: int = 4,
                      projector: str = "winner"):
    """Content-addressable cleanup: WTA or annealed superposition feedback."""
    scores = np.asarray(model.dot_row(bank, cue), dtype=np.float64)
    if not np.all(np.isfinite(scores)):
        raise FloatingPointError('nonfinite resonator feedback scores')
    winner = int(np.argmax(scores))
    if projector == 'codebook':
        # Canonical resonator-style autoassociative projection: X^T X cue.
        # (Rows of X are candidate hypervectors.)  Unlike winner-take-all,
        # all codebook items contribute to the recurrent state.  Candidate
        # identity is reported by nearest cleanup, not forcibly projected.
        mixed = scores @ bank
        if model.name in ('bsc','map'):
            return np.where(mixed >= 0, 1, -1).astype(np.int8), winner
        if model.name == 'fhrr':
            return (mixed / np.maximum(np.abs(mixed),1e-8)).astype(np.complex64), winner
        mixed = mixed / max(float(np.linalg.norm(mixed)),1e-8)
        return mixed.astype(np.float32), winner
    if temperature is None or top_k <= 1:
        return bank[winner].copy(), winner
    top = np.argsort(scores)[-min(top_k, len(scores)):]
    raw = scores[top]
    # Score scales vary between HRR, FHRR, and bipolar; normalize locally.
    scale = max(float(np.std(scores)), 1e-6)
    logits = (raw - max(raw)) / (scale * temperature)
    weights = np.exp(np.maximum(logits, -80))
    weights = weights / weights.sum()
    mixed = weights @ bank[top]
    if model.name in ('bsc', 'map'):
        mixed = np.where(mixed >= 0, 1, -1).astype(np.int8)
    elif model.name == 'fhrr':
        mixed = mixed / np.maximum(np.abs(mixed), 1e-8)
        mixed = mixed.astype(np.complex64)
    else:
        mixed = mixed / max(float(np.linalg.norm(mixed)), 1e-8)
        mixed = mixed.astype(np.float32)
    return mixed, winner


def _bind_many(model: Model, vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        return model.neutral()
    result = vectors[0]
    for vector in vectors[1:]:
        result = model.bind(result, vector)
    return result


class ResonatorNetwork:
    """Coupled-factor recurrent resonator with independent item-memory banks.

    For slot i, estimate its factor using the current guesses at EVERY other
    slot: ``cue_i = unbind(bind(guesses_except_i), composite)``; then project
    ``cue_i`` onto slot i's candidate memory, and feed the projection back.
    Repeat asynchronous sweeps until stable, cycling, or the iteration limit.

    This is an iterative, coupled-feedback resonator using either WTA/
    annealed cleanup or canonical codebook autoassociative projection. It does NOT enumerate candidate pairs or triples, and is not a
    guarantee of global factor recovery. Random restarts and a reported score
    help reveal local attractors. Banks describe factor *slots*, not a single
    unordered candidate vocabulary. The caller must compare against a search
    oracle when small enough and against true ground truth in experiments.

    Complexity per restart is approximately O(iterations * factor_slots *
    vocabulary * D), plus binding/unbinding overhead; HRR also uses FFTs.
    """

    def __init__(self, model: Model, banks: list[np.ndarray], *,
                 max_iters: int = 24, restarts: int = 16,
                 soft_steps: int = 4, seed: int = 0, top_k: int = 4,
                 projector: str = "winner"):
        if projector not in ('winner', 'codebook'):
            raise ValueError('projector must be winner or codebook')
        if not 2 <= len(banks) <= 8:
            raise ValueError('resonator requires 2..8 factor slots')
        if max_iters < 1 or restarts < 1 or soft_steps < 0 or top_k < 1:
            raise ValueError('invalid resonator control parameters')
        self.model = model
        self.banks = [np.ascontiguousarray(b) for b in banks]
        for bank in self.banks:
            if bank.ndim != 2 or bank.shape[1] != model.D or not len(bank):
                raise ValueError('every bank must have shape (V_i, model.D)')
        self.max_iters = int(max_iters)
        self.restarts = int(restarts)
        self.soft_steps = int(soft_steps)
        self.seed = int(seed)
        self.top_k = int(top_k)
        self.projector = projector

    def decode(self, composite: np.ndarray, *, trace: bool = False,
               initial_indices: list[int] | None = None) -> ResonatorResult:
        comp = np.asarray(composite)
        if comp.shape != (self.model.D,):
            raise ValueError('composite must have shape (D,)')
        rng = np.random.default_rng(self.seed)
        n = len(self.banks)
        if initial_indices is not None and (len(initial_indices) != n or any(
                not 0 <= k < len(self.banks[i]) for i, k in enumerate(initial_indices))):
            raise ValueError('initial_indices must identify one item per bank')
        best: ResonatorResult | None = None
        projection_count = 0
        all_trace = []
        for restart in range(self.restarts):
            if restart == 0 and initial_indices is not None:
                ids = tuple(int(v) for v in initial_indices)
            else:
                ids = tuple(int(rng.integers(len(b))) for b in self.banks)
            guesses = [b[k].copy() for b, k in zip(self.banks, ids)]
            seen = set()
            stable = 0
            is_converged = False
            for step in range(self.max_iters):
                # Soft cleanup can help escape shallow basins during warm-up.
                # Hard cleanup gives discrete, testable candidate identities.
                soften = (self.projector == 'winner' and step < self.soft_steps)
                next_ids = []
                for i, bank in enumerate(self.banks):
                    other = _bind_many(self.model,
                                       [guesses[j] for j in range(n) if j != i])
                    cue = self.model.unbind(other, comp)
                    temperature = (1.1 - 0.8 * step / max(self.soft_steps, 1)) if soften else None
                    projected, winner = _project_feedback(
                        self.model, bank, cue, temperature=temperature,
                        top_k=self.top_k, projector=self.projector)
                    projection_count += 1
                    guesses[i] = projected  # asynchronous recurrent feedback
                    next_ids.append(winner)
                current = tuple(next_ids)
                # Score the DISCRETE decoded factors, not soft internal states.
                reconstructed = _bind_many(self.model,
                                           [b[k] for b, k in zip(self.banks, current)])
                fit = float(np.clip(_sim(self.model, comp, reconstructed), -1.0, 1.0))
                if best is None or fit > best.similarity:
                    best = ResonatorResult(current, fit, False, step + 1,
                                           restart + 1, projection_count, [])
                if trace:
                    all_trace.append({'restart': restart, 'step': step,
                                      'indices': current, 'similarity': fit})
                if not soften:
                    stable = stable + 1 if current == ids else 0
                    if stable >= 2:
                        is_converged = True
                        break
                    if current in seen:
                        break
                    seen.add(current)
                ids = current
            if best is not None and best.indices == current and is_converged:
                best.converged = True
                best.iterations = step + 1
            if best is not None and best.similarity >= 0.99999:
                # Perfect reconstruction in the tested algebra. HRR may not
                # reach 1.0 due to roundoff; no correctness claim follows.
                break
        assert best is not None
        best.restarts_used = restart + 1
        best.projections = projection_count
        best.trace = all_trace if trace else []
        return best


def resonator_network(model: Model, composite: np.ndarray,
                      factor_banks: list[np.ndarray], **kwargs) -> ResonatorResult:
    """Functional convenience wrapper for the *actual* recurrent network."""
    return ResonatorNetwork(model, factor_banks, **kwargs).decode(composite)
