# C14 P2B G1 — Offline supply-chain gate, resource footprint, and remaining native acceptance

**Date:** 2026-10-27.  **Status:** Source gate candidate, not a production-ready DoWhy integration.
**Parent checkpoint:** `Cognitum_C14_P2B_Pinned_DoWhy_Worker_Candidate_2026-10-27.zip` (`sha256 f2c339a41e257a0abe564e71af3d53dbc7903025118be4a0439b1eed7fe983e4`).

## A. Verified source footprint — not installed binary size

Parent checkpoint ZIP: 946,552 bytes; 345 ZIP files including the checkpoint manifest; uncompressed aggregate source/documentation/tests: 2,659,899 bytes (345 ZIP file entries including manifest). Breakdown of archived *source* (excluding generated `CHECKPOINT_INFO.json`):

| Category | Files | Uncompressed bytes | Compressed bytes |
|---|---:|---:|---:|
| Cognitum Python package `cognitum/` | 94 | 743,227 | 229,892 |
| Protobuf sources `proto/` | 30 | 71,533 | 28,556 |
| Tests | 63 | 576,711 | 143,633 |
| Documentation | 110 | 938,991 | 391,725 |
| Lu integration candidate source | 11 | 104,236 | 32,929 |
| Tools | 26 | 67,540 | 26,428 |
| Other metadata/project source | 11 | 157,661 | 41,643 |

**Runtime footprint is not equivalent to archive size.** This checkpoint is Python source, not a native compiled ARM/Windows binary and includes no transformer weights. Mandatory Python/Protobuf/NetworkX dependencies and optional scientific stacks dominate installation. A desktop Linux Python 3.13.5 environment reported Python-alone ~95,384 kB resident; Python with `cognitum.causal` imported ~108,312 kB (process baseline already unusually high due to site startup); delta ~12.9 MB on this machine only. Not a supported lower-bound or Windows measurement.

Examples of installed distribution disk sizes *in this specific Linux environment*, not estimates of Windows wheels: NumPy 68.9 MB, SciPy 139.2 MB, pandas 70.7 MB, scikit-learn 44.5 MB, statsmodels 50.2 MB, networkx 15.5 MB. Total across those six installed distributions approximately 389 MB. These are package-file sums, not deduplicated RAM use. They exclude interpreter and further DoWhy dependencies, and cannot be extrapolated directly to Windows. The pinned DoWhy 0.14 universal wheel is 403,110 bytes **before dependencies** (PyPI release metadata).

### Resource-tier architecture (design proposal, NOT measured deployment guarantees)

- **Lite core:** typed contracts, basic exact arithmetic, state proposal/validation, bounded finite causal reference. No ML framework or third-party scientific stack should be required for operations that can be implemented without them. Some current C14 causal graph routines do require NetworkX and Protobuf; packaging split/alternative graph implementation is pending.
- **Scientific:** SciPy/NumPy, computational numeric solvers and selected numerical backends loaded only on demand.
- **Causal mature:** optional DoWhy worker in an isolated pinned environment, never required for ordinary Lu/Math/C03 startup.
- **Research:** neural/temporal/Bayesian causal adapters and GPU-capable backends, strictly opt-in with memory and GPU budgets.
- **Microcontroller/very low RAM:** not supported by this Python distribution; requires separate compiled implementations and constrained-algorithm validation, not merely stripping documentation.

## B. New deterministic wheelhouse gate

`tools/c14_p2b_wheelhouse_gate.py` is an **offline verifier** intended to run in a trusted installer/build pipeline. It accepts a separately approved JSON lock and a wheelhouse directory. Target fixed to CPython 3.13 Windows x86-64 for this stage. It validates SHA-256 hashes, wheel filename/metadata identity, basic wheel compatibility tags, each wheel archive's member paths, duplicate names, unexpected files, and `Requires-Dist` dependency closure including version constraints and target-specific markers (ordinary non-extra requirements). The lock must include DoWhy==0.14.

Example lock *shape* (illustrative only; cannot pass as written):

```json
{
  "schema_version": 1,
  "target": {"python_version": "3.13", "platform": "win_amd64"},
  "packages": [
    {"filename": "dowhy-0.14-py3-none-any.whl", "sha256": "<real 64-character SHA-256>"}
  ]
}
```

Run with `PYTHONPATH=. python tools/c14_p2b_wheelhouse_gate.py --lock LOCK.json --wheels WHEELHOUSE`; exit 0 only for successful **syntactic/closure** validation. The lock must be endorsed and distributed by the trusted host/installer, independently of the wheel supplier. **A valid wheelhouse gate is not permission to run untrusted code** and is not yet connected to worker-launch admission; Windows DLL/VC runtime/ABI imports and runtime loading remain separately testable requirements. Test fixtures deliberately use synthetic wheels and cannot qualify real DoWhy.

## C. Remaining gates (explicitly open)

| Gate | Pass condition | Current status |
|---|---|---|
| DoWhy real API | DoWhy 0.14 and all dependencies installed in reviewed isolated environment; typed backdoor + placebo synthetic-golden tests pass | **Open**: DoWhy absent; positive tests skipped |
| Win64 offline wheelhouse | Full approved wheel hashes + dependency closure + licenses/ABI vetting | **Open**: verifier implemented, no approved wheelhouse or lock |
| Windows process containment | Lu-authenticated WorkerCall; Job Object kill-on-close and tree termination; CPU/memory cap, FS/network denial, cross-user/secret access negative tests | **Open**: no Windows Lu host test |
| Worker supply-chain admission | Host supplies pinned executable, code, wheelhouse and build key; no model-provided bypass flag | **Open**: source SHA gate exists but `host_isolation_attested` flag is a development placeholder |
| Native Protobuf compatibility | C02/C03/Lu API and ACL integration with real Windows host | **Open**: standalone protobuf descriptors match, but native host integration absent |
| Causal validity | Real benchmark data, independent causal assumptions review, multiseed sensitivity, no false positive claims | **Open**: only synthetic/unit fixtures |

## D. Verification evidence and safety boundary

This G1 checkpoint adds an offline wheelhouse checker and negative tests, plus positive DoWhy API fixture tests that **skip when dependency unavailable**. It does not alter the P1/P2A/P2B worker logic or Protobuf fields, and leaves the adapter default disabled. The offline verifier is a necessary pre-install guard, not a production OS sandbox or cryptographic trust anchor. Neither Python `host_authorized=True` nor `host_isolation_attested=True` prove Lu authorization.

When moving to a real Windows x86-64 target: stage an externally approved wheel lock with provenance and licensing review, run the verifier; install into an offline isolated environment, then execute positive tests and memory/CPU measurements; finally perform Lu-host Job Object containment/denial/revocation tests. Only Lu can sign/attest acceptance. Record results separately from synthetic tests.
