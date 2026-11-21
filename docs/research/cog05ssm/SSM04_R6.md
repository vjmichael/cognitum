# COG-05-SSM-04-R6 — authenticated, durable R5 streaming checkpoints

**2026-11-21 status: implemented as isolated research candidate; exact-source native Windows/Linux acceptance pending.** R5-R1 accepted mathematical source and test blobs remain unchanged. This work adds no installed or privileged execution authority.

## Recovery contract and bounded on-disk representation

New sidecar module: cognitum/research/ssm_stochastic_checkpoints.py.

- serialize_stream_checkpoint(engine, authentication_key=..., stream_id=..., model_context=..., revision=..., source_cursor=...) returns a **canonical, deterministic, versioned, HMAC-SHA256 signed UTF-8 JSON byte sequence**. Signing domain is independent of other project protocols. No pickle, code deserialization, dynamic imports, authentication key, unauthenticated timestamp, filesystem path or hidden environment state is included.
- restore_stream_checkpoint(blob, authentication_key=..., expected_stream_id=..., model_context=..., minimum_revision=..., expected_checkpoint_sha256=...) first checks size, strictly decodes JSON (no duplicate object keys or NaN), refuses other schema versions, verifies expected stream and externally supplied model-context hash, requires the trusted anti-rollback revision floor, validates original exact-checkpoint SHA-256 if externally anchored, and compares the HMAC in constant time **before reconstructing engine state**.
- The restored engine owns its own deep-copied NumPy arrays and is validated for bounded dimensions, exact Gaussian generator/noise-block structure, nonnegative rates, bounded clock/counters, consistent retained state indices, strictly increasing timestamps, correct missing/released counts, consistent current filter/posterior and adjacent conditioned-state pairs, and no expired pending state. No existing live stream is modified on failure.
- Snapshot includes model generator and joint process/sensor covariance rate with cross-noise, filtered mean/square root, exact timestamp and watermark, all counters, pending states and adjacent conditional pairs, retained-memory limits, and cumulative likelihood. **No released output history** is serialized or spuriously re-emitted.
- Checkpoint size capped at 4 MiB, pending state limit is inherited from R5 (1..256). The module does not relax R5 event-time bounds.
- atomic_write_checkpoint(absolute_path, bytes) uses exclusive same-directory temporary creation, restrictive file permissions, full write, file fsync, atomic replace and **POSIX directory fsync**. read_checkpoint rejects a symlink at the final path and refuses unbounded reads. The caller owns the trusted parent directory, exclusive-writer control and filesystem ACL. Python's portable Windows API lacks POSIX-style directory fsync; **Windows power-loss durability is not claimed** until actual native custody and interruption testing.

## Threat model and nonclaims

Authentication is not encryption; checkpoint state remains plaintext at rest. The secret HMAC key is provided by a **trusted caller/OS credential broker** and must never be embedded in a checkpoint or source file. The model_context byte string must be built by that caller from the **complete approved model specification including initial prior**. Caller must maintain an independently trusted monotonically increasing revision floor (and preferably exact checkpoint digest anchor) for anti-rollback protection. A saved checkpoint cannot itself prove it is the newest one. A source_cursor string is authenticated, but actual cursor authenticity and replay ordering require a separate durable input journal.

**Exactly-once external outputs, transactional input/ack handoff, authorization to the MEL, key custody and authenticated OS process identity are not implemented here.** Mathematical state continuation is deterministic only from a valid checkpoint and the same post-checkpoint integrated increment stream. For crash recovery, an external durable journal must atomically coordinate checkpoint commit, input acknowledgement, and output delivery; R6 deliberately refuses to invent that policy.

## R6 synthetic research checks

research_tests/ssm04r6/test_checkpoints.py supplies **22 cases** (17 cases, one parameterized for 6 seeded splits): authenticated deterministic canonical roundtrip, real R5 correlated irregular/missing-increment continuation across a checkpoint, watermarked and zero-duration restart, replay and model misbinding denial, tamper/HMAC refusal, noncanonical and duplicate-key strict JSON denial, independently signed malformed state refusal, backward-pair covariance and clock tamper refusal, signed source-cursor restoration, atomic file replacement and injected failure recovery, symlink denial, 4-MiB memory budget, long retained-window preservation, and 6 randomized deterministic interruptions. The suite runs against genuine R5 and original R3/R4 dependencies in the native batch.

The original accepted R5 numerical source and tests remain exact:
- cognitum/research/ssm_stochastic_streaming.py 731208b392d3a948ee7677c2e24f1117e2c8df79
- research_tests/ssm04r5/test_streaming.py 826e1a7402cf89ae5c8855cbe52fd8280617c73a

New exact R6 Git blobs:
- cognitum/research/ssm_stochastic_checkpoints.py 30773bfaf4871bf686df0690419e3244c380be03
- research_tests/ssm04r6/test_checkpoints.py 8532167cc41b80cc69424219881c1b58e1a1a101

## Native qualification plan

One branch-scoped exact-source workflow batch across Windows/Ubuntu Python 3.11/3.13 running unchanged original R3/R4/R5 suites plus R6 and earlier SSM tests. Original JUnit XML, exact Git head SHA, and 12 original source/test blob IDs are uploaded from each environment. A fifth independent job compares the original four JUnits, all per-platform hash receipts and scientific-scope denials. Only genuine failures authorize a reviewed consolidated source repair. After full acceptance retire the one-time push trigger without altering the qualified Python files.

**Next:** COG-05-SSM-04-R6-R1 — reconcile native qualification, independent evidence and refusal/recovery tests; then prepare protected broker/journal and installed MEL acceptance separately.
