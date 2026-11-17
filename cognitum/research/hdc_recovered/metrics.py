"""Ranking metrics (BEIR conventions) + multi-seed aggregation.

nDCG uses graded relevance (2^g - 1) / log2(i + 2); BEIR qrels are mostly
binary, where this reduces to standard binary nDCG.
"""
from __future__ import annotations

import numpy as np


def _dcg(graded, k):
    total = 0.0
    for i, g in enumerate(graded[:k]):
        if g > 0:
            total += (2.0 ** g - 1.0) / np.log2(i + 2)
    return float(total)


def ndcg_at_k(ranked_ids, rel, k=10):
    """rel: {doc_id: grade}. Returns None if the query has no relevant docs."""
    if not rel:
        return None
    dcg = _dcg([rel.get(d, 0) for d in ranked_ids], k)
    ideal = sorted((g for g in rel.values() if g > 0), reverse=True)[:k]
    idcg = _dcg(ideal, k)
    if idcg <= 0:
        return 1.0
    return float(dcg / idcg)


def evaluate(ranked_ids, rel, n_docs):
    """Per-query metrics from a ranked id list and gold map {doc_id: grade}."""
    if not rel:
        return None
    best = None
    for i, d in enumerate(ranked_ids):
        if d in rel:
            best = i
            break
    if best is None:
        return {"top1": 0, "top10": 0, "ndcg10": 0.0, "rank": n_docs + 1,
                "hit": 0}
    nd = ndcg_at_k(ranked_ids, rel, 10)
    return {
        "top1": int(best == 0),
        "top10": int(best < 10),
        "ndcg10": nd if nd is not None else 0.0,
        "rank": best + 1,
        "hit": 1,
    }


def aggregate(rows, keyfn=None):
    """Group result rows (by dataset, pipeline, D, noise) and average the
    per-seed metrics into mean/std. Rows are dicts with metric fields."""
    if keyfn is None:
        def keyfn(r):
            return (r.get("dataset"), r.get("pipeline"), r.get("D"),
                    r.get("noise"))
    groups = {}
    for r in rows:
        groups.setdefault(keyfn(r), []).append(r)
    out = []
    for k in sorted(groups, key=lambda t: (str(t[0]), str(t[1]), str(t[2]), str(t[3]))):
        rs = groups[k]
        agg = {"dataset": k[0], "pipeline": k[1], "D": k[2], "noise": k[3],
               "n_seeds": len(rs)}
        for m in ("top1", "top10", "ndcg10", "mean_rank", "mean_cos", "n_queries"):
            vals = [r[m] for r in rs if r.get(m) is not None]
            if not vals:
                continue
            agg[m + "_mean"] = round(float(np.mean(vals)), 5)
            if len(vals) > 1:
                agg[m + "_std"] = round(float(np.std(vals, ddof=1)), 5)
        out.append(agg)
    return out
