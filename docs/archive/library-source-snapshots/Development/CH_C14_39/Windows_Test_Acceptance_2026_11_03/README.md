# CH39 Windows read-only acceptance — 2026-11-03

Two user-executed Windows test kits produced **PASS** outcomes against the exact same frozen CH39 reproduction archive.

| Check | Original kit v1 | Corrected kit v3 |
|---|---|---|
| Audit status | PASS | PASS |
| Original archive SHA-256 | PASS | PASS |
| Archived SHA-256 manifests | 1,099/1,099 | 1,099/1,099 |
| Original CH23 source pins | 15/15 | 15/15 |
| Ed25519 attestor signatures | 15/15 | 15/15 |
| Ed25519 final signer signatures | 15/15 | 15/15 |
| Python / cryptography | 3.14.6 / 50.0.2 | 3.14.6 / 50.0.2 |
| Fresh MPFR | Not requested | Not requested |

**Exact machine-generated public audit JSON byte equality**: yes. Both audit JSON files have SHA-256 `c1e515be363659f8237990c3330803aa4c565ad9fc47d2cd1f255fe23150c3f3`.

- Frozen CH39 archive SHA-256: `9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.
- Public witness terminal tip: `112980038c992461c0eaf43c2d3f066191e4c7404b058ba434c1ba1352af68c5`.
- v1 run: `2026-11-03T07:24:27.6888747-07:00`. v1 summary reports `PASS_PUBLIC_WINDOWS_AUDIT`.
- v3 run: `2026-11-03T07:36:43.152210-07:00`. v3 summary reports `PASS_PUBLIC_WINDOWS_AUDIT`, process exit `0`.
- The interim v2 failed to launch because a stale `py` registration selected a removed LM Studio Python. It did not execute the evidence auditor and is **not** a Cognitum proof failure.
- These are **two executions of the same public-audit mathematics and cryptographic verifier**, not two independently implemented cryptographic auditors.

**Scope**: only the read-only Windows public-evidence gate is accepted. A fresh native Windows MPFR verification, Linux five-UID separation and global-optimality certification were not established by these runs. The mathematical scientific disposition remains `NO_GO` (0/15 global-optimality certificates).

## Provenance/privacy

The redacted JSON artifact provides SHA-256 hashes of each of the six user-supplied log/JSON files for later reconciliation. Raw logs and Windows account paths have **not** been added to the public repository. Do not mistake archival SHA-256 matches for independent proof recomputation.