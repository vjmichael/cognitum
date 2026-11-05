# Cognitum C01–C19 — repository-wide regression and integration closeout

**Audit date:** 2026-11-04. **Baseline audited:** `main` at
`3c7614634ed210580644708be304a14702ec5325`.

**Decision: NOT RELEASE-READY; source work spans multiple open PRs.**
All C01–C19 portfolio areas have some implementation or design history, but
that does not establish that all 19 practical implementations coexist in
one tested artifact. This is a concrete engineering closeout inventory and
an admission gate, not a claim that the repository or Lu DLC is finished.

## 1. What has actually been verified

- **Main branch:** Python regression at the audited exact head **passed**
  (Actions run [41899272946](https://github.com/vjmichael/cognitum/actions/runs/41899272946)).
  Its maintained C14 causal-library and C12 NetworkX planning acceptance
  also passed at that head. C12 PR #69 and bounded C14 PR #63 are merged.
- **C01–C05 foundational support** is present on main (typed core
  capability contracts, bounded Protobuf/worker boundaries, evaluation,
  collector receipts and scientific math), but Lu installed-host
  authorization/worker lifecycle acceptance is not independently certified
  by this inventory.
- **C06/C07 host-owned reference PR #77:** dedicated C06/C07 and shared
  regression checks **passed** at `ccc2bd9b3e187d41e2d92c87e3f4e5e721df67e3`,
  but GitHub reports the PR's mergeability as `dirty` relative to main.
  Separate experimental draft PR #78 had 29/30 checks pass per tested
  module, with a flawed literal FTS5 query test: the token `OR` really
  occurs in a source document and is legitimately searchable. Test repair
  committed; no exact-new-head pass yet.
- **C08/C09 optional research PR #79:** C08 HDC candidate-verification
  and shared regression **passed** at
  `0b173cf538c4ce4fb74e084ee20dc38d2335f84c`. PR remains a
  **draft** and must not be used as a canonical Lu memory or
  automatically admitted production capability.
- **C10 formal proofs PR #67:** unresolved. Native cvc5/Carcara attempted
  proof verification; Carcara rejected a proof containing an unsupported
  `all_simplify` rule. No independent UNSAT certification. Another CI
  failure came from incorrectly escaped synthetic `unsat\\n` fixtures;
  corrected on branch, but actual native proof compatibility remains open.
- **C11 OR-Tools/HiGHS PR #68:** previous test expected a feasible solution
  to be rejected. The test was corrected; independent optimizer optimality
  certification has *not* thereby been established. Exact-head CI has no
  verified success and the PR conflicts with main.
- **C12 planning PR #69:** **merged**, existing CI passed.
- **C13 Bayesian PR #70:** dedicated genuine SciPy matrix previously
  passed; generic regression lacked the optional statistics dependency.
  Workflow corrected, but no exact-head acceptance is established.
- **C14 PR #63:** bounded maintained causal-library integration **merged**;
  open-ended C14 research remains deferred by project decision.
- **C15 tracking PR #71:** core spatial acceptance passed on prior head.
  Earlier real MOT17-02-FRCNN 299-frame detections comparison showed
  HOTA/MOTA/IDF1 metrics from the `trackers eval` backend, but this is
  **not yet independently confirmed** by the separately pinned official
  TrackEval. Native official evaluator encountered seqmap CLI mismatch
  and later a legacy `np.float` alias; compatibility patch was committed.
  Official TrackEval run at latest head was still **queued** when checked.
  Do not label previous metrics as official TrackEval/leaderboard evidence.
- **C16 physics PR #72:** four-method native SciPy ODE acceptance passed
  on a previous exact head on Windows/Linux Python 3.11/3.13. Shared
  Windows failures were in Linux-cgroup host-recovery tests. Follow-up
  documentation head remains separately unverified, with merge conflict.
- **C17 temporal PR #73:** Windows native acceptance passed at the prior
  head; three Linux assertions reflected mistaken zero-horizon and HMM
  confidence-alert assumptions. Test fixes committed but require new-head
  acceptance. Shared Windows errors belong to Linux-only host-recovery.
- **C18 adaptation PR #74:** after fixing malformed Python escaped
  newlines, **native acceptance passed at current head**
  `b4734bdc3c4ef7848b513c1d3cc1121353d71c03`
  (Actions run [41906721112](https://github.com/vjmichael/cognitum/actions/runs/41906721112)).
  It is not yet merged, and a combined-tree integration pass is still
  required.
- **C19 topology PR #75:** prior Windows native matrix passed; Linux
  rejected valid duplicate-point zero-lifetime H0 classes. Bounded
  correction committed, but the repaired native matrix at
  `15dbe8ab32f11ddde6a5d1735da6619eee72c858` was **queued**.

## 2. Integration blockers by priority

1. **One-tree source convergence (P0).** Merge candidates only after
   resolving GitHub-reported conflicts and retesting at merged/rebased
   exact SHAs. GitHub reports `dirty` for most practical component
   PRs against current `main`, including #67, #68, #70–#75, and #77.
   Do not force merge unrelated source trees. C06/C07 #77 and #78,
   and C08/C09 earlier research branches versus #79, need intentional
   source reconciliation to avoid multiple competing implementations.
2. **Shared regression (P0).** `tools/run_crossplatform_regression.py`
   already excludes precisely five Linux kernel-specific test modules
   from Windows and labels them `NOT_RUN_ON_WINDOWS` rather than
   claiming a pass. Main Python regression passed at the audited SHA.
   Re-run combined-tree 3.11/3.13 Windows/Linux after every integration
   batch, including optional native library dependencies and Protobuf
   descriptor parity. Do not remove fail-closed cgroup checks.
3. **C10 proof format (P0).** cvc5's native emitted Alethe proof must
   genuinely be checkable by a compatible independently pinned Carcara.
   The `all_simplify` rejection is not a reason to accept unknown rules.
4. **Real-data/independent evidence (P1).** Obtain independently
   computed official C15 HOTA/MOTA/IDF1 for both C15 and ByteTrack from
   identical MOT17 detections. C19 native duplicate-point matrix
   must pass; C11 optimization and C13 calibration require current-head
   acceptance; C16/C17 need rebased exact-head tests.
5. **Lu DLC end-to-end gate (P0 for shipping).** In a separately built
   *installed* Windows Lu and Linux test host: native worker lifecycle,
   explicit per-turn authorization, Protobuf request/response parity,
   persisted effects/rollback, real cancellation, process-tree cleanup,
   restart recovery and model-authored request boundary. No
   model-selected executable, direct untrusted SQL, hidden state as
   canonical memory, or headless synthetic success can stand in for
   this proof. The Lu Workspace DLC interface is deferred until its
   separate host design is approved; do not silently merge PR #61.

## 3. Admission sequence

- **Batch A — foundation and host-owned truth:** reconcile C05 #66
  and C06/C07 #77/#78 with main. Keep Lu ANSF/SQLite as canonical owner.
- **Batch B — independently bounded reasoning:** C10 #67 (after checker
  compatibility), C11 #68, C13 #70. C12 remains merged.
- **Batch C — spatial/numerical/temporal:** C15 #71 (independent TrackEval),
  C16 #72, C17 #73. C14 remains frozen/merged.
- **Batch D — adaptive and geometric:** C18 #74, C19 #75.
- **Research overlay:** C08/C09 PR #79 only after provenance, license,
  compatibility and optional distribution review; keep experiments inert.
- **Integrated release gate:** build a *single merged candidate* and run
  Windows/Linux Python 3.11/3.13 baseline and optional native checks,
  Protobuf parity, genuine benchmark evidence, OS lifecycle faults and
  Lu installed-app E2E. No automatic release until all relevant gates pass.

## 4. What this branch contributes

- `tools/cognitum_integration_source_gate.py` inventories all 19
  expected component entrypoint paths within **one checked-out tree**.
  It fails `--require-sources` while any are missing, and never marks
  release readiness true solely on source presence.
- `tests/test_integration_source_gate.py` verifies incomplete trees,
  fake-complete source trees, and symlinks cannot be treated as
  sufficient release evidence.
- `.github/workflows/cognitum-integration-closeout.yml` launches a
  four-way Windows/Linux Python 3.11/3.13 combined-tree regression and
  the strict source convergence gate, preserving JSON evidence artifacts
  even when the gate fails.
- The gate is deliberately **expected to fail on current main** because
  C06/C07, C10/C11, C13, and C15–C19 practical implementations have
  not been merged. This is a precise unresolved gap, not a CI nuisance
  to silence.
- It does **not** reclassify all source-present components as verified;
  independent native-library and Lu host demonstrations remain external
  to this simple source inventory and required before release.

## 5. Decision

**Status: Engineering portfolio implemented in separate branches;
repository-wide production integration NOT CLOSED.** Main baseline is
green, but most recent specialist branches are not in the same build.
Proceed with staged conflict reconciliation and exact-head acceptance.
No new open-ended HDC/KAN/SSM or C14 research required to close the
defined v1 engineering scope. HDC/KAN/SSM can be revisited before
C14 research, as previously decided.
