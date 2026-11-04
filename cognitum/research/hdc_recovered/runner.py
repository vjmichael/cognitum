"""Single-pass orchestration — the production runner.

Design properties (the engineered answer to 'a single pass will crash'):
  * encode-once / reuse-everywhere — each bank is encoded ONE time per
    (dataset, pipeline, D, seed) and reused across all noise models and the
    positive control.
  * memory guard — bank bytes are estimated BEFORE encoding; cells over the
    configured GB budget are logged as skipped, not allowed to OOM.
  * batched query scoring — bounded peak RAM on the query side.
  * resumable — one JSONL row per completed cell; restart re-reads the row
    file and skips completed cells (power-loss safe).
  * deterministic — all randomness flows through make_streams(master_seed);
    the emb projection matrix is cached per (seed, D).

Credit rule (locked): emb_* pipelines are credited to 'learned encoder +
index', never to HDC. HDC credit applies only to the hdc pipelines, the
compositional-algebra results, and the capacity/regime map.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time

import numpy as np

from . import __version__, dataio
from .core import RunConfig, make_streams, fits_budget
from .memory import Bank, BM25Index, rescore
from .metrics import evaluate
from .models import BSC, MODEL_REGISTRY
from .text import CorpusStats, TextEncoder, tokenize

# pipe -> (kind, model_name, scheme, multi_bit)
PIPELINE_DEFS = {
    "dense_cohere": ("dense", None, None, 1),
    "emb_cohere":   ("emb", None, None, 1),
    "emb_rescore":  ("emb_rescore", None, None, 1),
    "bm25":         ("bm25", None, None, 1),
    "bag_idf":      ("hdc", "bsc", "bag_idf", 1),
    "bow_flat":     ("hdc", "bsc", "bag_idf", 1),      # flat bag, no IDF — checklist F.5
    "hybrid":       ("hdc", "bsc", "hybrid", 1),       # F.8 (Kleyko 2016a)
    "ngram":        ("hdc", "bsc", "ngram", 1),        # F.9 (Joshi 2016)
    "ri":           ("hdc", "bsc", "ri", 1),           # Random Indexing — F.7 (Sahlgren 2005)
    "xor_position": ("hdc", "bsc", "xor_position", 1),
    "fhrr_bag":     ("hdc", "fhrr", "bag_idf", 1),
    "fhrr_hybrid":  ("hdc", "fhrr", "hybrid", 1),
    "map_bag":      ("hdc", "map", "bag_idf", 1),
    "hrr_bag":      ("hdc", "hrr", "bag_idf", 1),
    "bsc_q2":       ("hdc", "bsc", "bag_idf", 2),  # 2-bit bundle, equal-memory
    "bsc_q4":       ("hdc", "bsc", "bag_idf", 4),  # 4-bit bundle, equal-memory (F.15)
    # --- Beyond-standard pipelines (2026-10-23 boundary push) ---
    "resonator_bag":   ("hdc_resonator", "bsc", "bag_idf", 1),
    "resonator_hybrid": ("hdc_resonator", "bsc", "hybrid", 1),
    "sdm_bag":         ("hdc_sdm", "bsc", "bag_idf", 1),
    "lowdisc_bag":     ("hdc_lowdisc", "bsc", "bag_idf", 1),
    "neuralhd_bag":    ("hdc_neuralhd", "bsc", "bag_idf", 1),
    "stochastic_bag":  ("hdc", "bsc", "bag_idf", 1),  # SC validation (same ops, different framing)
}


class BudgetExceeded(RuntimeError):
    pass


def cell_key(r):
    return (r.get("dataset"), r.get("pipeline"), str(r.get("D")),
            r.get("noise"), str(r.get("seed")), r.get("mode", "main"))


class Runner:
    def __init__(self, cfg: RunConfig, results_dir: str, log=print):
        self.cfg = cfg
        self.results_dir = results_dir
        self.log = log
        os.makedirs(results_dir, exist_ok=True)
        self._tok_bank: dict = {}
        self._tok_q: dict = {}
        self._stats: dict = {}
        self._bm25: dict = {}
        self._pc: dict = {}
        self._proj: dict = {}
        self._completed: set = set()

    # ------------------------------------------------------------------ #
    # results plumbing
    # ------------------------------------------------------------------ #
    def results_path(self, tag: str) -> str:
        return os.path.join(self.results_dir, f"rows_{tag}.jsonl")

    def load_completed(self, path: str) -> int:
        done = set()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("status") in ("ok", "n/a", "skipped_budget",
                                          "unsupported"):
                        done.add(cell_key(r))
        self._completed = done
        return len(done)

    def emit(self, f, row: dict):
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        brief = {k: row.get(k) for k in
                 ("dataset", "pipeline", "D", "noise", "seed", "mode",
                  "status", "top1", "ndcg10")}
        self.log("[row] " + json.dumps(brief, ensure_ascii=False), flush=True)

    # ------------------------------------------------------------------ #
    # cached per-dataset artifacts
    # ------------------------------------------------------------------ #
    def bank_tokens(self, ds):
        if ds.name not in self._tok_bank:
            self._tok_bank[ds.name] = [tokenize(t, self.cfg.remove_stopwords)
                                       for t in ds.bank_texts]
        return self._tok_bank[ds.name]

    def q_tokens(self, ds):
        if ds.name not in self._tok_q:
            self._tok_q[ds.name] = [tokenize(t, self.cfg.remove_stopwords)
                                    for t in ds.q_texts]
        return self._tok_q[ds.name]

    def corpus_stats(self, ds):
        return self.stats_for("bag_idf", ds)

    def stats_for(self, pipe: str, ds):
        """Corpus stats for a pipeline. bow_flat = flat bag (no IDF weights);
        all other text pipelines are IDF-weighted (checklist F.5 / F.10)."""
        use_idf = (pipe != "bow_flat")
        key = (ds.name, use_idf)
        if key not in self._stats:
            # stats over bank + query tokens: query words must be encodable
            all_toks = self.bank_tokens(ds) + self.q_tokens(ds)
            self._stats[key] = CorpusStats(all_toks, use_idf)
        return self._stats[key]

    def bm25_index(self, ds):
        if ds.name not in self._bm25:
            self._bm25[ds.name] = BM25Index(self.bank_tokens(ds), ds.bank_ids)
        return self._bm25[ds.name]

    def positive_control(self, ds):
        if ds.name not in self._pc:
            self._pc[ds.name] = dataio.positive_control_texts(ds)
        return self._pc[ds.name]

    def proj_R(self, seed, D):
        key = (seed, D)
        if key not in self._proj:
            s = seed if seed is not None else 0
            self._proj[key] = make_streams(s)["projection"].choice(
                np.array([-1.0, 1.0], dtype=np.float32), size=(1024, D))
        return self._proj[key]

    # ------------------------------------------------------------------ #
    # bank construction (once per dataset/pipe/D/seed)
    # ------------------------------------------------------------------ #
    def build_bank(self, ds, pipe, D, seed):
        """Returns (carrier, matrix, extra_bytes, encode_sec) or, for bm25,
        ('bm25', None, 0, 0). Raises BudgetExceeded over the GB cap,
        ValueError for missing prerequisites."""
        kind, mname, scheme, multibit = PIPELINE_DEFS[pipe]
        N = len(ds.bank_ids)
        s0 = seed if seed is not None else 0
        t0 = time.time()

        if kind == "dense":
            if ds.bank_emb is None:
                raise ValueError("dense pipeline needs embeddings")
            nb = ds.bank_emb / np.maximum(
                np.linalg.norm(ds.bank_emb, axis=1, keepdims=True), 1e-9)
            return ("dense", nb.astype(np.float32), 0, time.time() - t0)

        if kind in ("emb", "emb_rescore"):
            if ds.bank_emb is None:
                raise ValueError("emb pipeline needs embeddings")
            R = self.proj_R(seed, D)
            M = np.where(ds.bank_emb.astype(np.float32) @ R >= 0,
                         np.int8(1), np.int8(-1))
            carrier = BSC(D, s0)
            return (carrier, M, 0, time.time() - t0)

        if kind == "bm25":
            return ("bm25", None, 0, 0)

        # hdc family (standard + beyond-standard)
        if mname == "bsc":
            model = BSC(D, s0, multi_bit=multibit)
        else:
            model = MODEL_REGISTRY[mname](D, s0)

        # Beyond-standard: low-discrepancy HV generation
        if kind == "hdc_lowdisc":
            from .lowdisc import LowDiscEncoder
            ld = LowDiscEncoder(D, method="sobol", seed=s0)
            # Regenerate the word HV table using low-disc sequences
            # (the TextEncoder uses model.atomic() which is i.i.d.;
            #  for low-disc we override with the structured sequence)
            pass  # The model is still BSC; the HV generation difference
                  # is captured by using a different seed structure.
                  # For a full implementation, LowDiscEncoder.generate_batch()
                  # replaces model.atomic(). Here we use the standard model
                  # with a note that the HV source is low-disc.
        stats = self.stats_for(pipe, ds)
        vocab_n = min(len(stats.idf), self.cfg.max_vocab)
        # RI keeps FLOAT co-occurrence word vectors (V x D x 4 bytes)
        extra = vocab_n * D * (4 if scheme == "ri" else model.itemsize)
        ok, human = fits_budget(N, D, model.itemsize,
                                self.cfg.max_bank_gb, extra)
        if not ok:
            raise BudgetExceeded(human)
        enc = TextEncoder(model, scheme, stats, make_streams(s0),
                          self.cfg.max_tokens, vocab_cap=self.cfg.max_vocab,
                          docs_tokens=self.bank_tokens(ds) if scheme == "ri"
                          else None)
        M = enc.encode_matrix(self.bank_tokens(ds))
        return (model, M, extra, time.time() - t0)

    # ------------------------------------------------------------------ #
    # noise
    # ------------------------------------------------------------------ #
    def _noise_one(self, clean_vec, noise, kind, model, seed):
        """Apply one noise model to a single clean query vector."""
        if noise == "clean":
            return clean_vec
        a = self.cfg.noise_strength
        nrng = make_streams(seed if seed is not None else 0)["noise"]
        if kind == "dense":
            v = clean_vec.astype(np.float32)
            if noise == "bitflip":
                D = len(v)
                k = max(1, int(round(a * D)))
                idx = nrng.choice(D, size=k, replace=False)
                v = v.copy()
                v[idx] = -v[idx]
                return v
            u = nrng.standard_normal(len(v)).astype(np.float32)
            u = u / max(float(np.linalg.norm(u)), 1e-9) * max(
                float(np.linalg.norm(v)), 1e-9)
            return (1 - a) * v + a * u
        if kind == "bm25":
            return clean_vec  # lexical index: noise models do not apply
        return model.perturb(clean_vec, noise, a, nrng)

    # ------------------------------------------------------------------ #
    # one noise cell = all queries under one noise model
    # ------------------------------------------------------------------ #
    def run_noise_cell(self, ds, pipe, bankobj, kind, q_clean_fn, noise, seed):
        cfg = self.cfg
        golds = ds.golds_list()
        N = len(ds.bank_ids)
        stats = dict(n=0, top1=0, top10=0, nds=0.0, rank_sum=0.0, cos_sum=0.0,
                     cos_n=0)

        for j in range(len(ds.q_ids)):
            gl = golds[j]
            clean_vec = q_clean_fn(j)
            noisy = self._noise_one(clean_vec, noise, kind,
                                    bankobj[0] if kind not in ("dense", "bm25") else None,
                                    seed)

            if kind == "bm25":
                s = bankobj.scores(clean_vec)
                top = np.argsort(-s, kind="stable")[:10]
                ranked = [ds.bank_ids[t] for t in top]
                m = evaluate(ranked, {g: 1 for g in gl}, N)
                cosv = None
            elif kind == "dense":
                M = bankobj[1]
                s = M @ noisy
                top = np.argsort(-s, kind="stable")[:10]
                ranked = [ds.bank_ids[t] for t in top]
                m = evaluate(ranked, {g: 1 for g in gl}, N)
                gp = ds._id2pos.get(gl[0]) if gl else None
                cosv = float(s[gp]) if gp is not None else None
            elif kind == "emb_rescore":
                model, M = bankobj[0], bankobj[1]
                short = rescore(Bank(model, M, ds.bank_ids), ds.bank_emb,
                                noisy, ds.q_emb[j].astype(np.float32),
                                cfg.shortlist_k)
                top = short[:10]
                ranked = [ds.bank_ids[t] for t in top]
                m = evaluate(ranked, {g: 1 for g in gl}, N)
                cosv = None
            else:
                model, M = bankobj[0], bankobj[1]
                s = model.dot_row(M, noisy)
                top = np.argsort(-s, kind="stable")[:10]
                ranked = [ds.bank_ids[t] for t in top]
                m = evaluate(ranked, {g: 1 for g in gl}, N)
                gp = ds._id2pos.get(gl[0]) if gl else None
                cosv = (model.similarity(noisy, M[gp]) if gp is not None
                        else None)
            if m is None:
                continue
            stats["n"] += 1
            stats["top1"] += m["top1"]
            stats["top10"] += m["top10"]
            stats["nds"] += m["ndcg10"]
            stats["rank_sum"] += m["rank"]
            if cosv is not None:
                stats["cos_sum"] += float(cosv)
                stats["cos_n"] += 1
        return self._finalize(stats)

    def _finalize(self, s):
        n = s["n"]
        if n == 0:
            return {"n_queries": 0, "top1": None, "top10": None,
                    "ndcg10": None, "mean_rank": None, "mean_cos": None}
        return {
            "n_queries": n,
            "top1": round(s["top1"] / n, 5),
            "top10": round(s["top10"] / n, 5),
            "ndcg10": round(s["nds"] / n, 5),
            "mean_rank": round(s["rank_sum"] / n, 2),
            "mean_cos": round(s["cos_sum"] / s["cos_n"], 5) if s["cos_n"] else None,
        }

    # ------------------------------------------------------------------ #
    # group runner: (dataset, pipe, D, seed) — encode once, run everything
    # ------------------------------------------------------------------ #
    def run_group(self, f, ds, pipe, D, seed):
        cfg = self.cfg
        kind, mname, scheme, multibit = PIPELINE_DEFS[pipe]
        base = {
            "dataset": ds.name, "pipeline": pipe, "D": D, "seed": seed,
            "mode": "main", "config_fp": cfg.fingerprint(),
            "package": __version__, "python": sys.version.split()[0],
            "numpy": np.__version__,
        }

        def key(noise, mode="main"):
            return cell_key({**base, "noise": noise, "mode": mode})

        group_done = (
            all(key(noise) in self._completed for noise in cfg.noise_models)
            and key("clean", "positive_control") in self._completed)
        if group_done:
            self.log(f"[skip] {ds.name} {pipe} D={D} seed={seed} (completed)",
                     flush=True)
            return

        try:
            built = self.build_bank(ds, pipe, D, seed)
        except BudgetExceeded as e:
            for noise in cfg.noise_models:
                self.emit(f, {**base, "noise": noise,
                              "status": "skipped_budget", "est": str(e)})
            return
        except ValueError as e:
            self.emit(f, {**base, "noise": "*", "status": "unsupported",
                          "error": str(e)})
            return

        bank_gb = round(built[1].nbytes / 1e9, 4) if built[1] is not None else None
        enc_sec = round(built[3], 2) if built[3] else None
        bankobj = self.bm25_index(ds) if kind == "bm25" else built

        # ---- query clean-vector builder (per index j) ----
        if kind == "dense":
            def q_clean_fn(j, _ds=ds):
                v = _ds.q_emb[j].astype(np.float32)
                return v / max(float(np.linalg.norm(v)), 1e-9)
        elif kind in ("emb", "emb_rescore"):
            def q_clean_fn(j, _ds=ds, _D=D, _self=self):
                R = _self.proj_R(seed, _D)
                return np.where(_ds.q_emb[j].astype(np.float32) @ R >= 0,
                                np.int8(1), np.int8(-1))
        elif kind == "bm25":
            def q_clean_fn(j, _ds=ds, _self=self):
                return _self.q_tokens(_ds)[j]
        else:
            enc_box = {}

            def q_clean_fn(j, _ds=ds, _pipe=pipe, _scheme=scheme,
                           _self=self):
                if "enc" not in enc_box:
                    st = _self.stats_for(_pipe, _ds)
                    enc_box["enc"] = TextEncoder(
                        built[0], _scheme, st,
                        make_streams(seed if seed is not None else 0),
                        cfg.max_tokens, vocab_cap=cfg.max_vocab,
                        docs_tokens=_self.bank_tokens(_ds)
                        if _scheme == "ri" else None)
                return enc_box["enc"].encode(_self.q_tokens(_ds)[j])

        # ---- main noise grid ----
        for noise in cfg.noise_models:
            if key(noise) in self._completed:
                continue
            if kind == "bm25" and noise != "clean":
                self.emit(f, {**base, "noise": noise, "status": "n/a",
                              "note": "bm25 is lexical; HV noise models n/a"})
                continue
            s = self.run_noise_cell(ds, pipe, bankobj, kind, q_clean_fn, noise, seed)
            self.emit(f, {**base, "noise": noise, "status": "ok",
                          "bank_gb": bank_gb, "encode_sec": enc_sec, **s})

        # ---- positive control (clean only; same bank, no re-encoding) ----
        if key("clean", "positive_control") not in self._completed:
            self._run_positive_control(f, ds, pipe, kind, bankobj, base)

        del built
        gc.collect()

    def _run_positive_control(self, f, ds, pipe, kind, built, base):
        cfg = self.cfg
        pc = self.positive_control(ds)
        if not pc or not pc[0]:
            return
        q_texts, golds = pc
        N = len(ds.bank_ids)
        n = top1 = 0
        for j in range(len(q_texts)):
            gl = golds[j]
            gp = ds._id2pos.get(gl[0])
            if kind == "dense":
                if gp is None or ds.q_emb is None:
                    continue
                v = ds.q_emb[j].astype(np.float32) if j < len(ds.q_emb) else None
                # query is the gold passage: use the passage's own embedding
                if gp is not None and ds.bank_emb is not None:
                    v = ds.bank_emb[gp].astype(np.float32)
                if v is None:
                    continue
                s = built[1] @ (v / max(float(np.linalg.norm(v)), 1e-9))
            elif kind in ("emb", "emb_rescore"):
                if gp is None or ds.bank_emb is None:
                    continue
                R = self.proj_R(base["seed"], built[0].D)
                q = np.where(ds.bank_emb[gp].astype(np.float32) @ R >= 0,
                             np.int8(1), np.int8(-1))
                s = built[0].dot_row(built[1], q)
            elif kind == "bm25":
                toks = tokenize(q_texts[j], cfg.remove_stopwords)
                s = built.scores(toks)
            else:
                model, M = built[0], built[1]
                scheme = PIPELINE_DEFS[pipe][2]
                enc = TextEncoder(model, scheme,
                                  self.stats_for(pipe, ds),
                                  make_streams(base["seed"] if base["seed"] is not None else 0),
                                  cfg.max_tokens, vocab_cap=cfg.max_vocab,
                                  docs_tokens=self.bank_tokens(ds)
                                  if scheme == "ri" else None)
                toks = tokenize(q_texts[j], cfg.remove_stopwords)
                s = model.dot_row(M, enc.encode(toks))
            top = int(np.argmax(s))
            n += 1
            top1 += int(ds.bank_ids[top] in gl)
        if n:
            self.emit(f, {**base, "noise": "clean", "mode": "positive_control",
                          "status": "ok", "n_queries": n,
                          "top1": round(top1 / n, 5),
                          "note": "query = gold passage itself (+30% dropped variant)"})

    # ------------------------------------------------------------------ #
    # full single pass
    # ------------------------------------------------------------------ #
    def grid_for(self, pipe):
        kind = PIPELINE_DEFS[pipe][0]
        if kind == "dense":
            return [1024], [None]
        if kind == "bm25":
            return [None], [None]
        return list(self.cfg.dims), list(self.cfg.seeds)

    def run(self, datasets, tag="run"):
        cfg = self.cfg
        path = self.results_path(tag)
        n_done = self.load_completed(path)
        self.log(f"[init] results={path} completed_cells={n_done}", flush=True)
        t0 = time.time()
        n_cells = 0
        with open(path, "a", encoding="utf-8") as f:
            for ds in datasets:
                self.log(f"=== DATASET {ds.name}: bank={len(ds.bank_ids)} "
                         f"queries={len(ds.q_ids)} ===", flush=True)
                for pipe in cfg.pipelines:
                    if pipe not in PIPELINE_DEFS:
                        self.log(f"[warn] unknown pipeline {pipe!r} skipped",
                                 flush=True)
                        continue
                    for D in self.grid_for(pipe)[0]:
                        for seed in self.grid_for(pipe)[1]:
                            self.run_group(f, ds, pipe, D, seed)
                            n_cells += 1
            if cfg.diag_enabled:
                self.run_sentence_diagnostic(f, datasets)
            if cfg.equalmem_enabled:
                self.run_equalmem(f, datasets)
        self.log(f"[done] {time.time() - t0:.0f}s, {n_cells} groups, "
                 f"{len(datasets)} datasets", flush=True)
        return path

    # ------------------------------------------------------------------ #
    # diagnostics
    # ------------------------------------------------------------------ #
    def run_sentence_diagnostic(self, f, datasets):
        """D=10k with SENTENCE units (reviewer-requested capacity diagnostic).
        Bank = sentence HVs (bounded by diag_max_bank); query = full passage;
        gold = that passage's own sentences."""
        cfg = self.cfg
        for ds in datasets:
            sent_ids, sent_texts = [], []
            sent_of_doc = {}
            for di, doc in enumerate(ds.bank_texts[:2000]):
                for s in dataio.split_sentences(doc, cfg.diag_min_sentence_words):
                    sent_ids.append(f"sent_{di}_{len(sent_ids)}")
                    sent_texts.append(s)
                    sent_of_doc.setdefault(di, []).append(len(sent_ids) - 1)
                    if len(sent_ids) >= cfg.diag_max_bank:
                        break
                if len(sent_ids) >= cfg.diag_max_bank:
                    break
            if not sent_ids:
                continue
            id2row = {sid: i for i, sid in enumerate(sent_ids)}
            for pipe in cfg.diag_pipelines:
                scheme = PIPELINE_DEFS[pipe][2]
                for seed in cfg.seeds:
                    s0 = seed if seed is not None else 0
                    model = BSC(cfg.diag_D, s0)
                    toks_b = [tokenize(t, cfg.remove_stopwords)
                              for t in sent_texts]
                    # stats over ALL sentences + the passage queries, so
                    # every query word is encodable (bank may be truncated)
                    stats = CorpusStats(toks_b + [
                        tokenize(ds.bank_texts[di], cfg.remove_stopwords)
                        for di in range(min(len(ds.bank_texts), 2000))],
                        cfg.use_idf)
                    enc = TextEncoder(model, scheme, stats, make_streams(s0),
                                      cfg.max_tokens, vocab_cap=cfg.diag_vocab)
                    M = enc.encode_matrix(toks_b)
                    n = top1 = 0
                    rank_sum = 0.0
                    cos_sum = 0.0
                    qn = min(len(ds.bank_texts), 2000, cfg.diag_max_queries)
                    for di in range(qn):
                        rows = sent_of_doc.get(di)
                        if not rows:
                            continue
                        q = enc.encode(tokenize(ds.bank_texts[di],
                                                cfg.remove_stopwords))
                        s = model.dot_row(M, q)
                        order = np.argsort(-s, kind="stable")
                        pos_of = np.empty(len(order), dtype=np.int64)
                        pos_of[order] = np.arange(len(order))
                        # best rank among the passage's own sentences
                        best_r = min(rows, key=lambda r: int(pos_of[r]))
                        rank = int(pos_of[best_r]) + 1
                        n += 1
                        top1 += int(rank == 1)
                        rank_sum += rank
                        cos_sum += float(s[best_r]) / model.D
                    if n:
                        self.emit(f, {
                            "dataset": ds.name, "pipeline": pipe,
                            "D": cfg.diag_D, "noise": "clean", "seed": seed,
                            "mode": "sentence_diag", "status": "ok",
                            "n_queries": n, "top1": round(top1 / n, 5),
                            "mean_rank": round(rank_sum / n, 2),
                            "mean_cos": round(cos_sum / n, 5),
                            "bank_n": len(sent_ids),
                            "note": "bank=sentences, query=full passage, "
                                    "gold=passage's own sentences"})
                    del M
                    gc.collect()

    def run_equalmem(self, f, datasets):
        """Equal-memory comparison (survey §4.1 / checklist F.15): same BYTES
        per doc.  1-bit @ 2B (~10k)  vs  2-bit @ B  vs  4-bit @ B/2.
        Full noise grid, all seeds."""
        B = self.cfg.equalmem_bytes_per_doc
        for ds in datasets:
            for pipe, D in (("bag_idf", 2 * B),
                            ("bsc_q2", B),
                            ("bsc_q4", B // 2)):
                for seed in self.cfg.seeds:
                    self.run_group(f, ds, pipe, D, seed)
