# C08 HDC / C09 KAN P1 — optional first-party research adapters

Status: **research-only CPU P1**, no Lu integration, installer authorization, HDC memory ownership, user-secret access, model-advertised tools or supervised CE execution. Source and tests are inside the private Cognitum repository only after the relevant PR merges.

## Provenance

Original user-owned K4 integrated archive: `Zog_Zoo_HDC_KAN_K4_Integrated_2026-10-25.zip` SHA-256 `1a054696c26e5350ae93f7150f6846bae973f6ff1aa0934fde92f264dba5a229`. Original user-owned optional depth overlay: SHA-256 `fc2809aa8bd8a681edf67c55a65d8b32ddcfca312cdc70104e27a63db8709a64`. Source was inspected for BSC and portable KAN behavior. `cognitum/research/kan_portable.py` preserves the original `zogzoo_kan/portable.py` byte-for-byte (SHA-256 `450db99cc83431455bc03a2f962186cc2f2f31856acda9072d71dc5c86676348`). The entire old research archive and optional depth overlay were **not** imported.

## C08 — BSC candidates

`cognitum.research.hdc_optional.query` implements the original BSC role/entity XOR binding concept as a deterministic 256-bit SHA-256-derived bipolar/XOR representation. Accepts at most 32 records and returns at most eight ordered *candidate IDs* and Hamming distances. The index and canonical source snapshot IDs must match; stale revisions, duplicate IDs, unknown fields and malformed Protobuf are denied.

It does not fetch canonical records, prove the candidate relation, authenticate the snapshot string, check user permissions or defeat a strong exact graph/BM25 baseline. It is an intentionally tiny, auditable research adapter, not a replacement for Lu's ANSF+SQLite or the full archived HDC model suite. Before any model exposure, the Lu host must reauthorize and recheck each source ID.

## C09 — pinned portable KAN inference

`cognitum.research.kan_optional.predict` loads a caller-supplied, SHA-256-pinned, size-limited **K4 NumPy `.npz`** checkpoint into the archived portable KAN CPU inference implementation. The research policy defaults to disabled. Checkpoint member names, count, uncompressed size, layer count, architecture, dimensions, finite values and the feature domain are bounded. A missing/mismatched digest, unexpected checkpoint field, malformed request, non-finite value, or out-of-domain input is rejected. No model training, network, pickle deserialization, hidden `eval`, learned update or optional depth module is enabled.

The output is explicitly approximate, not uncertainty-calibrated, not physically proven, and not authorized by Lu. A caller-supplied digest is **integrity only**; it does not establish external model identity or consent.

Run: `python -m pytest -q tests/test_research_optional.py` with Protobuf and NumPy installed. This is a first functional adapter slice; the full portfolio still requires host-compatible typed registration, deletion/revision guards, real checkpoint provenance, independent held-out datasets, training/OOD studies and optional depth testing. Improvement over conventional algorithms is **not** a prerequisite for working as transformer augmentation.
