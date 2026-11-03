# CH40-I — five-UID recovery and crash audit (2026-11-03)

**Scientific release: NO_GO. Full all-15 live-signature acceptance: NOT COMPLETE.**

Recovered CH40-H research sources from the frozen CH40-G/F packages. Ran the Linux five-UID harness under root with distinct writer UID1000, math UID1002, checker UID1004, attestor UID1003, and signer UID65534. The 15-case uninterrupted replay began with one_event_n160_i00; its completion is not established by the current evidence.

### Independently confirmed
- Existing CH40-H/CH40-G protocol suite and new hard-crash regression suite: **38/38 passed**.
- SQLite FULL-sync committed nonce survives process SIGKILL and rejects reuse after restart; an uncommitted transaction rolls back. Corrupted nonce DB is rejected.
- Historical one-case CH40-G public chain verifies against independently supplied pinned key fingerprints and terminal tip. Four deliberate record/anchor/missing-revision/HEAD mutations are rejected.
- The CH40-H 15-record auditor correctly refuses this historical one-record chain.
- Real AF_UNIX UID65534->UID1003 attestor test: consume nonce despite absent math/checker; SIGKILL attestor; relaunch; reject reused challenge with unchanged one-row nonce ledger and zero signatures.

### Outstanding
Fresh 15 signed revisions and independent public verification of all 15; signer mid-publication crash reconciliation (current signer fail-closes and requires manual repair); machine power-failure fault injection and off-host terminal-tip anchoring. Signatures do **not** establish an unrestricted global optimum or close the finite-root 0.05 gap.

The reproducible CH40-I crash tests and service-restart script are archived as `Cognitum_CH40I_Crash_Recovery_Evidence_2026-11-03.zip` in the ChatGPT conversation artifact; this note does not claim that archive is committed to GitHub.
