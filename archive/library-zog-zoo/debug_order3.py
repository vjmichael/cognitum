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
D = m.D

# --- exact encoder path ---
toks_tr = tk[:e.max_tokens]
toks_f, W_enc = e._word_hvs(toks_tr)
wts_enc = np.array([e.stats.weight(t) for t in toks_f], dtype=np.float32)
bag_enc = m.bundle_weighted(W_enc, wts_enc)
k = W_enc.shape[0]
rows = np.arange(k)
cols = (np.arange(D)[None, :] - rows[:, None]) % D
order_enc = W_enc[rows[:, None], cols]
final_enc = m.bundle(np.vstack([bag_enc, order_enc]))

# --- my check path ---
idx = np.array([e.word_idx[w] for w in toks_f])
W_chk = e.W[idx]
wts_chk = np.array([e.stats.weight(w) for w in toks_f], dtype=np.float32)
bag_chk = m.bundle_weighted(W_chk, wts_chk)
order_chk = np.empty_like(W_chk)
for i in range(k):
    order_chk[i] = np.roll(W_chk[i], i)
final_chk = m.bundle(np.vstack([bag_chk, order_chk]))

print("W same:", np.array_equal(W_enc, W_chk))
print("wts same:", np.array_equal(wts_enc, wts_chk))
print("bag same:", np.array_equal(bag_enc, bag_chk))
print("order same:", np.array_equal(order_enc, order_chk))
print("final same:", np.array_equal(final_enc, final_chk))
print("encode() matches internal:", np.array_equal(e.encode(tk), final_enc))
print("encode() matches my check:", np.array_equal(e.encode(tk), final_chk))