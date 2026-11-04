# C08/C09/SSM recovery, comparison, and consolidation decision

Date: 2026-11-04
Disposition: **recovered experimental research in one Cognitum codebase;
no production promotion or additional optimization sprint**.

## Consolidated source of truth

- `cognitum/research/hdc_recovered/` is the isolated historical Zog Zoo
  research namespace (BSC, MAP, HRR, FHRR, sparse distributed memory,
  resonator/factor cleanup, stochastic, low-discrepancy, neural HDC, text,
  quantum-circuit *simulation*, data/benchmark runner and self-test). These
  modules are not native Lu tools or a trusted canonical data store.
- `cognitum/research/hdc_optional.py`, `hdc_index_lifecycle.py`,
  `hdc_canonical.py`, and `hdc_admission.py` are the controlled C08
  candidate/verification research boundary. Lu ANSF/FTS5 remains canonical.
- `cognitum/research/kan_optional.py` and `kan_portable.py` remain the
  existing opt-in portable KAN checkpoint inference boundary. Historical
  trainable KAN and K4 optimization overlay are **not yet source-verified or
  restored in this PR**, so they are not silently claimed delivered.
- `cognitum/research/ssm_recovered.py` is the previously built **bounded,
  non-trained diagonal linear SSM reference**; this is not Mamba/S4 and does
  not replace C07's event/snapshot truth store.
- The user's Library source trees `/torchHD-main`, `/pykan-master`,
  `/Zog Zoo` and uploaded SSM engineering guide are catalogued in
  `HDC_KAN_SSM_LIBRARY_GITHUB_GAP_AUDIT_20261104.md`. Third-party entire
  source trees are not bulk-vendored into a public repository.

## Comparative readout — distinguish task and evidence level

| Domain | Existing or new control | Observed/evaluable result | Limit |
| --- | --- | --- | --- |
| HDC VSA algebra | BSC/MAP/FHRR/HRR bind, unbind, item cleanup | Original archived HDC self-test reported/passed 20/20 in local recovery environment; 4 families retained | Algebra is not evidence of search superiority |
| HDC retrieval | Exact relation, SQLite FTS5, BSC+canonical recheck | Deterministic synthetic controls and precision/recall/latency harness committed | Synthetic 32-record examples do not predict large-data, noise or ARM energy outcomes |
| HDC advanced methods | SDM/resonator, stochastic, QMC, neural reduction and simulated quantum | Source recovered, adversarial/numerical tests and cross-platform CI submitted | No verified hardware acceleration, trained-generalization or external benchmarks |
| KAN | Pinned portable NumPy RBF/spline inference | Original tests and shared single-checkpoint numerical/timing harness committed | No matched trained MLP or spline fit comparison in this PR |
| SSM | Stable diagonal recurrence vs independent NumPy recurrence and chunk continuation | Source and numerical parity tests added | Not selective SSM, trained Mamba, S4/S5 or long-range sequence-learning benchmark |

**Conclusion:** HDC's low-power ARM opportunity is a *provisional research
hypothesis*. Keep C08, C09 and SSM available inside the one Cognitum
distribution as **optional research components**, preserving provenance and
limits. Do not route production requests automatically to any of them or
declare any universal winner.

## Engineering closeout boundary

1. Restore archived mechanisms without replacing newer security fixes.
2. CI on Windows/Linux Python 3.11/3.13 and existing Cognitum regressions
   must pass before PR #79 is merge-ready.
3. Keep research modules isolated, not privileged or auto-enabled. In
   particular, recovered HDC memory is **not** a second canonical Lu DB,
   HDC hit scores are **not** proof, and an SSM hidden state is **not**
   verified user memory.
4. No further performance optimization or ARM platform porting in this
   closeout. Any missing K4 trainable source, advanced symbolic KAN,
   learned selective SSM, or edge energy claims are **deferred named gaps**,
   not blockers to advancing to the next Cognitum component.
5. Next Cognitum work resumes on the broader component roadmap, keeping
   C08/C09/SSM bounded and independent.

Release state: **source recovery and comparative instrumentation present;
CI/production acceptance not yet established on latest PR head**.

## Revisit order — owner decision (2026-11-04)

Continue the broader Cognitum component acceptance and integration roadmap now.
When the postponed scientific-research work is reopened, **revisit HDC,
KAN and SSM before revisiting C14**. For C14, preserve the established
standard causal-library integrations and previously frozen scope; do not
resume open-ended causal research until after the three architecture-family
reviews. This scheduling preference does not block CI or maintenance bugfixes
on existing C14 code.
