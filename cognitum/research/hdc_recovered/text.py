"""Text -> hypervector encoders (standard practices per the survey).

Schemes (checklist §B):
  bag_idf      — IDF-weighted bag of word HVs; integer-counter bundling at the
                 end (Random-Indexing / LSA family; single-pass corpus stats).
  hybrid       — bag part + permutation-ordered part (Kleyko et al. 2016a):
                 preserves BOTH partial-match and order similarity. This is the
                 standard fix for the F2 failure (XOR-position binding
                 destroying word-overlap signal).
  ngram        — bag part + n-gram HVs (multiplicative binding of permuted
                 word HVs, n = 2..3; Joshi et al. 2016 / PDP family).
  xor_position — ablation: word HV XORed with a random per-position HV. Kept
                 ONLY so the 2026-10-20 F2 result remains reproducible.

Position = cyclic shift (np.roll) of the word HV by word index — the standard
permutation-based position (Kussul & Baidyk 1993; Kanerva 2009), NOT i.i.d.
random position binding.

Word -> atomic HV assignment is a seeded "random index" shared across the
corpus (Random Indexing lineage). All randomness flows through caller-supplied
streams, so (master_seed, scheme, D) is fully reproducible.
"""
from __future__ import annotations

import re

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been
before being below between both but by can could did do does doing down during
each few for from further had has have having he her here hers herself him
himself his how i if in into is it its itself just me more most my myself no
nor not now of off on once only or other our ours ourselves out over own same
she should so some such than that the their theirs them themselves then there
these they this those through to too under until up very was we were what when
where which who whom why will with you your yours yourself yourselves
""".split())

SCHEMES = ("bag_idf", "hybrid", "ngram", "xor_position", "ri")


def tokenize(text: str, remove_stopwords: bool = True) -> list:
    toks = [t for t in TOKEN_RE.findall((text or "").lower()) if len(t) >= 2]
    if remove_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return toks


class CorpusStats:
    """Single-pass corpus statistics: document frequency + smooth IDF."""

    def __init__(self, docs_tokens: list, use_idf: bool = True):
        df: dict = {}
        for toks in docs_tokens:
            for w in set(toks):
                df[w] = df.get(w, 0) + 1
        n = max(len(docs_tokens), 1)
        self.n_docs = n
        self.df = df
        # DETERMINISM (locked 2026-10-21): sorted key order. Python string
        # hashing is randomized per process, so dict insertion order from
        # set(toks) was NOT reproducible across runs — which made the
        # word->HV assignment (and HDC scores) drift run-to-run.
        keys = sorted(df)
        if use_idf:
            self.idf = {w: float(np.log((1 + n) / (1 + df[w])) + 1.0) for w in keys}
        else:
            self.idf = {w: 1.0 for w in keys}

    def weight(self, w: str) -> float:
        return self.idf.get(w, 1.0)


class TextEncoder:
    """Encode texts into hypervectors with a given model + scheme.

    Daily-use surface:
        enc = TextEncoder(model, "hybrid", stats, streams)
        hv  = enc.encode("the cat sat on the mat")
        M   = enc.encode_matrix(token_lists)   # (n, D)
    """

    def __init__(self, model, scheme: str, stats: CorpusStats, streams: dict,
                 max_tokens: int = 512, vocab_cap: int | None = None,
                 docs_tokens: list | None = None):
        if scheme not in SCHEMES:
            raise ValueError(f"unknown scheme {scheme!r}; expected one of {SCHEMES}")
        self.model = model
        self.scheme = scheme
        self.stats = stats
        self.streams = streams
        self.max_tokens = int(max_tokens)

        self.word_idx: dict = {}
        self.W = None  # (n_words, D) word-HV matrix

        if scheme == "ri":
            # Random Indexing (Sahlgren 2005; Kanerva et al. 2000) — the
            # standard HDC text encoder (checklist §B.1):
            #   doc index  = sparse ternary vector (±1 at ~D/8 positions)
            #   word vector = superposition of the doc indices of the docs
            #                 in which the word occurs (co-occurrence
            #                 structure — NOT per-word i.i.d. random vectors)
            #   text        = superposition of word vectors -> binarize
            if docs_tokens is None:
                raise ValueError("scheme 'ri' requires docs_tokens")
            m = self.model
            rng = streams["word"]
            n_docs = len(docs_tokens)
            dense = m.atomic(n_docs, rng)                      # (n_docs, D) ±1
            sparsity = max(8, int(round(m.D / 8)))
            keep = rng.random((n_docs, m.D)) < (sparsity / m.D)
            DI = np.where(keep, dense, 0).astype(np.float32)
            ctx: dict = {}
            for d, toks in enumerate(docs_tokens):
                seen = set()
                di = DI[d]
                for w in toks:          # list order -> deterministic sum order
                    if w in seen:
                        continue
                    seen.add(w)
                    if w in ctx:
                        ctx[w] = ctx[w] + di
                    else:
                        ctx[w] = di.copy()
            keys = sorted(ctx.keys())
            if vocab_cap:
                keys = keys[:int(vocab_cap)]
            self.word_idx = {w: i for i, w in enumerate(keys)}
            self.W = np.stack([ctx[w] for w in keys]).astype(np.float32)
            return

        # CONSISTENCY (locked 2026-10-21): pre-register the full vocabulary
        # in ONE deterministic draw so every encoder built from the same
        # (stats, streams) shares the EXACT same word->HV table. This is what
        # makes bank / query / positive-control encodings comparable — without
        # it the positive control collapses to chance (smoke: PC top1 = 0.0 on
        # every HDC pipeline while dense/emb/bm25 PC = 1.0).
        if stats is not None:
            words = list(stats.idf.keys())
            if vocab_cap:
                words = words[:int(vocab_cap)]
            if words:
                self._ensure_words(words)

        # scheme-specific seeded constants
        if scheme == "xor_position":
            self.P = model.atomic(max_tokens, streams["position"])
        elif scheme == "ngram":
            roles = model.atomic(2, streams["position"])
            self.L = roles[0]
            self.R = roles[1]

    # -- word HV table --------------------------------------------------------
    def _ensure_words(self, words) -> None:
        new = [w for w in words if w not in self.word_idx]
        if not new:
            return
        base = len(self.word_idx)
        for w in new:
            self.word_idx[w] = base + (len(self.word_idx) - base)
        n = len(self.word_idx)
        cur = self.W.shape[0] if self.W is not None else 0
        if n > cur:
            grow = max(n, cur * 2, 1024)
            W_new = self.model.atomic(grow, self.streams["word"])
            if cur:
                W_new[:cur] = self.W
            self.W = W_new

    def add_words(self, words) -> None:
        """Pre-register a word set (e.g. the corpus vocab) before encoding."""
        self._ensure_words(list(words))

    def _word_hvs(self, toks):
        toks = [t for t in toks if t in self.word_idx]
        if not toks:
            return None
        idx = np.array([self.word_idx[t] for t in toks], dtype=np.int64)
        return toks, self.W[idx]

    # -- single text ----------------------------------------------------------
    def encode(self, toks: list) -> np.ndarray:
        m = self.model
        toks = toks[: self.max_tokens]
        if self.scheme == "ri":
            # RI: superposition of (co-occurrence) word vectors -> binarize.
            # Fixed word table: no growth (OOV words are simply absent).
            got = self._word_hvs(toks)
            if got is None:
                return m.neutral()
            _, W = got
            s = W.sum(axis=0, dtype=np.float32)
            return m.bundle(s.reshape(1, -1))
        self._ensure_words(toks)
        got = self._word_hvs(toks)
        if got is None:
            return m.neutral()
        toks_f, W = got
        k = W.shape[0]
        parts = []

        if self.scheme in ("bag_idf", "hybrid", "ngram"):
            wts = np.array([self.stats.weight(t) for t in toks_f], dtype=np.float32)
            parts.append(m.bundle_weighted(W, wts))

        if self.scheme == "hybrid":
            # ordered part: superposition of cyclic-shifted word HVs.
            # Vectorized: order[i, col] = W[i, (col - i) % D]  (== roll(W[i], i))
            rows = np.arange(k)
            cols = (np.arange(self.model.D)[None, :] - rows[:, None]) % self.model.D
            order = W[rows[:, None], cols]
            parts.append(m.bundle(order))

        elif self.scheme == "ngram":
            # n-gram HVs: bind(permute(w_i), permute(w_{i+1}), ...) —
            # multiplicative binding of cyclically shifted symbol HVs
            # (Joshi 2016 / PDP). Vectorized gather (elementwise-bind models:
            # BSC/MAP/FHRR — the ngram pipeline is BSC in PIPELINE_DEFS).
            rows = np.arange(k)
            cols = np.arange(self.model.D)[None, :]
            grams = []
            for n in (2, 3):
                g = W[rows]
                for j in range(1, n):
                    rj = (rows + j) % k
                    cj = (cols - (rows + j)[:, None]) % self.model.D
                    g = g * W[rj[:, None], cj]
                if k - n + 1 > 0:
                    grams.append(g[: k - n + 1])
            if grams:
                parts.append(m.bundle(np.vstack(grams)))

        elif self.scheme == "xor_position":
            P = self.P[:k]
            parts.append(m.bundle((W.astype(np.int16) * P.astype(np.int16)).astype(np.int8)))

        if len(parts) == 1:
            return parts[0]
        return m.bundle(np.vstack(parts))

    # -- batch ----------------------------------------------------------------
    def encode_matrix(self, token_lists: list) -> np.ndarray:
        """Encode all documents (serial loop — the per-doc compute is small,
        memory-bound, and Python-overhead-bound. BLAS threading in the
        underlying NumPy ops provides the multi-core speedup where it helps
        (the matmul in bundle_weighted and dot_row)."""
        out = np.empty((len(token_lists), self.model.D),
                       dtype=self.model.neutral().dtype)
        for i, toks in enumerate(token_lists):
            out[i] = self.encode(toks)
        return out

    # Alias for backwards compatibility with test scripts
    encode_matrix_serial = encode_matrix
