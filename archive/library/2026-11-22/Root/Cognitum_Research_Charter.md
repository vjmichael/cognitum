# Cognitum Research Program
## Adaptive markets and cross-domain knowledge synthesis
**Status:** Proposed research backlog | **Date:** November 18, 2026

**Authorization boundary:** Documentation only. No new repository, implementation, live-money trading or changes to existing projects. Complete independent TradeBot and Cognitum foundations first.

## CR-01 — Adaptive market intelligence under uncertainty

### Objective
Investigate whether hyperdimensional computing (HDC) and Kolmogorov–Arnold networks (KANs), separately and jointly, can learn useful market representations, forecast uncertain outcomes and improve risk-aware decisions in a nonstationary environment. TradeBot acts as the independent data and simulated-execution platform.

### Architecture
- TradeBot: timestamped historical and live market events, order simulation, fees, latency, slippage, portfolio accounting and replay.
- HDC: encode observable market features, bind asset and temporal context, retrieve similar regimes and update associative memory with provenance.
- KAN: learn conditional nonlinear functions of features and retrieved regime information. Use quantile objectives or probabilistic heads and ensembles to estimate predictive uncertainty; ordinary KANs do not intrinsically provide calibrated uncertainty.
- Decision policy: convert estimated return distributions into buy, sell, hold or abstain decisions under explicit risk and exposure constraints. Keep predictive learning distinct from policy optimization.
- Audit layer: record features available at decision time, model versions, training intervals, forecasts, actions and realized outcomes. No exchange credentials or real-money execution access.

### Hypotheses
H1: HDC regime retrieval improves out-of-sample forecasting or adaptation versus an otherwise equivalent predictor. H2: KAN provides predictive value beyond conventional nonlinear baselines at comparable resource budgets. H3: combined HDC/KAN improves calibration, risk-adjusted simulated performance or adaptation relative to either alone. H4: uncertainty-aware abstention reduces downside relative to an always-active policy at matched exposure. Null results are valid.

### Experimental sequence
| Task | Deliverable / gate |
|---|---|
| CR-01A | Frozen data contract, timestamp semantics, data quality and leakage tests |
| CR-01B | Historical replay and baseline policies: cash, buy-and-hold, simple momentum, linear and MLP predictors |
| CR-01C | HDC-only regime recognition and retrieval, including drift detection |
| CR-01D | KAN predictors with quantile or distributional outputs; ensemble uncertainty |
| CR-01E | Combined models, risk limits and abstention policy; ablation experiments |
| CR-01F | Walk-forward evaluation with purging/embargo where overlapping labels require it; untouched final test periods |
| CR-01G | Real-time paper trading using fake funds; exchange sandbox or realistic local simulator |
| CR-01H | Reproducible research report including negative outcomes and deployment limitations |

### Evaluation protocol
Pre-register horizons, transaction-cost model, baseline budgets and decision thresholds. Fit normalization and models on training data only. Use chronological splits, multiple market regimes, paired comparisons, block-bootstrap confidence intervals and sensitivity analysis for multiple strategy trials. Measure forecast MAE and quantile loss, interval coverage and calibration, net return, maximum drawdown, turnover, Sharpe ratio with stated annualization assumptions, abstention coverage, drift recovery, compute and memory. Distinguish aleatoric uncertainty, epistemic uncertainty and distribution shift; their separation is approximate. Run frozen and online-learning variants separately; online updates may use outcomes only after they become available. Paper fills cannot establish live execution profitability.

## CR-02 — Cross-domain functional-space synthesis

### Objective
Investigate whether independently trained Cognitum instances can contribute knowledge to a shared representation and whether a higher-order Cognitum can discover transferable relationships that are not evident to isolated instances.

### Mathematical proposal
Let each domain d contribute a learned function f_d: X_d → Y_d, a representation encoder E_d, and a knowledge record K_d containing observations, parameters, uncertainty, validity conditions and provenance. Domain mappings A_d project compatible records into a common representation Z. A meta-model G learns from the aligned records, relations and function evaluations, rather than assuming raw parameters from unrelated networks are directly comparable.

Define candidate synthesis as G({A_d(K_d)}) → (h, u, p), where h is a proposed cross-domain relation or function, u is uncertainty, and p identifies supporting evidence. The shared space may include higher-dimensional HDC vectors, functional descriptors, graph relations and KAN basis evaluations. Increased vector dimension alone is not evidence of increased intelligence or discovered physical dimensions. Effective dimensionality, predictive value and transfer must be measured.

### Architecture
- Independent domain engines: independently trained and versioned; initially markets and controlled synthetic dynamical systems.
- Knowledge exchange contract: domain identity, units, coordinate conventions, time horizon, feature semantics, evidence sources, model version and calibrated confidence where available.
- Alignment: preserve domain distinctions; use explicit semantic mappings, anchor tasks and independent validation. Never treat independently learned HDC codebooks as automatically compatible.
- Meta-Cognitum: HDC retrieval across aligned knowledge and KAN learning of cross-domain relationships or residual corrections. Optional graph and symbolic constraints preserve interpretability.
- Verification: test candidate relations against held-out interventions, domain-specific ground truth and null models. Keep hypotheses separate from verified knowledge; do not recursively promote unverified outputs.

### Example experiment
Train one instance on synthetic oscillators, one on controlled regime-switching stochastic processes and one on market features. Ask the meta-model to identify common dynamical descriptors such as persistence, oscillation or regime-transition patterns. Evaluate whether transferred representations improve prediction or sample efficiency on previously unseen systems. Similarity is not causation; validate with controlled interventions where possible.

### Experimental sequence
| Task | Deliverable / gate |
|---|---|
| CR-02A | Versioned knowledge exchange schema and provenance model |
| CR-02B | Independent synthetic domain instances with known ground truth |
| CR-02C | HDC codebook alignment and cross-domain retrieval benchmarks |
| CR-02D | Meta-KAN learning of compositional relations; compare against pooling and multitask baselines |
| CR-02E | Held-out domain transfer, ablation, random-alignment and shuffled-knowledge controls |
| CR-02F | Effective rank, intrinsic dimension estimates, calibration and evidence audit |
| CR-02G | Optional market-domain extension after CR-01 produces validated records |

### Success criteria
Demonstrate reproducible improvement over isolated engines, naive pooling and parameter-matched alternatives on pre-specified held-out tasks. Measure positive and negative transfer, sample efficiency, effective rank, compute and confidence calibration. A proposed novel relation qualifies as a discovery only after independent validation; mere compression, correlation or larger embeddings do not qualify.

## Portfolio and resource controls
Both programs remain deferred research proposals. No implementation authorization is implied. Finish and verify TradeBot's independent ingestion/replay foundation and Cognitum's stable mathematical runtime first. Then authorize one experiment cohort at a time, with fixed compute/storage budgets, stop conditions and documented results. Use existing project infrastructure; do not create another repository. CR-02 synthetic work does not require market results but should not divert current engineering resources. Hardware acceleration is optional and should follow measured profiling, not precede scientific validation.
