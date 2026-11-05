# Cognitum CH40-G — authenticated live research attestation

Research integration of CH39's separated Linux roles with CH40-F's independent original-producer cap checker. **Scoped Linux PASS:** one original frozen case, 127 nodes, 83 original direct and 44 coupled caps, 127 inherited caps, two CH39 224-bit MPFR replays (worker and independent checker), and one 160-bit original producer-trace replay in separate rational/Decimal checker.

Original CH23 case: `one_event_n80_i00`. Five genuine numeric Linux UIDs: writer 1000, math 1002, checker 1004, attestor 1003, signer 65534. Original source zip SHA-256 and all fifteen trace/certificate pins are frozen in code. Checker-source and signing-key directory access is OS-restricted. AF_UNIX SO_PEERCRED checks apply at worker/checker/attestor/signer request boundaries. Private keys generated within their own process identities, deleted after acceptance.

**Four live failed-attack gates:** unavailable checker; altered pinned producer trace; checker terminated during fresh verification; forged UID1002 worker report. All four denied attestation and created zero signed records. Protocol test suite: 25/25. Positive witnessed chain is independently publicly auditable with one attestor Ed25519 signature and one signer Ed25519 signature and its SHA-256 tip. Duplicate case signing after a clean signer restart refused.

## Reproduction

Extract the package to a short path on Linux. The system must support Python 3.13+, `cryptography`, MPFR/GMP libraries, `setpriv`, and numeric UID isolation under root. This is **not** a Windows test or installer. Run `sudo ./RUN_CH40G_LINUX_RESEARCH.sh valid` to set up the disposable baseline and execute the full live proof. Attack modes: `missing-checker`, `tampered-trace`, `interrupted-checker`, `forged-worker` (they create distinct temporary UIDs/keys). Outputs of new runs are under `results/`.

Source-only policy tests: `python -m pytest -q source/tests/test_protocol40g.py`. The package's `accepted_results/` contains the original live outputs, public chain, and source evidence without any private key. The read-only auditor needs an external trust anchor; do not treat a tip included in the same ZIP as an independently published anchor. The observed local anchor values are in `CH40G_FINAL_ACCEPTANCE.json`.

## Important limits

This is a **research fork**, not a deployment of Cognitum C14/G25 or Lu, and not an update to the historical CH39 signed chain. CH40-G uses its own signature domains to avoid accidental CH39 acceptance. The 14 other original datasets were mathematically checked in CH40-F, but not live signed through these five UID services. No original Taylor/Newton certificate is promoted, no finite-root 0.05 gap closes, and no unrestricted global optimum is certified. Power-failure reconciliation, attestor nonce persistence across restart independent of the signer, and off-host tip anchoring are still open.