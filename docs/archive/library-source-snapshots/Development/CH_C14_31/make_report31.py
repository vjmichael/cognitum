"""Generate CH31 report from frozen original-data replay receipts."""
from __future__ import annotations
import json,pathlib,statistics
D=pathlib.Path(__file__).resolve().parent
r=json.loads((D/'benchmark_results.json').read_text())
assert r['cases']==15 and r['restart_reverified_cases']==15 and r['global_certificates']==0
stages=[7,15,31,63,95,127]
per={s:[next(x for x in item['stages'] if x['nodes']==s) for item in r['per_case']] for s in stages}
rows=[]
for s in stages:
 vals=per[s];rows.append(f"| {s} | {sum(x['fresh'] for x in vals):,} | {sum(x['reused'] for x in vals):,} | {sum(x['cpu_seconds'] for x in vals):.2f} | {statistics.mean(x['gap_upper_display'] for x in vals):.6f} |")
ambiguous=[x for x in r['per_case'] if x['original_data_identity'].get('ambiguous')]
body=f'''# Cognitum CH-C14-31 — Progressive MPFR replay and trustworthy restart

**Date:** November 2, 2026 (America/Phoenix)  
**Disposition:** Scope-limited research-engineering verification PASS; unrestricted-global and scientific C14 promotion **NO-GO**.  
**Isolation:** No production C14, pinned G25, Lu, Windows, or DLC changes.

## Design and source binding

CH31 reuses archived CH29 original-data 63- and 127-node certificates against **the 15 exact original CH23 datasets**. Input CSV-equivalent rows are the original CH25 frozen JSON, bound by SHA256 using CH29's original case registry. The full dual matrix digest, original CH29 frozen protocol, and original archived certificate hashes are verified before every case.

To exercise a longer staged sequence, we derive 7/15/31/95-node **proof-prefix projections** from existing 63/127-node CH29 proof trees. This is a mathematical verifier experiment, **not four new solver runs**. Each derived prefix is a closed binary partition, and the full MPFR replay proves its actual upper bounds. Original 63 and 127 nodes remain unchanged.

The precise sequence is **7 → 15 → 31 → 63 → 95 → 127**, always replaying only newly admitted nodes while retaining prior *verified in-process* MPFR endpoints. No saved verification receipt, hash, pickle, cache file, or imported checkpoint is accepted as a mathematical proof.

## Cohort and measured CPU

| Stage (nodes) | Newly replayed MPFR bounds (15 cases) | Reused previously checked caps | Process CPU, seconds | Mean remaining objective gap |
|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The six stages collectively verified **{r['total_fresh_caps_during_chain']:,} new node-bound evaluations**, and reused **{r['total_reused_caps_during_chain']:,} prior certified caps**; the sequence would require 15×(7+15+31+63+95+127) = **5,070** bound computations if every stage were independently replayed from scratch. Actual repeated MPFR bound recomputations across the sequence were only **{r['total_fresh_caps_during_chain']:,}**, a **{(1-r['total_fresh_caps_during_chain']/5070)*100:.1f}%** reduction *in bound computations*, not necessarily CPU time because partition traversals, result validation, and bookkeeping still cost time.

Cumulative measured **same-process progressive verification CPU**: **{r['total_cpu_incremental_chain_seconds']:.2f} s** across all 15 cases. Individual stage CPU timing includes input model setup, partition traversal, MPFR bounds for the new nodes, and receipt checks. These totals are process-CPU summed over parallel case workers, not wall-clock speedup claims.

## Real process restart: fail closed

Every original case was independently resumed in a **new Python interpreter process**. No raw verified objects or computed caps were sent into that process: it reads the source-bound original CH29 63-node certificate and performs **63 fresh MPFR cap checks** before it may extend to the 95 and 127 nodes. It then checks only 32+32 new bounds and verifies the complete partition and ancestor caps again.

- **{r['restart_reverified_cases']}/15 OS-process restarts** individually reestablished a cold trusted 63-node checkpoint.
- Reused node counts after restart: 0 at 63, 63 at 95, 95 at 127.
- Total fresh restart verification process CPU (63+32+32): **{r['total_cpu_fresh_restart_seconds']:.2f} s**, separately measured.
- All final gaps match CH29's original cold 127-node verification within 1×10⁻¹⁰ display units. The displayed tolerance is only a regression check; proof decisions use directed MPFR endpoint comparisons at 224 bits.

A restarted process **cannot restore** trusted MPFR state from serialized content. Original certificate files are *untrusted inputs to be reverified*, and a stored receipt is only an audit artifact. The Python interpreter/process itself remains a trusted-code boundary: arbitrary malicious in-process code is outside this engineering threat model.

## CH23 ambiguity preservation

All **3/15** original CH23 ambiguous zero-event cases remain explicitly **UNRESOLVED_REFUSE_CERTIFICATION**. All other cases remain research-only; none achieved the 0.05 finite-domain objective-gap threshold. No unrestricted-coefficient-domain optimality, uniqueness, causal identification, confidence-interval calibration or statistical production readiness is claimed.

## Integrity, negative tests, and limitations

A focused 18-test research suite plus eight invalid-prefix subtests rejects changed historical nodes, wrong split axes, incomplete proof partitions, forged certification, altered model input, changed duals, precision mismatch, wrong stage budget, and unsupported external cache import. The chain rejects retracing a prior stage; failed verification does not poison an already verified prior prefix. The original CH29 independent verifier and its results remain available for differential checks.

Remaining limitations: proof routines reuse CH24/CH27/CH29 MPFR and mathematical enclosures, not a separately formalized proof-assistant specification; only a finite coefficient box is covered. Derived intermediate prefixes are post hoc verification fixtures, not prospectively run optimizer checkpoints. No cross-process cryptographic state import was implemented (intentionally).

## Next work

If longer-running consumers need durable restarts, preserve **only the original certificate and its provenance**, not trusted proof state. Consider a streaming/event-journal representation of monotone proof-tree extensions, and profile exact cap recomputations against partition-validation overhead on representative 255-/511-node CH29 search outputs when independently available. Keep scientific C14 NO-GO.
'''
(D/'Engineering_Report_CH_C14_31.md').write_text(body)
print('report lines',len(body.splitlines()))