"""Invariant suite for the Zog Zoo HDC component.

Runs on synthetic in-memory data only — no datasets, no network. Every
failure is a bug in the algebra/index/metrics, not a regime finding.

Usage:  python -m zogzoo_hdc selftest
"""
from __future__ import annotations

import math

import numpy as np

from .core import bank_bytes, fits_budget, make_streams, stream_check
from .memory import Bank, BM25Index, rescore
from .metrics import evaluate, ndcg_at_k
from .models import BSC, FHRR, HRR, MAP
from .text import CorpusStats, TextEncoder, tokenize


def _fresh(seed=11):
    return make_streams(seed)


def test_streams():
    a = stream_check(42, "word")
    b = stream_check(42, "word")
    c = stream_check(42, "position")
    d = stream_check(43, "word")
    assert a == b, "same (seed, stream) must reproduce"
    assert a != c, "different streams must differ"
    assert a != d, "different master seeds must differ"


def test_bsc_algebra():
    m = BSC(1024, seed=1)
    rng = _fresh()["run"]
    a, b = m.atomic(2, rng)[0], m.atomic(2, rng)[1]
    bound = m.bind(a, b)
    rec = m.unbind(a, bound)
    assert np.array_equal(rec, b), "BSC unbind must be exact (self-inverse)"
    # cleanup: bundled superposition must be closest to one of its members
    items = m.atomic(200, rng)
    pick = np.arange(5)
    s = m.bundle(items[pick])
    best = int(np.argmax(m.dot_row(items, s)))
    assert best in set(pick.tolist()), "cleanup must return a member"


def test_bsc_capacity():
    """D=1024, m=5 items bundled, N=100 dictionary: recall must be high."""
    m = BSC(1024, seed=2)
    rng = _fresh(3)["run"]
    items = m.atomic(100, rng)
    ok = 0
    for t in range(200):
        pick = rng.choice(100, size=5, replace=False)
        s = m.bundle(items[pick])
        best = int(np.argmax(m.dot_row(items, s)))
        ok += int(best in set(pick.tolist()))
    assert ok / 200 >= 0.9, f"BSC recall {ok/200} below 0.9"


def test_fhrr_unbind():
    m = FHRR(1024, seed=1)
    rng = _fresh()["run"]
    a, b = m.atomic(2, rng)[0], m.atomic(2, rng)[1]
    rec = m.unbind(a, m.bind(a, b))
    sim = m.similarity(rec, b)
    assert sim > 0.99, f"FHRR unbind near-exactness failed: {sim}"


def test_fhrr_cleanup():
    m = FHRR(512, seed=2)
    rng = _fresh(3)["run"]
    items = m.atomic(150, rng)
    ok = 0
    for t in range(100):
        pick = rng.choice(150, size=4, replace=False)
        s = m.bundle(items[pick])
        best = int(np.argmax(m.dot_row(items, s)))
        ok += int(best in set(pick.tolist()))
    assert ok / 100 >= 0.85, f"FHRR cleanup recall {ok/100} below 0.85"


def test_map_and_hrr():
    m = MAP(512, seed=1)
    rng = _fresh()["run"]
    a, b = m.atomic(2, rng)[0], m.atomic(2, rng)[1]
    assert np.array_equal(m.unbind(a, m.bind(a, b)), b), "MAP self-inverse"

    h = HRR(256, seed=1)
    a, b = h.atomic(2, rng)[0], h.atomic(2, rng)[1]
    rec = h.unbind(a, h.bind(a, b))
    sim = h.similarity(rec, b)
    # KNOWN WEAKNESS: HRR deconvolution noise caps round-trip ~0.71 at all D
    # (measured 2026-10-21; matches Tier A H2: mean 0.77 / min 0.17).
    # This is exactly why FHRR (conjugate unbind) is the near-exact family.
    assert sim > 0.65, f"HRR conv/corr round-trip collapsed: {sim}"


def test_noise_semantics():
    m = BSC(512, seed=1)
    rng = _fresh()["run"]
    v = m.atomic(1, rng)[0]
    a = 0.2
    # bitflip flips exactly round(a*D) coordinates
    bf = m.perturb(v, "bitflip", a, rng)
    assert int(np.sum(bf != v)) == int(round(a * 512))
    # mixture: cos(v, out) == (1-a)/sqrt((1-a)^2 + a^2), and out != v (old bug)
    mx = m.perturb(v, "mixture", a, rng)
    cos = float(np.dot(v, mx)) / (512 * float(np.linalg.norm(mx)) / np.sqrt(512))
    expected = (1 - a) / math.sqrt((1 - a) ** 2 + a ** 2)
    assert abs(cos - expected) < 0.02, f"mixture cos {cos} vs {expected}"
    assert not np.array_equal(mx.astype(np.int8), v), "mixture must change the vector"
    # clean is identity
    assert np.array_equal(m.perturb(v, "clean", a, rng), v)
    # FHRR bitflip rotates exactly round(a*D) components
    f = FHRR(512, seed=1)
    w = f.atomic(1, _fresh()["run"])[0]
    bf2 = f.perturb(w, "bitflip", a, rng)
    assert int(np.sum(bf2 != w)) == int(round(a * 512))


def test_bm25():
    docs = [
        ["the", "cat", "sat"],
        ["the", "dog", "ran"],
        ["cat", "dog", "bird"],
        ["xyzzy", "flurb"],
        ["cat", "cat", "cat", "bird", "bird"],
    ]
    ids = ["d%d" % i for i in range(5)]
    idx = BM25Index(docs, ids)
    top, _ = idx.search(["cat", "sat"], k=5)
    assert ids[int(top[0])] == "d0", "exact-match doc must rank first"
    # rare word must have higher idf than common one
    assert idx.idf["xyzzy"] > idx.idf["the"]


def test_ndcg_handcheck():
    # rel: a=3, b=1; ranked [b, a, c]
    # DCG = 1/1 + 7/log2(3);  IDCG = 7/1 + 1/log2(3)
    n = ndcg_at_k(["b", "a", "c"], {"a": 3, "b": 1}, 10)
    dcg = (2 ** 1 - 1) / math.log2(2) + (2 ** 3 - 1) / math.log2(3)
    idcg = (2 ** 3 - 1) / math.log2(2) + (2 ** 1 - 1) / math.log2(3)
    assert abs(n - dcg / idcg) < 1e-9
    assert ndcg_at_k(["x"], {}, 10) is None
    # perfect rank = 1.0
    assert abs(ndcg_at_k(["a", "b"], {"a": 3, "b": 1}, 10) - 1.0) < 1e-9


def test_evaluate():
    ranked = ["d0", "d1", "d2"]
    m = evaluate(ranked, {"d1": 1}, 10)
    assert m["top1"] == 0 and m["top10"] == 1 and m["rank"] == 2
    m = evaluate(ranked, {"d5": 1}, 10)
    assert m["top1"] == 0 and m["rank"] == 11  # miss -> N+1
    assert evaluate(ranked, {}, 10) is None


def test_rescore_fixes_order():
    """Constructed case: binary shortlist order is wrong, float order is right."""
    m = BSC(64, seed=1)
    rng = _fresh()["run"]
    A, B, C = m.atomic(3, rng)
    q_bin = A.copy()                      # binary: A is the exact match
    # float space disagrees: B is the true answer, A is a decoy
    float_bank = np.stack([
        np.array([0.0, 1.0, 0.0]),   # A (decoy in float space)
        np.array([1.0, 0.0, 0.0]),   # B (true answer)
        np.array([0.0, 0.0, 1.0]),   # C
    ])
    q_float = np.array([0.95, 0.05, 0.0])
    bank = Bank(m, np.stack([A, B, C]), ["A", "B", "C"])
    assert bank.search(q_bin, k=3)[0][0] == 0, "sanity: binary puts A first"
    final = rescore(bank, float_bank, q_bin, q_float, k=3)
    assert final[0] == 1, "rescore must prefer the float-closer item"


def test_text_encoder():
    texts = [
        "the cat sat on the mat",
        "the cat and the dog played",
        "quantum physics experiments",
    ]
    stats = CorpusStats([tokenize(t) for t in texts])
    m = BSC(256, seed=1)
    e1 = TextEncoder(m, "bag_idf", stats, _fresh(1), 64)
    e2 = TextEncoder(m, "bag_idf", stats, _fresh(1), 64)
    h1 = e1.encode(tokenize(texts[0]))
    h2 = e2.encode(tokenize(texts[0]))
    assert np.array_equal(h1, h2), "same seed must be deterministic"
    e3 = TextEncoder(m, "bag_idf", stats, _fresh(2), 64)
    assert not np.array_equal(h1, e3.encode(tokenize(texts[0]))), \
        "different seed must give different word HVs"
    # similarity sanity: overlapping texts closer than disjoint
    h_a = e1.encode(tokenize(texts[0]))
    h_b = e1.encode(tokenize(texts[1]))
    h_c = e1.encode(tokenize(texts[2]))
    assert m.similarity(h_a, h_b) > m.similarity(h_a, h_c)


def test_encoder_consistency_pc():
    """REGRESSION (2026-10-21 smoke): two encoders from the same
    (stats, streams) must share the EXACT same word->HV table. The
    positive control depends on this: encoding a bank document as a
    query with a fresh encoder must rank that document first. (The old
    incremental word-table growth made bank and query disagree -> PC
    top1 = 0.0 on every HDC pipeline.)"""
    texts = [
        "alpha beta gamma delta epsilon zeta",
        "beta alpha delta gamma epsilon zeta",
        "eta theta iota kappa lambda mu",
    ]
    stats = CorpusStats([tokenize(t) for t in texts])
    m = BSC(256, seed=1)
    e1 = TextEncoder(m, "bag_idf", stats, _fresh(5), 64)
    e2 = TextEncoder(m, "bag_idf", stats, _fresh(5), 64)
    h1 = e1.encode(tokenize(texts[0]))
    h2 = e2.encode(tokenize(texts[0]))
    assert np.array_equal(h1, h2), \
        "same (stats, streams) must give identical encodings"
    bank = Bank(m, np.stack([e1.encode(tokenize(t)) for t in texts]),
                ["a", "b", "c"])
    top, _ = bank.search(e2.encode(tokenize(texts[0])), k=3)
    assert int(top[0]) == 0, "positive control: query=bank doc must rank first"


def test_ri_encoder():
    """REGRESSION (checklist §B.1): Random Indexing — the standard HDC text
    encoder. word vector = superposition of doc indices (co-occurrence, not
    i.i.d. per-word randoms). Deterministic from (docs, seed); binary output;
    positive control: own doc must rank first."""
    docs = [
        ["alpha", "beta", "gamma", "delta"],
        ["beta", "gamma", "epsilon"],
        ["zeta", "eta", "theta", "iota"],
        ["alpha", "zeta", "mu"],
    ]
    stats = CorpusStats(docs)
    m = BSC(128, seed=3)
    e1 = TextEncoder(m, "ri", stats, _fresh(9), 64, docs_tokens=docs)
    e2 = TextEncoder(m, "ri", stats, _fresh(9), 64, docs_tokens=docs)
    h1 = e1.encode(docs[0])
    h2 = e2.encode(docs[0])
    assert np.array_equal(h1, h2), "RI must be deterministic from (docs, seed)"
    assert set(np.unique(h1)) <= {-1, 1}, "RI output must be binary ±1"
    bank = Bank(m, np.stack([e1.encode(d) for d in docs]), ["a", "b", "c", "d"])
    top, _ = bank.search(e1.encode(docs[2]), k=4)
    assert int(top[0]) == 2, "RI positive control: own doc must rank first"


def test_corpus_stats_deterministic():
    """LOCKED (2026-10-21): stats key order must be sorted — Python string
    hashing is randomized per process, so set/dict order was drifting the
    word->HV assignment between runs."""
    toks = [["delta", "alpha", "charlie"],
            ["charlie", "alpha"], ["alpha"]]
    s1 = CorpusStats(toks, True)
    s2 = CorpusStats(toks, True)
    assert list(s1.idf.keys()) == sorted(s1.idf.keys()), \
        "idf key order must be sorted (hash-randomization-safe)"
    assert list(s1.idf) == list(s2.idf)


def test_hybrid_preserves_overlap():
    """F2 regression guard: hybrid (bag + order) must keep word-overlap
    similarity positive even when word order differs — the property the old
    XOR-position pipeline lost."""
    stats = CorpusStats([
        tokenize("alpha beta gamma delta"),
        tokenize("beta alpha delta gamma"),
        tokenize("zzz qqq www eee"),
    ])
    m = BSC(512, seed=1)
    e = TextEncoder(m, "hybrid", stats, _fresh(1), 64)
    h1 = e.encode(tokenize("alpha beta gamma delta"))
    h2 = e.encode(tokenize("beta alpha delta gamma"))
    h3 = e.encode(tokenize("zzz qqq www eee"))
    assert m.similarity(h1, h2) > m.similarity(h1, h3), \
        "hybrid must preserve word-overlap across order changes"


def test_bank_search():
    m = BSC(128, seed=1)
    rng = _fresh()["run"]
    items = m.atomic(50, rng)
    bank = Bank(m, items, [f"d{i}" for i in range(50)])
    q = items[17]
    top, s = bank.search(q, k=5)
    assert int(top[0]) == 17
    assert bank.rank_of(q, ["d17"]) == 1
    assert bank.rank_of(q, ["d3"]) > 1


def test_memory_math():
    assert bank_bytes(57638, 1024, 1) == 57638 * 1024
    ok, human = fits_budget(57638, 1024, 1, 4.0)
    assert ok and "GB" in human
    ok2, _ = fits_budget(57638, 10000, 8, 4.0)  # FHRR @10k = 4.6GB
    assert not ok2


def test_stopwords_and_idf():
    toks = tokenize("The cat sat on the mat, the cat purred.")
    assert "the" not in toks and "cat" in toks
    stats = CorpusStats([[ "rare", "common" ], ["common", "common" ], ["common"]])
    assert stats.weight("rare") > stats.weight("common")


def test_parallel_config():
    """Verify CPU detection and BLAS threading are configured."""
    import os
    from .parallel import n_workers, set_blas_threads, verify_blas_threads
    n = n_workers()
    assert n >= 1, f"n_workers() returned {n}"
    assert n >= 4, f"expected >= 4 threads on this machine, got {n}"
    # BLAS threads should be set (via __init__.py call to set_blas_threads)
    env_val = int(os.environ.get("OPENBLAS_NUM_THREADS", "1"))
    assert env_val >= 1, f"OPENBLAS_NUM_THREADS={env_val}"
    ok = verify_blas_threads()
    print(f"  [parallel] cores={n} OPENBLAS={env_val} blas_multithreaded={ok}",
          flush=True)


def run_all():
    from .parallel import report
    print(report(), flush=True)
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}", flush=True)
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}", flush=True)
    print(f"\n{len(tests) - failed}/{len(tests)} passed", flush=True)
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all() else 1)
