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

ref = np.empty_like(W)
for i in range(k):
    ref[i] = np.roll(W[i], i)

rows = np.arange(k)
cols = (np.arange(D)[None, :] - rows[:, None]) % D
vec = W[rows[:, None], cols]

print("k =", k, "D =", D)
print("ref row0:", ref[0][:8])
print("vec row0:", vec[0][:8])
print("row1 ref:", ref[1][:8])
print("row1 vec:", vec[1][:8])
diff = np.where(ref != vec)
print("ndiff:", len(diff[0]))
if len(diff[0]):
    i, j = diff[0][0], diff[0][1]
    print(f"first diff at row {i} col {j}: ref={ref[i,j]} vec={vec[i,j]} W[{i},{(j-i)%D}]={W[i,(j-i)%D]}")