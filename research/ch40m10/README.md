# Cognitum CH40-M.10 — Durable trusted-verifier checkpoint and crash recovery

**Date:** 2026-11-03 America/Phoenix (2026-11-04 UTC). **Research-only; C14 scientific release NO-GO.**

## What is new

The unmodified CH40-M.8 **independent rational/Decimal replay** checks each pair of original FLINT/MPFR M.9 search journals. Only after it returns a fully checked result does the trusted M.10 coordinator sign the complete per-case audit receipt with an Ed25519 private key and atomically commit the receipt to **SQLite DELETE-journal mode, `synchronous=FULL`, one transaction per original case**.

On restart, the coordinator verifies every persisted row using an **externally pinned trusted public key**, an ordered cryptographic checkpoint chain, the unchanged CH40-K original source SHA pins, 30 current journal SHA hashes, the trusted source-code SHA pins of the independent rational verifier, and the committed proposition/receipt hashes. If all checks pass, it reuses the signed verifier decision without repeating the original rational arithmetic. New cases still require a full independent replay and the private signing key; a public-key-only mode can only validate complete prior work.

A valid signed checkpoint is evidence of a **previous trusted mathematical audit**—not a producer assertion and not new scientific proof. **Without an externally protected signer and public-key trust root, this is not a secure multi-principal production design.** An adversary who can steal the trusted signing private key can forge credentials; an adversary who can roll back the SQLite file to an earlier valid signed prefix may escape detection unless the caller supplies `--expected-tip` from an external independent anchor. The signer may not share a compromised UID/resource domain with an adversarial producer. No production promotion is authorized.

## Original-case measurements

All 15 frozen CH40-K original-case traces were checked by the unchanged M.8 independent bound code against M.9 native search journals. The 15 resulting receipts cover **296/296 exact child-bound checks**; signed checkpoints are committed in original case order. Independent evidence identities and the CH40-J historical signed records are not edited.

One complete fresh run and its signed public-key-only restart, measured externally using GNU `/usr/bin/time`:

| Metric | First full trusted verification | Reopen/recover signed records |
| --- | ---: | ---: |
| Cases accepted | 15 newly verified | 15 accepted signed records |
| Child-bound checks represented | 296 | 296 |
| Rational computations rerun | Yes | **No** |
| Full subprocess user+system CPU | **27.26 sec** | **2.37 sec** |
| Wall clock | 26.94 sec | 1.98 sec |
| Max RSS | 475608 KiB | 105224 KiB |
| Final chained evidence tip | `b4c16cd09913106f4aad582ca1cd2454b8fd2af57eb1f21de73f63961a8ccbea` | Same |

The full-process recovery CPU reduction is **91.3%**, but it is not a whole-solver speedup: the restart is a trusted signed-receipt check, and the initial audit already performed the mathematics. Separate recovery-only internal process CPU measurement was about 1.15 sec. Single controlled run, no confidence interval.

## Crash and tamper acceptance

- Injected a genuine Linux **SIGKILL** immediately after the first committed and signed case: process returned exit **137**; restart found exactly one valid signed case and completed the second without redoing it.
- Genuine `SIGKILL` **inside** an open uncommitted SQLite transaction: SQLite restored the preceding fully verified state, and the 15-case evidence remained valid.
- Reject mutated receipts, maliciously rehashed content with unchanged signatures, wrong verifier key, missing **middle** checkpoint, source pin / immutable run manifest changes, changed journal bytes, negative mathematical proof statement, and release-status forgery. A removed valid **tail** is detected with an independently supplied `--expected-tip`.
- **17/17 original-environment tests passed** with `ResourceWarning` treated as errors. In an isolated source-only environment without the original frozen verifier and fixtures, **5 contract checks pass and 12 original-evidence tests are explicitly skipped**, not misrepresented as mathematical acceptance.

## Reproduce locally (Linux)

Requires Python 3.13, `cryptography`, the existing CH40-M.8 independent verifier sources and CH40-K/CH40-J frozen original evidence in an immutable workspace, and the 30 CH40-M.9 original research journals. For convenience, a copy of the 30 original M.9 *journal files* is included in the evidence ZIP, but not the 800MB original CH40-K source trace collection.

Create an **isolated** verifier private-key directory and publish the trusted public key to an external trusted location. **Do not place the signer private key in the producer's domain or in an artifact ZIP/repository.**

```bash
export CH40M10_WORKSPACE=/path/to/original/research/workspace
python CH40M10/m10_durable_auditor.py --create-keys /secure/verifier-keys
python CH40M10/m10_durable_auditor.py \
  --db /trusted/checkpoints/m10.sqlite \
  --inputs /path/to/m9/journals \
  --public /separately/pinned/verifier-public.key \
  --private /secure/verifier-keys/verifier-private.key \
  --output /trusted/checkpoints/fresh_acceptance.json
# Record the emitted terminal_checkpoint_tip in a separate trusted location.
# Later (no private key needed for a complete signed run):
python CH40M10/m10_durable_auditor.py \
  --db /trusted/checkpoints/m10.sqlite \
  --inputs /path/to/m9/journals \
  --public /separately/pinned/verifier-public.key \
  --expected-tip 'THE_EXTERNALLY_PINNED_TIP' \
  --output /trusted/checkpoints/recovered_acceptance.json
```

`--kill-after-commit 1` is **test-only** and sends actual `SIGKILL`. If the private key cannot be trusted or a signature/hash check fails, recovery **REFUSES**. No fallback to trusting the saved producer result.

## Evidence and limitations

`m10_durable_auditor.py`, `test_m10.py`, independently generated signed SQLite research checkpoint records, test signer **public** key (research only), 30 M.9 original journal files, measured timings, two SIGKILL logs, and SHA-256 file manifest are in the separately supplied conversation ZIP. The signing **private key is expressly omitted**. The GitHub repository contains source, documentation and compact result records; large external frozen cases and secrets are not replicated there.

C14's mathematically certified global finite-root gap has **not** reached 0.05. This phase added *durability, authenticated provenance and rapid restart* to research verification; it did not produce a new global objective bound, demonstrate OS UID isolation of the signing key, provide hardware-backed anti-rollback, or approve a Lu Core Extension. Next sensible gate: isolate the trusted verifier signer from native producers using real OS permissions/job containment and anchor the terminal checkpoint tip to a durable trusted host record before any production use.
