# Cognitum P23c — HDC verified-association sidecar for P23b selective SSM

Date: 2026-11-02. Linux research prototype only. Lu and Windows unchanged. GitHub is the documentation/repository checkpoint, not the dev environment.

**Design:** The frozen trained P23b gated selective SSM remains the primary temporal estimator. The P23c sidecar uses a 2,048-bit SHAKE-derived HDC key index to *propose* matches to a narrow signed verified-association bank in SQLite. Each candidate must match exact identity and relation, be active, and pass HMAC integrity verification before being returned. Conflicting active objects produce `conflict`, not last-write-wins. HDC indexes can be rebuilt from the durable record. Recorded updates and retractions remain in an event history. The HMAC signer is assumed to be a trusted upstream authority; no proof of actual factual truth is supplied by this key.

**Integrated test:** A time-aligned 96-step sequence uses the real P23b checkpoint and per-timestep `model.step`; a verified wardrobe association arrives, a conflicting association arrives during occlusion, and an earlier association is retracted. HDC reads remain auxiliary; SSM numerical velocity outputs remain identical to running without this sidecar. This is **not** joint model training, integrated learned fusion, or better temporal RMSE.

**Focused + inherited tests:** 21 passed, two inherited optional result-fixture tests skipped. Test categories: signed ingestion, forged record refusal, 16–160-bit noisy HDC queries, excessive corruption abstention, false associations rejected by exact identity gate, conflict/retraction/event history, tampered record rejection, index reconstruction, SSM integration and occlusion.

**600-query audit** using 120 distinct signed associations at 0/64/128/160/256 flipped bits: 480 verified correct, 120 abstentions (256 flips exceeds the 160 threshold), 0 false factual assertions. HDC retrieval + exact verification median 0.2734 ms/query, vs SQLite direct exact lookup mean 0.0039 ms/query; not identical workloads, no HDC speed advantage. These are exact lexical-key lookups, **not semantic synonyms or natural unfamiliar-object queries**.

**Research PASS / production NO-GO:** Prototype demonstrates an HDC association bank coexisting with selective SSM memory without write authority. Still unverified: source truth, key provenance/rotation, time-scoped truth, rollback tampering, concurrency, security lifecycle, task-level improvement, joint fusion, robust semantic retrieval, false-accepted lookalike memories, and scale. P23b corrupted-sensor weakness persists.

**Reproduction:** Local ZIP `Cognitum_P23c_SSM_HDC_Verified_Association_Sidecar_2026-11-02.zip` SHA256 `a21500dd95e72280eee014325a7c7093cf97c896a8224fb5a9e4fa662fc71504`; manifest and independent extracted 21-pass / 2-skip replay verified. Contains P23c code, real P23b trained model/checkpoint, inherited tests and benchmark scripts. The tested source is an isolated overlay, **not merged into production**.

Next P23d: authenticated provenance/time-scoped revisions, realistic semantic-retrieval comparisons against SQLite/FTS/vector baselines, held-out task-level consistency tests across occlusion, adversarial index+record poisoning, multiprocess and recovery tests.
