# Cognitum P47 — Linux worker-lifecycle evidence quality gate

**Date:** 2026-10-31  
**Implementation:** Cognitum-only, local development; GitHub is the repository and documentation record, not the primary development hub.

## Why this exists

The separate Cognitum P46 local checkpoint reported a Linux direct-worker parent-lifetime fix and launch-race/fault-matrix tests, with **764 passed, 1 skipped and 3 native policy tests**. Those figures come from the earlier development conversation; the P46 full-source archive is **not present in this checkout**, so P47 neither imports nor replaces its worker implementation. GitHub `main` is behind this checkpoint. The P46 source and its native evidence must be reconciled from the original archive before integration or certification.

P47 adds a separate *structural* receipt verifier. It fails closed on duplicate or contradictory probe records, absent required cases, unobserved success, unreaped workers, surviving descendants, invalid PIDs, source-digest mismatch, malformed or duplicate-key JSON and oversized inputs.

## Contract

The receipt is strict UTF-8 JSON with exactly `schema`, `platform`, `source_sha256`, `runner_id`, and `cases`. The schema is `cognitum.lifecycle.v1`, platform is `linux`, and source digest is lowercase hex SHA-256. Each case has exactly `id`, `outcome`, `observed`, `worker_pid`, `reaped`, and `live_descendant_pids`.

P47 requires **five** Linux probe IDs: `supervisor-death-idle`, `supervisor-death-launch-race`, `supervisor-death-midflight`, `cancel-with-descendants`, and `output-pipe-backpressure`. A pass requires one observed PASS for each, `reaped=true`, and an empty live-descendant list. A zero PID is accepted only for a launch-race case that prevented the worker from launching. Absent/failing/contradictory case records make the verdict FAIL. Wrong schema/source or malformed envelope makes it INVALID.

Run with:

```bash
python -m unittest discover -s tests -p 'test_lifecycle_evidence.py' -v
python tools/verify_lifecycle_evidence.py path/to/native-receipt.json --source-sha256 <64-hex-digit-sha256>
```

The verifier prints `PASS`, `FAIL`, or `INVALID` in JSON and exits nonzero unless structural PASS. **Do not feed its output into an automatic Lu authorization path.** A locally constructed JSON document can pass this *shape* check without ever launching a worker. Structural PASS is **not** native test execution, trustworthy observation, cryptographic provenance, sandbox enforcement, authorization, or Windows certification. The P46 original native runner must generate independently observed receipts and a trusted source provenance chain before qualification. This code never enables worker admission.

## Local test evidence

Python 3.13.5, Linux; standalone unit command: **19/19 passed**, and Python source compile check passed. These are synthetic structural tests, not a live Cognitum P46 execution or a transformer benchmark. No Lu files, repository, or runtime were modified.

## Remaining gates

1. Recover and verify the exact P46 full-source archive and its SHA-256; reconcile with any later local work before integrating a P47 receipt exporter.
2. Wire an independent Linux native probe runner to emit the strict receipt and include negative survivor/launch-race observations; run it against **actual P46 worker code**.
3. Obtain independent provenance and native process-isolation evidence; avoid equating receipt syntactic validity with authenticity or resource containment.
4. Keep Windows job/handle/ACL and Lu-native integration gates open. Continue controlled Cognitum ON/OFF model trials separately.
