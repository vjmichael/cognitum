# CH-C14-39 — Restricted independent mathematical certificate checker

**Linux research milestone; scientific/production NO-GO.** Windows deferred. No changes to Cognitum production C14/G25 or Lu.

## The CH38 gap this closes

In CH38, mathematical worker UID 1002 returned a JSON statement of a successful MPFR proof replay. Attestor UID 1003 checked shape, pinned case/head/checkpoint, nonce and policy, but **could not know whether the computation had actually occurred**. A compromised math process could craft the same in-scope result and obtain a signature.

CH39 adds checker **UID 1004**, restricted with its own sealed original CH23 data, original CH33 proof snapshots, protected case manifest, and fresh MPFR worker pool. This checker is separate from writer UID 1000, worker UID 1002, attestor UID 1003, and witness signer UID 65534. The checker has **no signing key**; the worker cannot read or change the checker's proof sources. Both signer keys remain inaccessible to worker and checker.

## Admission / acceptance

1. Writer may request **only** a frozen case ID from the final signer; signer selects unpredictable nonce.
2. Attestor asks UID 1002 to verify original source. Worker returns a **claimed** result.
3. Attestor asks UID 1004 to check that exact result. The checker validates schema, nonce and policy, then **ignores the worker's success claim** and separately opens its own CH23 input, CH33 checkpoint and both archive epochs.
4. Checker uses fresh 224-bit MPFR interval verification of all 127 checkpoint nodes and the six original archived extension stages, comparing historical CH29 objective gaps. It refuses altered certificates and any discrepancy in its recomputed attestation.
5. Attestor accepts a narrowly scoped response **only** from peer UID 1004; checks exact canonical result hashes and binds the checker receipt to case, policy and nonce. Its Ed25519 ticket embeds the checker receipt. The final signer validates the complete ticket before its own signed durable publication.
6. The two Ed25519 domains are CH39-specific; CH38 tickets cannot be replayed as CH39 witnesses.

The signed checker receipt is **not a third signature**. Its authenticity depends on attestor's kernel peer-UID check, protected IPC path, and its own signed ticket. Independent **execution** uses the same mathematical verification code as the worker, so common-mode verifier bugs still exist; this is **not** an independently implemented interval-analysis engine. A compromised checker/attestor/root or rollback of both locally stored anchor and ledger is outside this gate.

## Reproduce

Extract the full CH38 archive and retain the original CH23–CH38 files unchanged. Add the `CH_C14_39` source next to them.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q CH_C14_39/tests/test_checker_gate39.py
# Root required to exercise actual setpriv UIDs, directories and AF_UNIX SO_PEERCRED.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_39/harness39.py \
  --root . --case one_event_n80_i00 --result CH_C14_39/one_case_results.json
# Fresh run/extraction; witness directory must not preexist.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_39/harness39.py \
  --root . --all --result CH_C14_39/original15_results.json
# Fresh full original-case source, malicious forged math-UID daemon:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_39/tests/live_forgery39.py .
# Checker omitted entirely; worker still claims success:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_39/tests/live_no_checker39.py .
# Original CH33 certificate box changed with its internal digests recomputed:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 pytest -q CH_C14_33/tests/test_compaction.py::TestCompaction::test_forged_valid_hashes_cannot_replace_mathematical_proof
```

Read-only public audit on the frozen CH32/CH33 source and independently retained signer/attestor public-key fingerprint + latest tip:

```bash
python CH_C14_39/audit39.py --original . --public CH_C14_39/CH39_public_witness \
  --signer-fingerprint '<external pin>' --attestor-fingerprint '<external pin>' \
  --tip '<external latest trusted tip>' --expected-count 15
```

`audit39.py` confirms signatures, signed checker receipts, original identity/lineage, and the complete externally pinned witness history; it does **not** re-run MPFR mathematics. Full proof verification happens under the real UID 1004 checker in the acceptance run.

## Remaining gates

- A truly independently **implemented** mathematical verifier to reduce shared-code/algorithm bugs.
- Off-host/externally operated immutable anchor, hardware power-loss simulation, and genuine disk quota EDQUOT.
- Production model calibration (global-optimality proof gap is still above 0.05 on all 15 original datasets).
- Windows validation deferred by user.

The only valid signed scientific disposition remains **NO_GO**. Any proof that fails its independent replay is **REFUSED**, never global-optimality certified.
