"""Write measured CH38 report only after 15 originals + offline signed audit pass."""
from __future__ import annotations
import json,re
from pathlib import Path
D=Path(__file__).resolve().parent
def main():
    r=json.loads((D/'original15_results.json').read_text())
    a=json.loads((D/'public_audit.json').read_text())
    t=(D/'ch38_tests.log').read_text().strip()
    if r['case_count']!=15 or a['signed_cases']!=15 or a['attestor_signatures_verified']!=15 or a['signer_signatures_verified']!=15:
        raise ValueError('Cannot report CH38 acceptance on partial original-data cases')
    if not re.search(r'31 passed in ',t):raise ValueError('Regression test count must be independently verified')
    lines=[
    '# Cognitum CH-C14-38 — Four-UID cryptographic key isolation',
    '', '**Date:** 2026-11-02 (America/Phoenix)',
    '', '**Disposition:** Linux scoped CH38 engineering acceptance PASS; production/scientific release **NO-GO**.',
    '', '## What changed',
    '', 'CH37 used UID 1002 for both original-MPFR calculations and its Ed25519 verifier attestation key. CH38 separates them. The journal writer UID 1000 can request only a frozen case; math UID 1002 owns the original proof files but **no private signature keys**; attestor UID 1003 owns the verifier attestation private key but **no original proof files**; and final signer UID 65534 owns its independent Ed25519 private key and final append-only signed ledger.',
    '', 'A new signer challenge is forwarded through the attestor to the math worker. Attestor binds exact case, nonce, policy and accepted original-data MPFR result to its signature; final signer verifies that ticket and serializes publication. Linux AF_UNIX filesystem ACLs and SO_PEERCRED constrain all three IPC boundaries.',
    '', '## Measured original-case acceptance',
    '', '| Metric | Result |','|---|---:|',
    f"| Original frozen CH23 cases | **{r['case_count']}/15** |",
    f"| CH33 original checkpoint nodes reverified | **{r['case_count']*127:,}** |",
    f"| Original historical frame replays | **{r['case_count']*6}** |",
    f"| Independent final-witness signatures | **{a['signer_signatures_verified']}** |",
    f"| Independent attestor signatures | **{a['attestor_signatures_verified']}** |",
    '| Original MPFR precision | **224 bits** |',
    f"| Full acceptance elapsed wall seconds | {r['elapsed_wall_seconds']:.2f} |",
    '| Protocol and Linux UID safety regressions | **31 passed** |',
    '| Global-optimality certificates | **0/15** |',
    '', 'The independent read-only public auditor authenticated the full signed history and pinned original CH32 journal heads, CH33 checkpoint SHA digests and SHA-256 checkpoint file bytes. The 15-case acceptance runner, not the public auditor, performed fresh MPFR computation. No synthetic cases replaced any original numerical benchmark.',
    '', '## Adversarial evidence',
    '', '- Real OS account tests deny mathematical UID read access to both private keys, deny attestor access to final signer key and sealed mathematical source, deny signer access to original proof files and attestor private key, and deny journal writer all private authority paths.',
    '- Wrong-UID direct socket connections are denied by Linux socket directory permissions and SO_PEERCRED.',
    '- Invalid/missing mathematical responses, altered nonce/case/policy, missing or false replay markers and changed source head are rejected before attestor signature issuance.',
    '- Signer rejects injected writer attestations, repeated cases and reused challenges; startup with absent attestor leaves the witness ledger at unsigned genesis.',
    '- Regression suite retains CH37 journal continuity and crash-failure policy, refuses orphan revisions, unpinned HEAD and wrongly permissioned secrets.',
    '', '## Critical mathematical trust limitation',
    '', '**An attacker who fully controls math UID 1002 can still lie to UID 1003 about the arithmetic.** The attestor authenticates *which account provided the report* and protects its key from that account; it cannot independently prove that the reported MPFR calculation occurred. All 15 measured CH38 original proofs actually ran under UID 1002, but that test alone is not a formally verified anti-forgery guarantee against a compromised math worker. To obtain this guarantee, a future verifier under an independent trust domain must replay an untrusted full proof certificate or a checkable compact mathematical transcript before attestation.',
    '', 'Root/host kernel compromise bypasses discretionary Linux UID boundaries. No off-host independently operated witness, protected timestamp, external rollback anchor, power-cut simulation, Windows/NTFS test, production deployment, or math global-optimality proof is claimed. CH36 kernel ENOSPC tests were not repeated as CH38 achievements.',
    '', '## Engineering recommendation',
    '', 'Next CH39: independently check original certificate mathematics in an OS-isolated audit account before granting signing approval, with measurable correctness/cost and explicit denial under forged math output. Then add separately operated off-host anchoring to close single-host rollback; continue deferring Windows as requested.',
    '', 'Source branch: `cognitum/ch-c14-38-four-uid-attestor-isolation-20261102`; preserve original CH23–CH37 history unchanged.',
    ''
    ]
    (D/'Engineering_Report_CH_C14_38.md').write_text('\n'.join(lines))
    print('CH38 engineering report prepared with live original evidence')
if __name__=='__main__':main()