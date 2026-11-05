"""Render factual CH37 engineering report from original frozen acceptance evidence."""
import json
from pathlib import Path
D=Path(__file__).resolve().parent

def main():
    data=json.loads((D/'original15_results.json').read_text())
    audit=json.loads((D/'public_audit.json').read_text())
    names=data['signed_audit']['cases']
    if data['case_count']!=15 or audit['signed_cases']!=15 or len(names)!=15:
        raise AssertionError('Cannot publish CH37 report without all original cases')
    if set(names)!=set(audit['signed_case_names']):raise AssertionError('Audited cases changed')
    text=f'''# Cognitum CH-C14-37 — Verified separation of mathematical verifier from witness signing key

**Date:** November 2, 2026 (America/Phoenix)  
**Engineering disposition:** scoped Linux account-separation acceptance **PASS**.  
**Scientific/global-optimality/production disposition:** **NO-GO**, 0 of 15 certified.  
**Windows and NTFS:** intentionally deferred by user. No production Cognitum C14/G25 or Lu code changed.

## Rationale and threat-boundary correction

In CH36 a mathematical verifier worker ran in a separate OS process but still shared the Ed25519 signing UID and could read its private key. CH37 implements three genuinely independent Linux account identities for the original 15-case research workflow:

| Principal | Linux UID | Protected assets | Inaccessible assets |
|---|---:|---|---|
| Journal writer | 1000 | Its own case-only client | Both private keys, sealed original source, direct verifier socket |
| Mathematical verifier | 1002 | Frozen original CH23–CH33 proof source, 224-bit MPFR, **verifier ticket key** | Witness signer's separate Ed25519 private key and signer IPC |
| Witness signer | 65534 | Witness signing key, 15-case frozen policy, verifier public key and signed append-only records | Verifier's private ticket key and full original proof source |

Unix-domain sockets are group-restricted (0660 in setgid access directories) and handlers enforce Linux `SO_PEERCRED`. The writer is allowed to provide only a frozen case ID; it cannot supply its own attestation, proof bytes, hash, signing key or path.

The signer issues a fresh 256-bit nonce bound to a signer-controlled policy hash. The verifier checks the same independently provisioned 15-case original policy, replays the 127-node original CH33 MPFR proof and six CH32 archived frames, checks the original CH29 gap evidence, and signs a strictly scoped attestation under its **different** verifier Ed25519 key. The signer verifies that ticket signature, nonce, case, original CH32 head and CH33 checkpoint, proof status and expected scientific refusal before making a separate V2 signer signature. Every V2 record embeds the verifier-signed source attestation; public auditors authenticate both signature layers.

## Exact frozen CH23 numerical acceptance

| Test | Result |
|---|---:|
| Original CH23 cases mathematically reverified under verifier UID 1002 | **15/15** |
| Original 127-node checkpoint nodes independently replayed | **1,905** |
| Original six-frame archival sequences independently replayed | **90 frames** |
| Committed V2 dual-signed chronological records | **15** |
| Independent public verifier-ticket signatures checked | **15** |
| Independent public signer-witness signatures checked | **15** |
| Source pins (CH32 heads and CH33 checkpoints/raw checkpoint bytes) independently matched | **15/15** |
| Parallel MPFR workers (same verifier UID only) | **4** |
| Wall-clock time for root-driven complete acceptance | **{data['elapsed_wall_seconds']} s** |
| Global-optimality certificates passing 0.05 gap threshold | **0/15** |

All original scientific uncertainty refusals, including the three zero-event ambiguity cases, remain unchanged. No synthetic mathematical benchmark replaces any original CH23 case.

## Adversarial and resilience evidence

- 15 isolated protocol/ledger unit tests passed, including altered ticket bodies, wrong verifier keys, replay/nonunique nonce, changed policy/checkpoint, noncanonical JSON, duplicate case, signer restart, false scientific GO, writable private-key modes and two partial-publication fault boundaries.
- One Linux root-operated live test verified that a running signer without a verifier service **does not publish a witness** and leaves the protected tip at genesis.
- One original-evidence public archive test verified the complete chain and deliberately inserted an unreachable revision, which was refused. These total **17/17 tests passed**.
- During integration, genuine OS UID isolation denied signer reads of verifier private key and source, verifier reads of signer private key, and direct writer/verifier access to each other's privileged sockets. The writer's attempted extra `attestation` field was rejected.
- A historical *research export-only* defect was caught: a one-case earlier witness from another temporary key had been left in the shared evidence export directory. The full live signer's actual protected ledger was unaffected. The orphaned export file was quarantined outside final evidence, the final public archive now contains exactly 15 signed revisions, the export harness refuses to merge different authorities, and the public auditor rejects orphan/extra revision files. The independent public 15-case audit passes after cleanup.
- A forged, replayed, differently pinned, disconnected or noncanonical verifier record is never grounds for signing. Post-revision/pre-HEAD and post-HEAD/pre-tip write-failure tests remain fail-closed and require explicit reconciliation.

## Independent public identity pins for this research run

- Witness signer Ed25519 public-key fingerprint SHA-256: `{data['public_signer_fingerprint']}`
- Mathematical verifier Ed25519 public-key fingerprint SHA-256: `{data['public_verifier_fingerprint']}`
- Exact frozen original input policy SHA-256: `{data['frozen_policy_sha256']}`
- Final V2 signed ledger tip SHA-256: `{data['trusted_tip_sha256']}`

The public verifier validates both Ed25519 chains, exact original source pins and generation continuity, but **does not itself repeat MPFR**. Fresh MPFR was performed separately in the signer-controlled integration request flow on verifier-owned processes. These pins must be independently retained to protect against replacement of the entire on-host signer store. Committing them to a Git repository is a reproducibility ledger, not equivalent to a separately governed off-host trust authority.

## Limits, residual risk, and next task

- UID separation is enforced against ordinary same-host unprivileged accounts. Root/kernel compromise, wrong deployment privileges or compromised Linux security policy can defeat it.
- The verifier's own private **verifier ticket key** remains under the mathematical verifier's UID. A compromised verifier can forge a scoped verifier ticket; it still cannot extract or wield the *separately held witness signer private key*. Further isolation of verifier execution from attestation-key issuance is the appropriate next hardening task if this threat is in scope.
- The witness signer itself, if compromised, can sign arbitrary V2 records; no independent second signer or off-host timestamp/transparency authority is deployed yet.
- The CH36 real kernel ENOSPC and intercepted fsync tests remain a distinct historical evidence set. CH37 adds refusal/rollback tests for the new dual-signature commit path; it **does not** claim new hardware power-cut or independent real EDQUOT verification.
- No production package, OS service installation, Windows/NTFS acceptance, Lu integration, or global-optimality conclusion is included.

**Final CH37 result: scoped Linux split-UID authority accepted; Cognitum scientific and production GO still withheld.**
'''
    (D/'Engineering_Report_CH_C14_37.md').write_text(text)
    print('CH37 report created, bytes',len(text.encode()))
if __name__=='__main__':main()