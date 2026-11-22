import os, sys
DEV = r"C:\Users\UserMN4312\Documents\Zog Zoo Dev"
os.chdir(DEV)
sys.path.insert(0, DEV)
import numpy as np
from zogzoo_hdc.core import make_streams
from zogzoo_hdc.models import BSC, FHRR, HRR, MAP
from zogzoo_hdc.text import CorpusStats, TextEncoder, tokenize
from zogzoo_hdc.memory import Bank

texts = ["the cat sat on the mat near the river",
         "a dog ran through the river and the meadow",
         "quantum physics experiments measure the state"]
toks = [tokenize(t) for t in texts]
stats = CorpusStats(toks, True)

cases = [
    ("ngram", BSC(256, 1)),
    ("fhrr_hybrid", FHRR(256, 1), "hybrid"),
    ("hrr_bag", HRR(256, 1), "bag_idf"),
    ("xor_position", BSC(256, 1)),
    ("bag_idf", MAP(256, 1)),
]
for case in cases:
    label, model = case[0], case[1]
    scheme = case[2] if len(case) > 2 else label
    st = make_streams(20261020)
    enc = TextEncoder(model, scheme, stats, st, 64, vocab_cap=1000)
    M = enc.encode_matrix(toks)
    bank = Bank(model, M, ["d0", "d1", "d2"])
    top, s = bank.search(enc.encode(tokenize(texts[0])), k=3)
    print(f"{label:14s} OK  top={list(top)}  sims={[round(float(x),3) for x in s]}")
print("ALL PIPELINE PROBES OK")