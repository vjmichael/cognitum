"""Item memory (Bank) with clean-up, BM25 lexical index, binary->float rescore.

All CPU-only. Bank.search is a single dot-product (matmul) — the generic
nearest-neighbor index (credited to the index, never to "HDC", per the locked
credit rule).
"""
from __future__ import annotations

import numpy as np


class Bank:
    """A set of stored hypervectors with ids (the 'item memory').

    Daily-use surface:
        bank  = Bank(model, matrix, ids)
        topk, s = bank.search(query_hv, k=10)
        rank    = bank.rank_of(query_hv, gold_ids)
    """

    def __init__(self, model, matrix: np.ndarray, ids: list):
        self.model = model
        self.M = np.ascontiguousarray(matrix)
        self.ids = list(ids)
        self.id2pos = {v: i for i, v in enumerate(self.ids)}

    @property
    def N(self) -> int:
        return len(self.ids)

    def bytes(self) -> int:
        return int(self.M.nbytes)

    def search(self, q: np.ndarray, k: int = 10):
        """Return (top-k indices into self.ids, full score vector)."""
        s = self.model.dot_row(self.M, q)
        k = min(int(k), self.N)
        if k < self.N:
            part = np.argpartition(-s, k - 1)[:k]
            order = np.argsort(-s[part], kind="stable")
            top = part[order]
        else:
            top = np.argsort(-s, kind="stable")
        return top, s

    def rank_of(self, q: np.ndarray, gold_ids: list):
        """1-based rank of the best gold item; None if no gold is stored."""
        gi = [self.id2pos[g] for g in gold_ids if g in self.id2pos]
        if not gi:
            return None
        s = self.model.dot_row(self.M, q)
        best = max(float(s[i]) for i in gi)
        return int(np.sum(s > best)) + 1

    def cos_to_gold(self, q: np.ndarray, gold_ids: list):
        """Similarity (dot/D for ±1 models; cosine for HRR) to the best gold."""
        gi = [self.id2pos[g] for g in gold_ids if g in self.id2pos]
        if not gi:
            return None
        s = self.model.dot_row(self.M, q)
        denom = self.model.D if self.model.itemsize in (1, 8) else None
        vals = [float(s[i]) / denom if denom else float(s[i]) for i in gi]
        return max(vals)

    def cleanup(self, hv: np.ndarray) -> int:
        """Standard clean-up memory (Plate 1991 / Kanerva 1998a): snap a noisy
        HV to the most-similar stored item (winner-take-all). Returns the row
        index into self.ids."""
        s = self.model.dot_row(self.M, hv)
        return int(np.argmax(s))


class BM25Index:
    """Standard BM25 (Robertson; k1=1.5, b=0.75) over tokenized docs.

    Inverted-index based: per query, work is proportional to the sum of
    posting-list lengths of the query terms — cheap at BEIR scale on CPU.
    """

    def __init__(self, docs_tokens: list, ids: list, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.ids = list(ids)
        self.N = len(docs_tokens)
        self.doclens = np.array([len(t) for t in docs_tokens], dtype=np.float32)
        self.avgdl = max(1e-9, float(self.doclens.sum()) / max(self.N, 1))

        df: dict = {}
        self.tfs = []
        for toks in docs_tokens:
            tf: dict = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self.tfs.append(tf)
            for w in tf:
                df[w] = df.get(w, 0) + 1

        self.idf = {w: float(np.log((self.N - f + 0.5) / (f + 0.5) + 1.0))
                    for w, f in df.items()}
        self.postings = {w: [] for w in df}
        for i, tf in enumerate(self.tfs):
            for w, f in tf.items():
                self.postings[w].append((i, f))

    def scores(self, query_tokens: list) -> np.ndarray:
        s = np.zeros(self.N, dtype=np.float32)
        k1, b, avgdl = self.k1, self.b, self.avgdl
        for t in dict.fromkeys(query_tokens):
            post = self.postings.get(t)
            if not post:
                continue
            idf = self.idf[t]
            for i, f in post:
                dl = self.doclens[i]
                s[i] += idf * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * dl / avgdl))
        return s

    def search(self, query_tokens: list, k: int = 10):
        s = self.scores(query_tokens)
        k = min(k, self.N)
        if k < self.N:
            part = np.argpartition(-s, k - 1)[:k]
            top = part[np.argsort(-s[part], kind="stable")]
        else:
            top = np.argsort(-s, kind="stable")
        return top, s


def rescore(binary_bank: Bank, float_bank: np.ndarray, binary_q: np.ndarray,
            float_q: np.ndarray, k: int = 100):
    """Standard fix for binary recall loss: shortlist by binary (Hamming/dot)
    similarity, then re-rank the candidates with the float representation.

    Returns the final ranked indices (into binary_bank.ids), best first.
    """
    short, _ = binary_bank.search(binary_q, k)
    s = float_bank[short].astype(np.float32) @ float_q.astype(np.float32)
    order = np.argsort(-s, kind="stable")
    return short[order]
