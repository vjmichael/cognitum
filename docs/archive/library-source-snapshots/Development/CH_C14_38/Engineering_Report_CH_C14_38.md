# Cognitum CH-C14-38 — Four-UID cryptographic key isolation

**Date:** 2026-11-02 (America/Phoenix)

**Disposition:** Linux scoped CH38 engineering acceptance PASS; production/scientific release **NO-GO**.

## What changed

CH37 used UID 1002 for both original-MPFR calculations and its Ed25519 verifier attestation key. CH38 separates them. The journal writer UID 1000 can request only a frozen case; math UID 1002 owns the original proof files but **no private signature keys**; attestor UID 1003 owns the verifier attestation private key but **no original proof files**; and final signer UID 65534 owns its independent Ed25519 private key and final append-only signed ledger.

A new signer challenge is forwarded through the attestor to the math worker. Attestor binds exact case, nonce, policy and accepted original-data MPFR result to its signature; final signer verifies that ticket and serializes publication. Linux AF_UNIX filesystem ACLs and SO_PEERCRED constrain all three IPC boundaries.

## Measured original-case acceptance

| Metric | Result |
|---|---:|
| Original frozen CH23 cases | **15/15** |
| CH33 original checkpoint nodes reverified | **1,905** |
| Original historical frame replays | **90** |
| Independent final-witness signatures | **15** |
| Independent attestor signatures | **15** |
| Original MPFR precision | **224 bits** |
| Full acceptance elapsed wall seconds | 344.41 |
| Protocol and Linux UID safety regressions | **31 passed** |
| Global-optimality certificates | **0/15** |

The independent read-only public auditor authenticated the full signed history and pinned original CH32 journal heads, CH33 checkpoint SHA digests and SHA-256 checkpoint file bytes. The 15-case acceptance runner, not the public auditor, performed fresh MPFR computation. No synthetic cases replaced any original numerical benchmark.

## Adversarial evidence

- Real OS account tests deny mathematical UID read access to both private keys, deny attestor access to final signer key and sealed mathematical source, deny signer access to original proof files and attestor private key, and deny journal writer all private authority paths.
- Wrong-UID direct socket connections are denied by Linux socket directory permissions and SO_PEERCRED.
- Invalid/missing mathematical responses, altered nonce/case/policy, missing or false replay markers and changed source head are rejected before attestor signature issuance.
- Signer rejects injected writer attestations, repeated cases and reused challenges; startup with absent attestor leaves the witness ledger at unsigned genesis.
- Regression suite retains CH37 journal continuity and crash-failure policy, refuses orphan revisions, unpinned HEAD and wrongly permissioned secrets.

## Critical mathematical trust limitation

**An attacker who fully controls math UID 1002 can still lie to UID 1003 about the arithmetic.** The attestor authenticates *which account provided the report* and protects its key from that account; it cannot independently prove that the reported MPFR calculation occurred. All 15 measured CH38 original proofs actually ran under UID 1002, but that test alone is not a formally verified anti-forgery guarantee against a compromised math worker. To obtain this guarantee, a future verifier under an independent trust domain must replay an untrusted full proof certificate or a checkable compact mathematical transcript before attestation.

Root/host kernel compromise bypasses discretionary Linux UID boundaries. No off-host independently operated witness, protected timestamp, external rollback anchor, power-cut simulation, Windows/NTFS test, production deployment, or math global-optimality proof is claimed. CH36 kernel ENOSPC tests were not repeated as CH38 achievements.

## Engineering recommendation

Next CH39: independently check original certificate mathematics in an OS-isolated audit account before granting signing approval, with measurable correctness/cost and explicit denial under forged math output. Then add separately operated off-host anchoring to close single-host rollback; continue deferring Windows as requested.

Source branch: `cognitum/ch-c14-38-four-uid-attestor-isolation-20261102`; preserve original CH23–CH37 history unchanged.