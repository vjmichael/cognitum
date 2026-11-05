# Cognitum CH-C14-34 — External proof-anchor ledger, bounded-write failures, and original-data verification

**Date:** 2026-11-02 (America/Phoenix)  
**Disposition:** scoped Linux research-engineering verification **PASS**; scientific and production certification **NO-GO**.

## Scope and provenance

Continue CH-C14-33 without modifying any original CH23 dataset, CH29 verified-bound output, CH32 durable journal frame, CH33 compacted checkpoint or interval BnB algorithm. All 15 original CH23 cases are loaded from the preserved CH33 full reproduction bundle. Test the threat of a writable proof store falsely presenting a rolled-back checkpoint by requiring an *externally supplied* anchor hash for every committed ledger generation; require independent MPFR verification before issuing a new anchor proposal. This is **not** an independent deployed witness service: the test harness obtains the pins from a local results file, which must not be confused with an external security domain.

## Implemented

- `anchor34.py`: canonical SHA-256 predecessor-linked anchor revisions with exclusive Linux writer locking; immutable revision create and fsync; atomic HEAD replace and directory fsync; validation against caller-held trusted SHA; schema/case/binding and direct-ancestry checks; retained revisions and fail-closed orphan detection; explicit pending cleanup. Journal checkpoint remains untrusted until CH33's mathematical proof replay completes.
- The scientific-safe entrypoint, `publish_verified_ch33()`, requires a CH33 cold 224-bit MPFR checkpoint replay, complete independent MPFR archive-history replay, and original head/checkpoint SHA-256 identities. The lower-level `AnchorLedger.publish()` is an evidence-storage primitive for tests, **not** proof certification by itself.
- Injected write/rename failure stages and preflight software ledger-budget checks. Independent Linux `RLIMIT_FSIZE` subprocess test causes a *real* kernel file-write refusal (EFBIG), which is not the same as a genuinely full disk (ENOSPC).
- `reconcile_after_head_interruption()` checks direct ancestry and independently recomputed MPFR history before *proposing* an advanced tip. It deliberately does not change or claim to change any caller-held external trust anchor.

## Measured original CH23 results

| Measure | Verified result |
|---|---:|
| Unmodified original CH23 cases | **15/15** |
| Fresh 224-bit MPFR checkpoint bounds recomputed | **1,905** (127 each) |
| Historical CH32 frames independently replayed mathematically | **90/90** (6 each) |
| CH33 archived epochs linked | **30** (2 each) |
| New anchor records written and reread with supplied expected tip | **15/15** |
| Separate new-process cold anchor-history *metadata* verifications | **15/15** (MPFR not rerun in this second process) |
| Maximum CH29 objective-gap-display disagreement | **0** |
| Sum of original-data per-process CPU measurements | **1,281.2 s** (not elapsed wall time) |
| Adversarial Linux ledger-storage regressions | **13/13** |
| Scientific bounded/unrestricted global certificates | **0/15** |

The three previously unresolved zero-event numerical-ambiguity cases stay unresolved. Their refusal is intentional and has not been converted into an acceptance.

## Original-data interrupted advance

Original case `one_event_n80_i00`: recover the authentic CH33 **63-node** checkpoint from the original archived prior-checkpoint envelope, independently replay its MPFR proof, commit the first trusted-pin candidate, install the original **127-node** checkpoint, and independently replay MPFR plus all **six** historical CH32 frames. Inject a controlled ENOSPC-like exception **after HEAD rename** (not actual disk exhaustion), confirm the previous external tip refuses the new HEAD, then mathematically reconcile and return a new candidate only for a separate authority to pin. The test passed; the external pin was **not** automatically rotated. CPU used by this case's two-generation verification: **107.5 s**.

Local storage regressions cover: externally pinned rollback, missing older immutable revision, forged digests, noncanonical/duplicate-key JSON, wrong binding/case, invalid generation/schema, retained interrupted temporary files, interrupted HEAD replacement, storage preflight refusal, orphan-revision cleanup, unknown files and a kernel file-size limit. This is not a hardware power-cut test.

## Reproduction and integrity

Use the bundled original CH23–CH33 reproduction tree with CH34 source and `anchor_storage/` evidence. Set `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` for CPU measurements:

```sh
python -m unittest discover -s CH_C14_34/tests -q
python CH_C14_34/cold_anchor_verify.py CH_C14_34/anchor_results.json CH_C14_34/anchor_storage
python CH_C14_34/audit34.py --workers 3 --output CH_C14_34/anchor_storage_fresh
python CH_C14_34/test_original_forward.py
```

The full audit intentionally refuses to reuse existing anchor output directories; the source original frozen data and retained anchor evidence must not be overwritten. `SHA256SUMS_FULL_CH34.json` in the full delivery ZIP covers every earlier original bundle member and each added CH34 file; old history was copied byte-for-byte from the verified CH33 ZIP.

## Security and portability limits

- **The promised independent trust root is an interface contract, not a deployed service.** An attacker able to rewrite both proof files and the stored expected tip can forge history. The next stage must use a separately controlled signer, non-rollbackable monotonic counter, or independently retained append-only witness with authenticated reads and key-rotation rules; self-contained anchor JSON alone is not a root of trust.
- Only Linux local-filesystem lock/fsync semantics are exercised. NTFS/Windows lock/rename behavior, network filesystems, actual hardware power cuts, hostile-disk behavior, and real full-volume ENOSPC are **untested**.
- Preflight byte accounting is **not a disk reservation**. The archive store remains unbounded, as retaining complete original CH32 mathematical replay evidence remains mandatory.
- CH33 mathematical replay is expensive but intentional. The CH34 metadata-only process check does not substitute for it. SHA-256 tamper evidence is not the mathematical proof.
- The 0.05 original bounded-gap acceptance target remains unmet. **No changes** to Lu or production Cognitum C14/G25; **no production admission**, no unrestricted-global theorem.

## Next work (CH35)

Implement independently authenticated witness persistence and compare-and-swap advancement with stale-client detection; exercise concurrent writers, actual quota/ENOSPC with fault-contained test filesystem where permitted, and read-only adversarial recovery. Then pursue Windows/NTFS and simulated power-loss testing with an explicit threat model. Keep the same 15 frozen original cases and refuse unverified promotions.