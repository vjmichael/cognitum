# C08/C09 P2 — Ephemeral HDC invalidation and signed KAN metadata

**Scope:** Optional research augmentation only. Lu has **not** approved or registered these capabilities. There is no end-to-end model trial, real publisher identity, licensed data or OS sandbox certificate.

## C08 — Derived-index lifecycle

`EphemeralDerivedIndex` holds a fixed, host-supplied index snapshot ID and up to 32 bounded `(candidate_id, role, entity)` records. Query delivery of experimental HDC candidate IDs occurs while an in-memory lock is held against invalidation. Full invalidation is required before installing a replacement revision and is exposed for edit, retract, delete, scope revoke, restore and source replacement. This reference does **not** subscribe to real Lu ANSF mutations, persist invalidation history, perform actual source ACL checks, or return authorized source excerpts. The embedding host MUST apply scope filtering and durable revision checks; candidates themselves confer no access rights.

## C09 — Signed metadata

The new `KanCheckpointApproval` message binds a model name, exact checkpoint digest, training-split digest, signer ID and feature units. An injected trusted-key policy verifies an Ed25519 signature over domain-separated canonical Protobuf bytes before the existing bounded NumPy K4 inference runs. Signer, model and training-split identifiers are checked against the *trusted host-injected policy*, not taken from the model. A revocation flag rejects the signer. Checkpoint archive validation, declared feature bounds and default-off research policy remain in force.

Signatures prove that the holder of a private key signed these **claims**. They do **not** authenticate an external publisher, model training data/license, calibration, timestamps, scientific accuracy or third-party expertise. Trust policy is in-memory, caller-injected and not a production persisted trust root. Do not allow an untrusted model to construct or replace it. The raw low-level KAN predictor is not a production tool interface.

## P2 tests and next gates

`python -m pytest -q tests/test_research_optional.py tests/test_c08_index_lifecycle.py tests/test_c09_signed_approval.py` validates correct opt-in behavior, stale source refusal, invalidation after deletion or scope revocation, duplicate IDs, mismatched feature units, corrupted signature, revoked key, changed split, unknown wire fields and checkpoint tampering. Next: host-owned canonical change feed/durable index generation; authenticated publisher trust and rotation; signed train/test manifests with actual rights; scientific robustness tests; real Lu model/worker invocation with permission and deletion checks. Claiming HDC superiority or KAN accuracy is outside this P2 gate.
