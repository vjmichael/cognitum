"""Core: run configuration, deterministic seeded RNG streams, memory accounting.

CPU-only. No GPU dependencies, by design.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict

import numpy as np

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Deterministic RNG streams
# --------------------------------------------------------------------------- #
def make_streams(master_seed: int,
                 names=("word", "position", "projection", "run", "noise")) -> dict:
    """Independent, deterministic PCG64 streams derived from one master seed.

    Each (master_seed, stream_name) pair reproduces the exact same sequence on
    any machine; different stream names are mutually independent. This is what
    makes multi-seed runs reproducible and power-loss resumable.
    """
    out = {}
    for name in names:
        key = f"zogzoo:{master_seed}:{name}".encode("utf-8")
        h = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
        out[name] = np.random.Generator(np.random.PCG64(h))
    return out


def stream_check(master_seed: int, name: str, n: int = 4) -> list:
    """Deterministic probe used by the self-test to assert stream behavior."""
    g = make_streams(master_seed, (name,))[name]
    return [int(x) for x in g.integers(0, 1_000_000, size=n)]


# --------------------------------------------------------------------------- #
# Memory accounting
# --------------------------------------------------------------------------- #
def bank_bytes(n_docs: int, D: int, itemsize: int) -> int:
    """Bytes for a (n_docs, D) bank of the given per-element size."""
    return int(n_docs) * int(D) * int(itemsize)


def fits_budget(n_docs: int, D: int, itemsize: int, max_gb: float,
                extra_bytes: int = 0) -> tuple[bool, str]:
    """Return (ok, human) for a bank + any auxiliary arrays vs a GB budget."""
    total = bank_bytes(n_docs, D, itemsize) + int(extra_bytes)
    gb = total / 1e9
    return (gb <= max_gb, f"{gb:.2f} GB")


# --------------------------------------------------------------------------- #
# Run configuration
# --------------------------------------------------------------------------- #
@dataclass
class RunConfig:
    """Everything a run needs. Serialized to JSON so a run is fully described
    by one versioned file (production: config in, results out)."""

    # --- data ---
    downloads_dir: str = r"C:\Users\UserMN4312\Downloads"
    beir_datasets: list = field(default_factory=lambda: [
        "fiqa", "cqadupstack-android", "nfcorpus", "scifact"])
    include_squad: bool = True
    max_queries: int = 0            # 0 = all (smoke: set to a small cap)

    # --- grid ---
    pipelines: list = field(default_factory=lambda: [
        "dense_cohere", "emb_cohere", "emb_rescore", "bm25",
        "bag_idf", "hybrid", "ngram", "xor_position",
        "fhrr_bag", "fhrr_hybrid", "map_bag", "hrr_bag",
    ])
    dims: list = field(default_factory=lambda: [1024, 512, 256, 128, 64, 32])
    noise_models: list = field(default_factory=lambda: [
        "clean", "bitflip", "mixture"])
    noise_strength: float = 0.2
    seeds: list = field(default_factory=lambda: [20261020, 20261021, 20261022])
    shortlist_k: int = 100            # binary shortlist size for emb_rescore

    # --- text ---
    max_vocab: int = 120000
    max_tokens: int = 512             # per-text token cap (position/roll bound)
    remove_stopwords: bool = True
    use_idf: bool = True

    # --- resources ---
    max_bank_gb: float = 4.0
    query_batch: int = 2048

    # --- D=10k sentence diagnostic (capacity, reviewer-requested) ---
    diag_enabled: bool = True
    diag_D: int = 10000
    diag_max_bank: int = 100000
    diag_min_sentence_words: int = 4
    diag_vocab: int = 30000
    diag_pipelines: list = field(default_factory=lambda: ["bag_idf", "hybrid"])
    diag_max_queries: int = 2000

    # --- equal-memory comparison (survey §4.1: bytes/item, not equal D) ---
    equalmem_enabled: bool = True
    equalmem_bytes_per_doc: int = 256   # 1-bit@2048 vs 2-bit@1024

    # --- beyond-standard options (2026-10-23 boundary push) ---
    # Resonator cleanup: max iterations for iterative factorization
    resonator_max_iters: int = 10
    resonator_tol: float = 1e-4

    # SDM (long-term memory tier): number of locations
    sdm_n_locations: int = 10000

    # Low-discrepancy HV generation: "sobol" or "halton"
    lowdisc_method: str = "sobol"

    # NeuralHD dimension elimination: threshold (0-1)
    neuralhd_threshold: float = 0.5

    # Stochastic computing: enable SC validation mode
    stochastic_enabled: bool = False

    # Quantum: enable quantum resource estimation in reports
    quantum_estimate: bool = False

    # --- outputs ---
    results_dir: str = ""

    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: str) -> "RunConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        base = os.path.dirname(os.path.abspath(path))
        # resolve results_dir relative to the config file
        if raw.get("results_dir") and not os.path.isabs(raw["results_dir"]):
            raw["results_dir"] = os.path.normpath(os.path.join(base, raw["results_dir"]))
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in raw.items() if k in known}
        return cls(**kwargs)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=1, ensure_ascii=False)

    def fingerprint(self) -> str:
        """Stable hash of the grid-defining fields (used to label result rows)."""
        defining = {
            "pipelines": sorted(self.pipelines),
            "dims": sorted(self.dims),
            "noise_models": sorted(self.noise_models),
            "noise_strength": self.noise_strength,
            "seeds": sorted(self.seeds),
            "max_vocab": self.max_vocab,
            "max_tokens": self.max_tokens,
            "remove_stopwords": self.remove_stopwords,
            "use_idf": self.use_idf,
            "schema": SCHEMA_VERSION,
        }
        blob = json.dumps(defining, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
