"""Data loading (BEIR parquet, SQuAD xlsx), sentence splitting, positive control.

Read-only on the Downloads datasets (locked rule). Paths/format proven by the
2026-10-20 harness (realdata_retrieval.py).
"""
from __future__ import annotations

import collections
import os
import re

import numpy as np


class Dataset:
    def __init__(self, name, bank_ids, bank_texts, bank_emb,
                 q_ids, q_texts, q_emb, golds):
        self.name = name
        self.bank_ids = bank_ids
        self.bank_texts = bank_texts
        self.bank_emb = bank_emb          # (n, 1024) float32 or None
        self.q_ids = q_ids
        self.q_texts = q_texts
        self.q_emb = q_emb                # (n, 1024) float32 or None
        self.golds = golds                # qid -> [gold doc ids]
        self._id2pos = {v: i for i, v in enumerate(bank_ids)}

    def golds_list(self):
        return [self.golds.get(q, []) for q in self.q_ids]

    def bank_text_of(self, doc_id):
        i = self._id2pos.get(doc_id)
        return None if i is None else self.bank_texts[i]


def _dense(emb_col, label):
    """list<float> parquet column -> (n, 1024) float32 with length diagnostics."""
    arr = emb_col.to_numpy(zero_copy_only=False)
    if arr.dtype != object:
        a = np.asarray(arr, dtype=np.float32)
        if a.ndim == 2:
            return a
    n = len(arr)
    L = 1024
    dist = collections.Counter(len(v) if v is not None else -1 for v in arr)
    print(f"EMB {label}: n={n} length_dist={dict(sorted(dist.items()))}", flush=True)
    out = np.zeros((n, L), dtype=np.float32)
    for i, v in enumerate(arr):
        if v is None:
            continue
        k = min(len(v), L)
        out[i, :k] = np.asarray(v[:k], dtype=np.float32)
    return out


def load_beir(name, downloads_dir, limit=None):
    import pyarrow.parquet as pq
    base = os.path.join(downloads_dir, name)

    def read_p(rel):
        return pq.ParquetFile(os.path.join(base, rel)).read()

    corpus = read_p(os.path.join("corpus", "0000.parquet"))
    queries = read_p(os.path.join("queries", "test.parquet"))
    qrels = read_p(os.path.join("qrels", "test.parquet"))

    names = [f.name for f in corpus.schema]
    qnames = [f.name for f in queries.schema]

    bank_ids = corpus.column("_id").to_pylist()
    bank_texts = corpus.column("text").to_pylist()
    bank_emb = _dense(corpus.column("emb"), name + " bank") if "emb" in names else None

    q_ids = queries.column("_id").to_pylist()
    q_texts = queries.column("text").to_pylist()
    q_emb = _dense(queries.column("emb"), name + " queries") if "emb" in qnames else None

    golds = {}
    for q, p in zip(qrels.column("query_id").to_pylist(),
                    qrels.column("corpus_id").to_pylist()):
        golds.setdefault(q, []).append(p)

    if limit is not None and limit > 0:
        q_ids = q_ids[:limit]
        q_texts = q_texts[:limit]
        if q_emb is not None:
            q_emb = q_emb[:limit]
        golds = {q: golds[q] for q in q_ids if q in golds}

    return Dataset("beir/" + name, bank_ids, bank_texts, bank_emb,
                   q_ids, q_texts, q_emb, golds)


def load_squad_dev(downloads_dir, max_queries=None):
    import openpyxl
    p = os.path.join(downloads_dir, "SQuAD_v2.0_Dataset-main",
                     "squad_2.0_dev_complete_11873.xlsx")
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = [str(h).lower() for h in next(rows)]
    ci = headers.index("context")
    qi = headers.index("question")

    bank_map = {}
    bank_ids, bank_texts, q_texts, golds = [], [], [], []
    for r in rows:
        ctx = r[ci] or ""
        qst = r[qi] or ""
        key = str(ctx)
        bid = bank_map.get(key)
        if bid is None:
            bid = "ctx%05d" % len(bank_ids)
            bank_map[key] = bid
            bank_ids.append(bid)
            bank_texts.append(key)
        q_texts.append(qst)
        golds.append(bid)
        if max_queries is not None and len(q_texts) >= max_queries:
            break
    wb.close()
    return Dataset("squad2/dev", bank_ids, bank_texts, None,
                   ["squad%d" % i for i in range(len(q_texts))],
                   q_texts, None,
                   {("squad%d" % i): [g] for i, g in enumerate(golds)})


# --------------------------------------------------------------------------- #
# Sentence diagnostic helpers
# --------------------------------------------------------------------------- #
SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def split_sentences(text, min_words=4):
    out = []
    for s in SENT_RE.split((text or "").strip()):
        w = s.split()
        if len(w) >= min_words:
            out.append(" ".join(w))
    if not out:
        t = (text or "").strip()
        if t:
            out = [t]
    return out


def positive_control_texts(data, drop_frac=0.3, seed=7):
    """Reviewer-mandated positive control: the query IS the gold passage itself
    (clean), plus a variant with 30% of its words dropped (deterministic).

    Returns (q_texts, golds_list) aligned lists. A pipeline that cannot
    retrieve these is buggy, not regime-limited.
    """
    g = np.random.Generator(np.random.PCG64(0x5EED ^ seed))
    q_texts, golds = [], []
    seen = set()
    for qid, gl in data.golds.items():
        if not gl:
            continue
        gold0 = gl[0]
        if data.bank_text_of(gold0) is None:
            continue
        if gold0 in seen:
            continue
        seen.add(gold0)
        doc = data.bank_text_of(gold0)
        q_texts.append(doc)
        golds.append([gold0])
        words = doc.split()
        if len(words) > 4:
            keep = set(g.choice(len(words), size=int(len(words) * (1 - drop_frac)),
                              replace=False))
            dropped = " ".join(w for i, w in enumerate(words) if i in keep)
            q_texts.append(dropped)
            golds.append([gold0])
    return q_texts, golds


def load_datasets(cfg, max_queries: int | None = None):
    """Load every dataset named in the config (BEIR + optional SQuAD)."""
    lim = max_queries if (max_queries and max_queries > 0) else None
    out = []
    for name in cfg.beir_datasets:
        out.append(load_beir(name, cfg.downloads_dir, limit=lim))
    if cfg.include_squad:
        out.append(load_squad_dev(cfg.downloads_dir, lim))
    return out
