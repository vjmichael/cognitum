import os, sys
DEV = r"C:\Users\UserMN4312\Documents\Zog Zoo Dev"
os.chdir(DEV)
sys.path.insert(0, DEV)
import numpy as np
from zogzoo_hdc.core import make_streams
from zogzoo_hdc.models import BSC
from zogzoo_hdc.text import CorpusStats, TextEncoder, tokenize

texts = ["the cat sat on the mat near the river bank",
         "a dog ran quickly through the river and the meadow",
         "quantum physics experiments measure the hidden state of a particle",
         "short one",
         "only"]
toks = [tokenize(t) for t in texts]
stats = CorpusStats(toks, True)
m = BSC(256, 7)

def roll_ref(W, i, D):
    return np.roll(W[i], i)

def ngram_ref(W, k, D, model):
    grams = []
    for n in (2, 3):
        for i in range(k - n + 1):
            g = W[i].copy()
            for j in range(1, n):
                g = model.bind(g, roll_ref(W, i + j, D))
            grams.append(g)
    return np.vstack(grams)

ok = True
for scheme in ("hybrid", "ngram"):
    e = TextEncoder(m, scheme, stats, make_streams(42), 64, vocab_cap=1000)
    for t in texts:
        tk = [w for w in tokenize(t) if w in e.word_idx]
        hv = e.encode(tokenize(t))
        if not tk:
            same = np.array_equal(hv, m.neutral())
            ok = ok and same
            print(f"{scheme:8s} k= 0 (empty) identical={same}")
            continue
        idx = np.array([e.word_idx[w] for w in tk])
        W = e.W[idx]
        k = W.shape[0]
        wts = np.array([e.stats.weight(w) for w in tk], dtype=np.float32)
        bag = m.bundle_weighted(W, wts)
        if scheme == "hybrid":
            order = np.array([roll_ref(W, i, m.D) for i in range(k)])
            # encoder design: bundle(order part) then superpose with bag
            ref = m.bundle(np.vstack([bag, m.bundle(order)]))
        else:
            grams = ngram_ref(W, k, m.D, m)
            ref = m.bundle(np.vstack([bag, m.bundle(grams)]))
        same = np.array_equal(hv, ref)
        ok = ok and same
        print(f"{scheme:8s} k={k:2d} identical={same}")
print("EQUIV:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)