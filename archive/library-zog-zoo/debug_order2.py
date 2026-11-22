import os, sys
DEV = r"C:\Users\UserMN4312\Documents\Zog Zoo Dev"
os.chdir(DEV)
sys.path.insert(0, DEV)
import numpy as np
from zogzoo_hdc.core import make_streams
from zogzoo_hdc.models import BSC
from zogzoo_hdc.text import CorpusStats, TextEncoder, tokenize

texts = ["the cat sat on the mat near the river bank"]
toks = [tokenize(t) for t in texts]
stats = CorpusStats(toks, True)
m = BSC(256, 7)
e = TextEncoder(m, "hybrid", stats, make_streams(42), 64, vocab_cap=1000)
tk = tokenize(texts[0])
idx = np.array([e.word_idx[w] for w in tk])
W = e.W[idx]
k = W.shape[0]
D = m.D
wts = np.array([e.stats.weight(w) for w in tk], dtype=np.float32)
bag = m.bundle_weighted(W, wts)
order = np.empty_like(W)
for i in range(k):
    order[i] = np.roll(W[i], i)
ref = m.bundle(np.vstack([bag, order]))
hv = e.encode(tk)
print("bag identical:", np.array_equal(bag, bag))
print("final identical:", np.array_equal(hv, ref), "ndiff:", int(np.sum(hv != ref)))
d = np.where(hv != ref)[0]
if len(d):
    print("diff cols:", d[:10])
    # inspect the pre-binarize sums at those cols
    s1 = np.sum(np.vstack([bag, order]), axis=0, dtype=np.int32)
    print("sums at diff:", s1[d[:10]])