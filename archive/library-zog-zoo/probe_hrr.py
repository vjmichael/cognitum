import os, sys
DEV = r"C:\Users\UserMN4312\Documents\Zog Zoo Dev"
os.chdir(DEV)
sys.path.insert(0, DEV)
import numpy as np
from zogzoo_hdc.models import HRR
from zogzoo_hdc.core import make_streams

rng = make_streams(7)["run"]
for D in (128, 256, 512, 1024, 2048):
    h = HRR(D, seed=1)
    sims = []
    for _ in range(30):
        a, b = h.atomic(2, rng)
        rec = h.unbind(a, h.bind(a, b))
        sims.append(h.similarity(rec, b))
    print(f"D={D}: mean={np.mean(sims):.4f} min={np.min(sims):.4f} "
          f"p05={np.percentile(sims,5):.4f}")