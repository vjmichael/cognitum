"""Format verified CH30 differential numerical replay measurements."""
import json,hashlib,statistics
from pathlib import Path
D=Path(__file__).resolve().parent
b=json.loads((D/'benchmark_results.json').read_text());rows=b['per_case']
def f(x):return f'{x:.2f}'
ratio=[r['legacy_cold_127_cpu_seconds']/r['incremental_127_cpu_seconds'] for r in rows]
lines=[
'# Cognitum CH-C14-30 — Incremental MPFR proof verification',
'', '**Date:** 2026-11-02 · **Scope:** Original CH23 finite-box interval proof engineering. **C14/G25 scientific promotion: NO-GO.**',
'', '## Work completed',
'', 'Replaced repeated full 224-bit MPFR verification of unchanged CH29 ancestor bounds with a safe **in-process incremental certificate session**. The initial 63-node proof is fully replayed independently; a 127-node extension may reuse the same 63 exact MPFR cap objects only if the verified nodes are unchanged and every new split is geometrically validated. All 64 new node bounds are recomputed at 224-bit MPFR, the complete partition is traversed, incumbent feasibility and objective floor are checked again, and the 0.05 objective-gap decision is independently reconstructed.',
'', 'There is **no external checkpoint restore**: restarting the verifier requires cold full replay. The cache cannot be deserialized or treated as standalone proof. A modified tree, unknown bound mode, changed input, proof parameter or failed claim is rejected without updating the trusted session.',
'', '## Frozen original-data results',
'',f"- Original CH23 cases: **{b['cohort_size']}/15**, including three historical zero-event ambiguity refusals.",
 f"- Proof-decision and gap agreement with original CH29 full verifier: **{b['cohort_size']}/{b['cohort_size']}**.",
 f"- 224-bit MPFR caps reused in second-stage replay: **{b['total_reused_mpfr_caps']}**; newly computed: **{b['total_fresh_mpfr_caps']}**.",
 f"- All original 0.05-gap global certificates: **{b['global_certificates']}**; all remain unresolved.",
 f"- Frozen CH30 protocol SHA256: `{b['protocol_sha256']}`.",
'', '### Per-case verification CPU (seconds; original archived fixtures, no substitutes)',
'', '| Original CH23 case | Cold 63 | Incremental 127 | CH29 cold 127 | Incremental speedup |',
 '|---|---:|---:|---:|---:|',
]
for r in rows:
 lines.append(f"| `{r['case_id']}` | {f(r['cold_63_cpu_seconds'])} | {f(r['incremental_127_cpu_seconds'])} | {f(r['legacy_cold_127_cpu_seconds'])} | {r['legacy_cold_127_cpu_seconds']/r['incremental_127_cpu_seconds']:.2f}× |")
lines+=['', '| Aggregate | **'+f(b['total_cold_63_cpu_seconds'])+'** | **'+f(b['total_incremental_127_cpu_seconds'])+'** | **'+f(b['total_legacy_cold_127_cpu_seconds'])+'** | **'+f(b['speedup_incremental_step_vs_cold_127'])+'×** |',
'', f"**Measured aggregate saving on the incremental step:** {(1-b['total_incremental_127_cpu_seconds']/b['total_legacy_cold_127_cpu_seconds'])*100:.1f}%. **Measured saving for verifying both certificates together:** {b['reduction_for_two_certificates']*100:.1f}%. The latter includes the required full verification of the 63-node checkpoint; no cold-start speedup is claimed.",
'', '## Security and numerical soundness',
'', '- `verifier30.py` accepts CH29 certificates as-is. First verification reconstructs every ancestor cap from the proven mathematical bound methods at 224-bit MPFR. Subsequent certificates are bound by SHA-256 to all unchanged proof-relevant inputs and protocol fields; the old proof-relevant node data are compared exactly.',
 '- A previous leaf may become an internal node only with a validated binary split. New leaves require fresh outward-rounded bound evaluation. A fresh feasible incumbent is checked for every new certificate, and all leaf caps are used in a fresh gap decision.',
 '- 15/15 targeted adversarial and functional tests passed (including forged global certification, changed partitions, changed duals and precision, and mutation after prior successful verification).',
 '- A failed incremental replay cannot replace the previously verified state. No disk cache, signature delegation or untrusted checkpoint import path exists.',
 '- The original CH29 verifier is retained for cold differential replay; the CH30 verifier still shares underlying MPFR logistic/Fisher interval code and is not an external formally certified proof assistant.',
'', '## Evidence and scientific limits',
'', '- Original CH23 source/deterministic data hashes and all CH29 reference certificates remain in `research/ch_c14_23/` through `research/ch_c14_29/` in Cognitum GitHub and the original CH29 reproduction archive.',
 '- No adjusted statistical estimator, global-search output, scientific causal identification, or production C14/G25 algorithm was changed.',
 '- Numerical decisions concern only the fixed coefficient domain `[-10,1] × [-5,5] × [-5,5]`. Global optimality over all real coefficients, uniqueness, and valid confidence interval calibration remain **unproven**.',
 '- CPU timings are process CPU on this Linux environment. They measure verification cost, not solver throughput, not cross-machine absolute speed and not wall-clock improvement under different parallel schedules.',
 '', '## Next engineering gate',
'', 'Profile shared-memory verification across more than two successive checkpoint budgets. For process-restart recovery, treat any persistent proof cache as untrusted until independently reconstructed or attested by a separately validated trust mechanism; never silently replace a mathematically verified bound with an unauthenticated display value.',
 '']
report='\n'.join(lines)
(D/'Engineering_Report_CH_C14_30.md').write_text(report)
print('report generated',len(lines),'lines',len(report),'chars')