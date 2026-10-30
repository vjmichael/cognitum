# C15 — GitHub source checkpoint reconciliation gate (portable)

Date: 2026-10-29 / 2026-10-30 UTC. Scope: Cognitum only. Lu remains unchanged.

## Purpose

The experimental C15 T3 Windows VM and T4 P0–P13B work exists in local checkpoint ZIP archives, while GitHub \`main\` had the older October 27 source tree. The T3/T4 milestone ledger was merged in PR #17, but **documentation alone does not constitute source synchronization**. An unconditional replacement from a 933-entry ZIP would also import generated evidence, caches and checkpoint metadata.

## New source tooling

- \`tools/c15_checkpoint_diff.py\`: bytewise SHA-256 inventory and diff of two explicitly supplied ZIP checkpoints; reports added, changed, removed and unchanged paths, with a conservative \`source_candidate\` vs generated/research-evidence classification.
- \`tests/test_c15_checkpoint_diff.py\`: synthetic archive tests for modifications, path traversal (including drive paths and backslashes), duplicate entries, Unix symlink entries, oversized files and preservation of source/evidence distinctions.
- Rejects unsafe inputs instead of permitting extraction or silent overwrites. CLI output files are created with exclusive-open mode.
- Does not mutate either archive, GitHub, Cognitum's existing source, or Lu.

Run:

\`\`\`powershell
python tools/c15_checkpoint_diff.py PREVIOUS_CHECKPOINT.zip CURRENT_CHECKPOINT.zip --out new-diff-report.json
\`\`\`

## Verified against real local checkpoints

P13 predecessor \`Cognitum_C15_T4_P11_P13_Timestamp_Uncertainty_Windows_Ready_2026-10-29.zip\` versus P13B \`Cognitum_C15_T4_P13B_Host_Evidence_Consistency_2026-10-29.zip\`:

- 928 entries before; 933 entries after.
- **927 unchanged; five added; one changed; zero removed.**
- New: P13B host evidence verifier, test, accompanying documentation and backlog. Modified: checkpoint README.
- Local combined regression: **42 passed** (source-reconciliation tests plus P13B evidence verifier and P13 runner contract tests). These are portable Linux runs; not Windows execution.
- The local machine-generated report is \`Cognitum_C15_GitHub_Source_Reconciliation_P13_to_P13B.json\` and is intentionally not a public test fixture.

## Important trust boundaries

**Not a GitHub tree comparison:** \`github_repository_compared=false\`. A local ZIP-to-ZIP delta cannot prove what GitHub currently contains; compare against the latest GitHub HEAD separately and review every conflict before bulk source import. \`github_upload_approved=false\`. File categorization does not constitute security review.

**Not a scientific or platform certification:** It does not authenticate real Windows execution, sealed host evidence, authentic measurements, timestamps, human reviewers, or OS isolation.

## Remaining repository work

1. Import the C15 implementation in reviewed, dependency-complete batches rather than copying the full ZIP. Include tested source, tests, matching \`.proto\`/generated bindings and CI updates.
2. Reconcile against GitHub \`main\` HEAD, which may contain later independent changes; never force-push or overwrite unrelated files.
3. Run GitHub CI on Linux/Windows after source review and preserve negative-test results.
4. P13 Windows-native execution and external P11/P12 scientific evidence are independently open; do not promote synthetic tests to accepted real-world results.
