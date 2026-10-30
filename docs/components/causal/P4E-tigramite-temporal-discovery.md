# Cognitum C14 P4E — Tigramite Temporal Causal Discovery Candidate

**Checkpoint date:** 2026-10-28  
**State:** Candidate adapter and typed contracts implemented; **genuine Tigramite 5.2.10.1 execution is NOT verified**; Windows/Lu host confinement NOT verified.  
**Parent:** C14 P4D source checkpoint. Parent archive must remain immutable.

## Scientific contract and assumptions

Tigramite 5.2.10.1 is pinned as an **optional, separately deployed** GPLv3 scientific runtime. It implements algorithms described in established literature:

- PCMCI / ParCorr (`run_pcmci(tau_min=1)`): time-lagged conditional-independence relationships. For this bounded adapter only lag>0 links are published. PCMCI result p-values use `fdr_method='fdr_bh'` (not equivalent to the selection `pc_alpha`).
- PCMCI+ / ParCorr (`run_pcmciplus(tau_min=0)`): lagged links and contemporaneous **partial** orientations. This adapter restricts output to the explicit mark vocabulary `-->`, `<--`, `o-o`, `x-x`, rejecting other marks instead of guessing. PCMCI+ `fdr_method='none'`: its p-values are **not** multiple-testing-corrected in this adapter.
- Max four observed variables, 500 rows, lag 1–3, 2 conditioning dimensions, one conditioning combination per step. These are **truncated algorithm settings** for a bounded reference candidate and can reduce discovery quality; they do not reproduce an unrestricted Tigramite analysis.
- ParCorr assumes continuous variables with linear relationships and Gaussian noise. Causal conclusions additionally depend on Markov/faithfulness, causal stationarity, adequate time resolution, and causal sufficiency/no relevant latent confounders. PCMCI+ contemporaneous orientations can be ambiguous even when assumptions hold.
- C14 P4C supplies exact timestamp admission. No missing-value imputation, timestamp snapping, silent resampling, automatic differencing, automatic stationarity certification, or inferred change-point corrections. Caller acknowledgement of stationarity is **not** evidence of it.
- A returned graph is a *statistical candidate*, never an independently proven physical causal graph. No effect estimates are produced. Graph edge frequencies or significance values are not posterior probabilities of causation.

## Protobuf and security interface

New versioned `proto/cognitum/causal/v1/temporal_discovery.proto`, with generated `cognitum/proto/causal_temporal_discovery_pb2.py`. Reuses **without changing** P4C `TemporalDiagnosticRequest` for timestamps, columns, sample bound, familywise threshold, and trace identity. `TemporalDiscoveryResult` describes a typed link set and explicit significance policy; proof/assumption-verified fields must remain false.

`causal_tigramite_backend.run_temporal_discovery_frame` requires all of: host authorization, explicit capability enabled, host-supplied worker policy enabled, host OS-isolation attestation, exact runtime version and SHA-256 of the Python executable and both worker source files. It launches one short-lived `python -I` process, validates Protobuf-only response, pins threads, enforces output size, and kills on timeout. **A Python subprocess, flags, source hashes, and the attestation *boolean* do not themselves implement or prove Windows Job Object security.** Only Lu's trusted host can supply and verify genuine OS security attestation. This code does not modify Lu or GitHub.

Receipt verification checks request digests, known endpoint marks, no duplicate or out-of-bounds edges, significance range, backend/version, result maturity, and forbidden claims. It is **not** independent statistical or causal verification. A malicious worker could forge plausible edges: the OS/process boundary, trusted provenance and independent synthetic comparisons are required for assurance.

All source/experimental backends are disabled unless specifically selected by Lu's trusted host. `TigramiteWorkerPolicy` is only an adapter policy shape; production authorization is still missing.

## Dependency and redistribution gate

Project page: https://pypi.org/project/tigramite/5.2.10.1/  
Documentation: https://jakobrunge.github.io/tigramite/  
Source/license: https://github.com/jakobrunge/tigramite  
PyPI wheel expected SHA-256 (metadata only, not downloaded): `1bba99ba05c3ba90bdc235b92e9d65d10b1744af73f9e0070c1d7204e6c81ddc`. Wheel is **not bundled** in this checkpoint.

Tigramite is GPLv3; before bundling/distributing it with Lu or Cognitum, independently review licensing, redistribution obligations, transitive dependency lock, offline wheel hashes, Windows CPython compatibility, provenance and binary trust. The presence of an optional extra is **not** a legal or security approval. The configured package source was unreachable (DNS failure) in this environment, and the wheel could not be downloaded for genuine execution.

## Verification done in this checkpoint

1. Unit tests: permission defaults, bogus source/hash/runtime pin, real unavailable dependency, supervised subprocess returning unavailable, synthetically **mocked** public Tigramite calls for both algorithms, graph shape, canonicalization, reciprocal contemporaneous endpoints, negative and malformed cases, timestamp rejection, forged claims/digests, P4D denial isolation.
2. Real legacy C14/C13 tests and all historical C14 smoke suites.
3. Independent `protoc` schema-to-binding wire shape validation.
4. No real third-party PCMCI/PCMCI+ result; the mocked API tests do **not** substitute for the genuine library tests. Two genuine runtime tests are explicitly skipped.

## Outstanding release gates

- Obtain known-hash Tigramite wheel in a pinned, isolated Linux test environment and verify that both `run_pcmci` and `run_pcmciplus` operate against the real installed API. **Then** repeat with synthetic lagged/intervention ground truth, independence controls, known latent confounding, irregular time sampling, and false discovery rates across repeated trials.
- Run Windows x86-64 sealed wheelhouse and native Job Object, process-tree kill, memory limit, restricted token, file/network fencing tests using Lu's actual supervisor. Never claim those tests from Linux mock attestation.
- Verify authenticated Lu Protobuf host admission, cancellation, diagnostic provenance and per-task revocation.
- Separate scientific calibration (precision, recall, false positives under assumptions) from reliability/security tests; register numerical tolerances, random seeds, dataset hashes and nonidentifiability cases before evaluation.
- Evaluate GPLv3 redistribution and packaging; optionally expose Tigramite as an independently installed research-only adapter rather than default bundled backend.
