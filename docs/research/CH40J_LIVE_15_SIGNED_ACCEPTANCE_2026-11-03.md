# CH40-J actual five-UID live research acceptance — 2026-11-03

Research gate: PASS_RESEARCH_SIGNED_CHAIN_ONLY. Scientific release: NO_GO.

The CH40-J Linux runner completed all 15 frozen original CH23 research cases with bounded workers=2 and numeric UIDs: writer 1000, math 1002, checker 1004, attestor 1003, signer 65534. One persistent signer identity issued 15 fresh Ed25519 signer signatures alongside 15 attestor signatures. The independent read-only CH40H public auditor verified all 15 case-specific cap receipts and 1,905 claimed capped nodes. That auditor verifies signed provenance and receipt constraints, but does not reexecute the live MPFR mathematical calculations.

Final status PASS_15_SIGNED: completed=15, remaining=[], errors={}.
Public audit CH40H-PUBLIC-AUDIT-V1: PASS_RESEARCH_SIGNED_CHAIN_ONLY; 15 signer signatures, 15 attestor signatures, 15 receipt checks.
Final terminal tip SHA-256: 941cba5e959b1147a7e3665b966ba97dca37446cf4c366b3efc44f836abda3b3
Signer public-key SHA-256: 887d038b41294787ea0d5b3c0024a740d467f95c7c05d631e1f95ac4d60a5ba7
Attestor public-key SHA-256: 05bb5b101ea1d82b4a384edade3678905e5e4e730a84f59910c45cd93c872b9f
Frozen policy SHA-256: 20114fd1eee3121467346eb4a00dc9d2577a1eb8ec612f24e296fdbc96a7345b
Historical original source ZIP SHA-256: 9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b

Public evidence ZIP filename: Cognitum_CH40J_Fresh_All15_Signed_Public_Evidence_2026-11-03.zip
ZIP size: 5,982,109 bytes.
ZIP SHA-256: 203c039ea0476f03d1b21a19a8248c95cddc1531359778c1d380ea9576f75ec5
This ZIP is available as a ChatGPT conversation artifact, not stored in the Git repository. It contains all 15 signed revisions, the public keys, frozen policy, historical source archive, audit scripts, status, execution log and manifest, but no private signing keys.

On a clean extraction, the standalone public auditor passed using the recorded fingerprints and terminal tip. Deliberate false-tip and modified-signed-record attacks were rejected.

Trust caveat: signing-key fingerprints and terminal tip were observed in the run itself and are recorded by this GitHub commit, rather than separately authenticated by an off-host third party. This is not a retroactively independent trust anchor.

Research only. No unrestricted global optimality or closure of the finite-root 0.05 gap is certified. Hardware power-loss fsync correctness and fully independent key provenance remain open. Scientific release remains NO_GO.
