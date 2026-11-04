"""Sparse Distributed Memory (SDM) — long-term memory tier.

Literature:
  Kanerva, P. (1988) — "Sparse Distributed Memory" (the original).
  Teeters, J., Kleyko, D., Kanerva, P., Olshausen, B. (2023) —
    "On separating long- and short-term memories in HDC"
    (Frontiers in Neuroscience, doi:10.3389/fnins.2022.867568).
  Code: https://github.com/jeffteeters/hdfsa

Architecture principle (Teeters 2023):
  - Superposition vector = WORKING memory (short-term, ~7 items,
    compositional, fast, small D=512-1024).
  - SDM = LONG-TERM memory (large capacity, address-based, fixed vector
    width, scales by adding locations NOT width).
  - They are complementary, not competing.
  - The "NN nearest-key side-channel" identified in H3 is the SDM in disguise.

Key advantage over superposition for large banks:
  - Storage: 15-35x less than superposition
  - Computation: 37-135x fewer ops per recall
  - Capacity: decoupled from D (add locations, not dimensions)
  - At error rate 10^-6: superposition needs D~9879; SDM needs D=512
    with ~2400 locations (vs 9879 dims with 1 location)

Biological connection:
  - Cerebellum = associative memory (SDM analog)
  - Cortex = compositional working memory (superposition analog)
  - Working memory holds ~7 items (Miller 1956), recalls from long-term

FPGA mapping:
  SDM lookup = Hamming distance comparison across all locations (parallel).
  Each location is a fixed-width comparator tree — single-clock-cycle
  (Schmuck et al. 2019: "single-clock-cycle inference with deep adder trees").
  Capacity scales by adding comparator banks, not by widening the tree.

Hardware policy: CPU-only (NumPy). Target: CPU now; FPGA/ASIC later. Never GPU.
"""
from __future__ import annotations

import numpy as np

from .models import Model


class SDM:
    """Sparse Distributed Memory — address-based long-term storage.

    Architecture (Teeters 2023, Kanerva 1988):
      - N locations (rows), each of width D (same as the working memory HV)
      - Lookup: Hamming distance (or dot product) between query and all locations
      - Write: assign a new location (or update existing)
      - Capacity scales with N (number of locations), NOT with D

    Daily-use surface:
        sdm = SDM(model, D, n_locations, seed)
        sdm.write(address_hv, content_hv)
        content, confidence = sdm.lookup(address_hv)
        topk, scores = sdm.search(address_hv, k=10)
    """

    def __init__(self, model: Model, D: int, n_locations: int = 10000,
                 seed: int = 0):
        self.model = model
        self.D = int(D)
        self.N = int(n_locations)
        self.seed = int(seed)
        # Locations matrix: (N, D) — initialized to zeros (empty)
        self.locations: np.ndarray = np.zeros(
            (self.N, D), dtype=model.neutral().dtype)
        # Content matrix: (N, D) — the stored values
        self.contents: np.ndarray = np.zeros(
            (self.N, D), dtype=model.neutral().dtype)
        # Occupancy mask: which locations have been written
        self.occupied: np.ndarray = np.zeros(self.N, dtype=bool)
        # Next write index (sequential allocation)
        self._next_write: int = 0

    @property
    def n_used(self) -> int:
        return int(self.occupied.sum())

    def bytes(self) -> int:
        """Total storage in bytes (locations + contents + mask)."""
        return (self.locations.nbytes + self.contents.nbytes
                + self.occupied.nbytes)

    def _similarity_scores(self, address: np.ndarray) -> np.ndarray:
        """Normalized similarity for the occupied address bank, not raw dot."""
        occ = self.occupied
        if not np.any(occ):
            return np.empty(0, dtype=np.float64)
        scores = np.asarray(self.model.dot_row(self.locations[occ], address), dtype=np.float64)
        if self.model.name in ("bsc", "map", "fhrr"):
            scores /= self.D
        return scores

    def write(self, address: np.ndarray, content: np.ndarray,
              mode: str = "new", match_threshold: float = 0.9) -> int:
        """Insert or update the nearest sufficiently similar address.

        ``mode='update'`` inserts into an empty memory or when no existing
        address has normalized similarity >= match_threshold. Collision and
        capacity errors are explicit; this is a nearest-key store, NOT a
        distributed Kanerva-style multi-location write.
        """
        if mode not in ("new", "update"):
            raise ValueError(f"unknown write mode {mode!r}")
        address = np.asarray(address)
        content = np.asarray(content)
        if address.shape != (self.D,) or content.shape != (self.D,):
            raise ValueError("address and content must both have shape (D,)")
        if not -1.0 <= match_threshold <= 1.0:
            raise ValueError("match_threshold must be between -1 and 1")
        if mode == "update" and self.n_used:
            scores = self._similarity_scores(address)
            best = int(np.argmax(scores))
            if float(scores[best]) >= match_threshold:
                idx = int(np.flatnonzero(self.occupied)[best])
                self.locations[idx] = address
                self.contents[idx] = content
                return idx
        if self._next_write >= self.N:
            reusable = np.flatnonzero(~self.occupied)
            if not len(reusable):
                raise MemoryError(f"SDM full: {self.N} locations exhausted")
            idx = int(reusable[0])
        else:
            idx = self._next_write
            self._next_write += 1
        self.locations[idx] = address
        self.contents[idx] = content
        self.occupied[idx] = True
        return idx

    def lookup_checked(self, address: np.ndarray, min_similarity: float = 0.9):
        """Return (content, score) or (None, score) for an unknown/noisy key."""
        if not self.occupied.any():
            return None, float("-inf")
        scores = self._similarity_scores(np.asarray(address))
        best = int(np.argmax(scores))
        score = float(scores[best])
        if score < min_similarity:
            return None, score
        idx = int(np.flatnonzero(self.occupied)[best])
        return self.contents[idx].copy(), score

    def delete(self, address: np.ndarray, match_threshold: float = 0.9) -> bool:
        """Delete an existing nearest key only if its normalized score passes."""
        if not self.occupied.any():
            return False
        scores = self._similarity_scores(np.asarray(address))
        best = int(np.argmax(scores))
        if float(scores[best]) < match_threshold:
            return False
        idx = int(np.flatnonzero(self.occupied)[best])
        self.occupied[idx] = False
        self.locations[idx].fill(0)
        self.contents[idx].fill(0)
        # Full-capacity single writes reuse holes; batch writes reject on overflow.
        return True

    def write_batch(self, addresses: np.ndarray, contents: np.ndarray) -> None:
        """Insert an entire batch or fail; never silently drop records."""
        addresses = np.asarray(addresses)
        contents = np.asarray(contents)
        if addresses.ndim != 2 or addresses.shape[1] != self.D or contents.shape != addresses.shape:
            raise ValueError("addresses and contents must both have shape (n, D)")
        n = len(addresses)
        if n > self.N - self._next_write:
            raise MemoryError(f"SDM has only {self.N - self._next_write} free append slots")
        self.locations[self._next_write:self._next_write + n] = addresses
        self.contents[self._next_write:self._next_write + n] = contents
        self.occupied[self._next_write:self._next_write + n] = True
        self._next_write += n

    def lookup(self, address: np.ndarray) -> tuple[np.ndarray, float]:
        """Single-address lookup: return best-matching content + confidence.

        This is the SDM analog of the "cleanup memory" (Plate 1991):
        snap the noisy query to the most-similar stored address, return
        its content. For a single key-value pair, this is exact.
        """
        if not self.occupied.any():
            raise ValueError("SDM is empty — no locations written.")
        occ = self.occupied
        scores = self._similarity_scores(address)
        best = int(np.argmax(scores))
        best_score = float(scores[best])
        idx = int(np.where(occ)[0][best])
        return self.contents[idx], best_score

    def search(self, address: np.ndarray, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
        """Return top-k locations by similarity (indices + scores).

        This is the "NN nearest-key index" — the workhorse for large banks
        that H3 showed holds to N=20k (fill 2.0). The SDM gives it a
        theoretical foundation (Teeters 2023).
        """
        if not self.occupied.any():
            raise ValueError("SDM is empty — no locations written.")
        occ_idx = np.where(self.occupied)[0]
        scores = self._similarity_scores(address)
        k = min(k, len(occ_idx))
        if k < len(occ_idx):
            part = np.argpartition(-scores, k - 1)[:k]
            order = np.argsort(-scores[part], kind="stable")
            top_local = part[order]
        else:
            top_local = np.argsort(-scores, kind="stable")
        top_global = occ_idx[top_local]
        top_scores = scores[top_local]
        return top_global, top_scores

    def rank_of(self, address: np.ndarray, gold_indices: list[int]) -> int | None:
        """1-based rank of the best gold location."""
        gi = [i for i in gold_indices if i < self.N and self.occupied[i]]
        if not gi:
            return None
        occ_idx = np.where(self.occupied)[0]
        scores = self._similarity_scores(address)
        # Map global indices to local
        pos_of = {int(g): i for i, g in enumerate(occ_idx)}
        best = max(float(scores[pos_of[g]]) for g in gi)
        return int(np.sum(scores > best)) + 1

    # ------------------------------------------------------------------ #
    # Two-tier interface (working memory + long-term memory)
    # ------------------------------------------------------------------ #
    def recall_and_compose(
        self,
        working: np.ndarray,
        n_factors: int = 2,
        compose: bool = True,
    ) -> tuple[np.ndarray, list[float]]:
        """Recall n_factors items from SDM using the working HV,
        optionally compose them back into the working space.

        This is the "working memory recalls from long-term memory"
        pattern (Teeters 2023 conclusion):
          1. Decompose working HV into top-n_factors most-similar locations
          2. Return their contents (optionally bundled)

        Parameters
        ----------
        working : np.ndarray
            The current working memory HV (shape (D,)).
        n_factors : int
            How many items to recall.
        compose : bool
            If True, bundle the recalled contents into one HV.
            If False, return them separately.

        Returns
        -------
        (result, confidences) : tuple
            result — the composed (or first) content HV.
            confidences — list of similarity scores for each recalled item.
        """
        top_idx, scores = self.search(working, k=n_factors)
        recalled = self.contents[top_idx]
        confidences = [float(s) for s in scores]

        if compose and len(recalled) > 1:
            result = self.model.bundle(recalled)
        else:
            result = recalled[0]
        return result, confidences


class TwoTierMemory:
    """Working memory (superposition) + Long-term memory (SDM).

    The correct HDC architecture for the companion AI (Teeters 2023):
      - Working memory: superposition, D=512-1024, ~7-20 items
        Holds: current context, active bindings, short-term state.
      - Long-term memory: SDM, D=512, N=10k-1M locations
        Stores: all learned associations, object files, persistent knowledge.
      - Communication: working memory recalls from long-term, composes
        results, writes back.

    Daily-use surface:
        mem = TwoTierMemory(model, D=512, n_locations=10000, seed=0)
        mem.store(key_hv, value_hv)
        value = mem.recall(key_hv)
        mem.compose_into_working([key1, key2, key3])
    """

    def __init__(self, model: Model, D: int, n_locations: int = 10000,
                 max_working: int = 20, seed: int = 0):
        self.model = model
        self.D = D
        self.sdm = SDM(model, D, n_locations, seed)
        self.max_working = max_working
        # Working memory: superposition of active items
        self._working: np.ndarray | None = None

    def store(self, key: np.ndarray, value: np.ndarray) -> None:
        """Store a key->value mapping in long-term memory (SDM)."""
        self.sdm.write(key, value)

    def recall(self, key: np.ndarray) -> tuple[np.ndarray, float]:
        """Recall a value from long-term memory by key."""
        return self.sdm.lookup(key)

    def recall_multi(self, keys: list[np.ndarray],
                     top_k: int = 3) -> tuple[np.ndarray, list[float]]:
        """Recall values for multiple keys, compose into working memory."""
        contents = []
        confidences = []
        for k in keys:
            val, conf = self.sdm.lookup(k)
            contents.append(val)
            confidences.append(conf)
        if contents:
            composed = self.model.bundle(np.stack(contents))
        else:
            composed = self.model.neutral()
        self._working = composed
        return composed, confidences

    def working_state(self) -> np.ndarray | None:
        """Return the current working memory HV (or None if empty)."""
        return self._working

    def working_reset(self) -> None:
        """Clear working memory."""
        self._working = None

    def bytes_total(self) -> int:
        """Total memory footprint (SDM + working)."""
        total = self.sdm.bytes()
        if self._working is not None:
            total += self._working.nbytes
        return total
