# Cognitum CH40-G — Engineering acceptance and risk boundaries

## Objective and implementation

Integrate CH40-F's independent, actual MPFR-producer bound certification into the existing research CH39 signer/attestor architecture. Preserve Linux separation, forbid worker-supplied assertions, and sign a **distinct CH40-G research-only** witness domain, never silently upgrading the CH39 evidence. This builds on exact pinned original CH23/CH29 inputs and CH32–33 archival certificates.

## Actual protocol

1. Writer UID1000 submits only a frozen original-case request to signer UID65534. Signer audits its durable ledger, enforces non-duplication, and creates a cryptographically random nonce.
2. Attestor UID1003 requests a fresh original CH39 224-bit MPFR 127-node + six-frame replay from UID1002 over SO_PEERCRED; this report alone is insufficient.
3. Attestor requests from UID1004, whose private files are inaccessible to other service identities, a fresh second CH39 224-bit replay plus CH40-F's separately implemented exact-rational/Decimal verification of the original historical producer's 160-bit MPFR direct, coupled, and inherited bounds. The trace hash and exact cap counts are checked against a frozen 15-case policy.
4. UID1003 signs the original worker and independent checker receipts together in `Cognitum/CH40G/RESEARCH/attestor-dual-math-caps/v1`. The ticket contains the case/source/producer trace/certificate hashes, nonce, 127 local and inherited bounds, explicit `NO_GO`, and restricted research scope.
5. UID65534 cryptographically verifies the attestor ticket and the research-cap claims again (including exact per-case 83/44 counts for the accepted case), appends a durable chained revision under its own Ed25519 domain `Cognitum/CH40G/RESEARCH/signer-chained-witness/v1`, and updates the pin. Separate public audit checks the full chain.

## Completed live acceptance

See `CH40G_FINAL_ACCEPTANCE.json` for all timings and SHA-256 anchors. The positive proof and public signature chain passed for `one_event_n80_i00` with 83 direct and 44 coupled producer bounds, 127 inherited caps, and zero unsupported caps. Live missing-checker, tampered-trace, mid-verification checker termination, and forged-worker scenarios all produced **zero signed revisions**. Twenty-five forged/promotion/replay protocol test cases passed. Linux UID access denial and signer process restart were directly exercised.

## Limitations / no-go

The 15-case CH40-F offline mathematical matrix is **not** a 15-case live CH40-G service acceptance; this gate intentionally exercised one complete real signed proof. The mathematical results remain finite-domain bounds and do not close the global-optimality gap. The attestor checker nonce set is in-memory (the signer durable ledger prevents duplicate already-signed cases), and no real sudden power cut or remotely pinned monotone tip was exercised. Importing the CH39 architecture into this distinct research fork is not production integration, and neither Lu nor Cognitum production C14/G25 changed. Signed witnesses contain NO private keys. Scientific disposition: **NO_GO**.