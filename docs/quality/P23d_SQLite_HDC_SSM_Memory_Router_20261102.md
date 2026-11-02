# Cognitum P23d — SQLite-backed associative router

**Date:** November 2, 2026. Linux research only; no Lu changes; all Windows tasks deferred. GitHub is an engineering repository, not the development environment.

## Verified local experiment

- SQLite persists signed admitted facts, current active/retracted state, conflict view, audit history, approved aliases, indexed exact queries and FTS5 candidate retrieval.
- HDC is a 2,048-dimensional rebuildable character-trigram/token feature-hashed candidate index. It stores no authoritative facts. Every approximate proposal must pass independent SQLite record checks and exact identity/relation verification. Approved aliases require independently signed admission; a similar-looking name never becomes a new identity by itself.
- Actual trained frozen P23b SSM checkpoint processed 128 steps, including 45 missing-observation steps. Memory revisions had zero influence on numerical trajectory; a verified alias resolved the correct identity, then the conflict was returned rather than resolved arbitrarily.
- **12/12 research tests passed** and separately extracted archive re-ran all 12 tests with checksum manifest verification.

## Measured retrieval baseline (300 synthetic memory records, 300 exact and 300 typo queries)

| Method | Exact hits | Typo query proposal recall | Wrong factual assertions | Mean exact-query latency |
|---|---:|---:|---:|---:|
| SQLite exact | 300/300 | 0/300 | 0 | 0.0156 ms |
| SQLite FTS5 ranked BM25 | 300/300 | 300/300 | 0 | 0.7592 ms |
| HDC index | 300/300 | 300/300 | 0 | 0.9068 ms |

**Decision:** HDC is not faster or more accurate than tuned FTS5 in this benchmark, therefore HDC's incremental value is **unproven**. Typo proposals are not verified facts. HDC is not a trained semantic world model, and its primary use here is optional associative routing. The real SSM is **not yet trained to fuse returned associations**, so no prediction benefit has been shown.

## Security caveats

HMAC authenticates admissions only under an assumed trusted upstream signing key; this does not establish factual truth. The research audit history does not resist privileged database rollback, status-bit editing or record deletion. Production needs signed revisions/rollback anchors, concurrency across processes, independent source approval, index repair/replay and adversarial recall validation.

## Reproducibility

Local research artifact `Cognitum_P23d_SQLite_HDC_SSM_Memory_Router_2026-11-02.zip`, SHA256 `815a40fae63500bfa89f3f249ae8c0cc4ac58f429274abfb834061d22519ad3c`, includes Python source, tests, trained P23b checkpoint, exact measurement JSON, report, SHA-256 manifest. After fresh extraction all 12 tests passed and 8/8 manifest member checks passed. **The code is in the archive, not merged into production.**

Next: run realistic scene/character consistency benchmark comparing exact, FTS5, vector retrieval, HDC, and hybrid models; study evidence and alias drift; add tamper-evident externally anchored event verification; measure actual SSM memory-integration task improvement before promotion.
