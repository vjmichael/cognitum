# COG-03A — HDC/VSA comprehensive research charter
2026-11-17. Owner reopens HDC for broad redevelopment, not a minimal standard-library plus one or two experimental methods. All registered methods should be represented and tested or receive a justified blocked/deferred disposition. Research inclusion does not mean production selection or every possible published variant. CPU-first; no KAN/SSM change; no CH40 pursuit; preserve accepted COG-07/07A source and C08 default-off canonical guard.

## Historical recovery
Retrieved October 24–28 Zog Zoo/MyAI conversation summaries and the historical Claude handoff, TorchHD integration review and experimental repair report. Full original conversations and Claude's external reply were not retrieved. Library's named historical folders /Zog Zoo and /torchHD-main do not resolve; search-indexed individual records are leads, not proof of surviving raw archives.
- Zog_Zoo_Claude_Handoff_2026-10-24.md (file_0000000042388230b82142d075bc2ec7), TorchHD_Integration_Review_2026-10-24.md (file_00000000d25882308a4ea06dfbc3954f) and corrected torchhd.py (file_00000000b76c8230a5cad83191764009): generic tensor conversion originally corrupted native BSC XOR and HRR convolution. Corrected CPU adapter explicitly typed TorchHD 5.8.4 tensors, 17 historical regression tests passed. Old BSC/HRR results contaminated; fresh paired inputs required.
- EXPERIMENTAL_REPAIRS_REPORT_2026-10-24.md (file_00000000d29481fdbdd0bfbe20e0fe7d): 19 historical new tests and 20 selftests passed. Pair-enumeration recovered 100% of bounded known triples (120 trials/model, D=256 V=16); old greedy under 5%; larger V=48 mean 21.8–116 ms, not general resonator success. SDM precursor nearest-address rather than multi-location Kanerva; 94.1% noisy recall matched brute-force and used 279072 B vs ideal packed 32768 B. NeuralHD precursor sliced nuisance dimensions, not native adaptive learner. Real scrambled QMC replaced mislabeled IID; Sobol max absolute cosine 1 despite mean 0.0296, so antipodal screening is mandatory. Stochastic CPU sampling and quantum schematic are not hardware demonstrations.
- Historical C2 high-D pilot D=100000 N=4000 V=1000 single seed 64 queries: FHRR 100%, HRR 96.9%, MAP 68.8%, BSC 64.1%. At N=8000 89.1/62.5/34.4/37.5%. No certified capacity. Equal 256 KiB stored-index pilot V=64 N=1024: packed BSC/MAP 96.9/96.6% clean, 86.6/86.7% corrupted cue; packed nearest-key 100/100%, hash 100/0%, phase8 FHRR 55.5/45.3%, float16 HRR 18.8/16.7%. Excluded metadata/counters/working RAM, different information contracts. C5 per-chain bundles originally trivialized relational task, corrected to shared graph. C6 actual deltas not 100k churn. Earlier K4 packed retrieval ~35.6→1.75 ms at 12000×2048 reported, source unlocated, reproduce and remeasure.
- Current Git source: 15 recovered Python modules plus package init, exact blobs in register. C08 [canonical guard](../components/hdc-kan/C08-canonical-ANSF-verification-20261104.md) narrow BSC candidate lookup, not a full HDC engine. Previous selftests are historical evidence, no new numeric run here.
- [P21b](../quality/P21b_HDC_Unfamiliar_Structure_Adversarial_20261101.md): centroid 58.33%, 400 erroneous raw assertions, 400/400 reordered pairs changed raw predictions. Guard prevented false assertions. [P21c](../quality/P21c_Compositional_HDC_Order_Invariant_20261101.md): role-aware association 738/744 (99.19%), 0 incorrect assertions, 211/216 new graph topologies, 0/744 order changes, exact graph 744/744 by construction and ~18× faster on this small workload. Preserve both.
- [P24](../quality/P24_HDC_Noisy_Signal_Recognition_Pilot_20261102.md) heavy synthetic sensor noise gave chance-level HDC. [P25](../quality/P25_HDC_Real_Optical_Noise_Robustness_20261102.md) matched noise augmentation removed apparent superiority (severe noise HDC 71.39% vs SVM 75.56%). Hypervector bit flips not sensor corruption. Reported SciFact dense 0.718 vs binary-rescore 0.717, BM25 0.646, word HDC 0.520 nDCG@10 not independently reverified. Reconstruct fresh holds or recover exact original raw data, don't mislabel new checkpoints.
- Current local Python 3.13.5 x86-64: NumPy, SciPy, scikit-learn, torch available; torchhd absent. No new benchmark or package install claimed.

## Literature anchors
- Kleyko et al. 2022/23 [I](https://arxiv.org/abs/2111.06077), [II](https://arxiv.org/abs/2112.15424): models, encoding, composition, memory and applications; register broad major algebras.
- Heddes et al. 2023 [TorchHD JMLR](https://www.jmlr.org/papers/v24/23-0300.html), [upstream MIT](https://github.com/hyperdimensional-computing/torchhd), [classifiers](https://torchhd.readthedocs.io/en/latest/classifiers.html), [docs](https://torchhd.readthedocs.io/en/stable/): eight listed VSA families and maintained learners; explicit types, pinned release/license before use. [hdlib](https://pypi.org/project/hdlib/) MIT alternative; [OpenHD](https://github.com/UCSD-SEELab/openhd) GPU research only, not CPU prerequisite.
- Vergés et al. 2025 [classification comparative review](https://doi.org/10.1007/s10462-025-11181-2): broader encoders/classifiers and datasets, use seven common datasets and 121 UCI benchmark as leads, not a mandate for uncontrolled Cartesian sweeps.
- Frady et al. 2020 [resonator networks 1](https://arxiv.org/abs/2007.03748); Kent et al. [part 2](https://pubmed.ncbi.nlm.nih.gov/33080160/): actual iterative factorization vs bounded search and capacity.
- Teeters et al. 2023 [separating long/short-term memory](https://doi.org/10.3389/fnins.2022.867568): true SDM vs item/superposition memory; external authoritative storage.
- Morris et al. 2022 [Stochastic-HD](https://doi.org/10.3389/fnins.2022.867192); [2024 stochastic computation and symbolic AI](https://doi.org/10.1186/s40537-024-01010-8): bitstreams, GraphHD and HD hashing; CPU first.
- [2025 Sobol optimization](https://prefer-nsf.org/pdf/Sobol-Sequence_2025.pdf): QMC lead, not blanket orthogonality claim.
- [2026 optimal representations](https://pmc.ncbi.nlm.nih.gov/articles/PMC12929535/), [structure-aware optimization](https://www.jstage.jst.go.jp/article/nolta/advpub/0/advpub_2026NCP0008/_article/-char/en), [2026 architectures survey](https://doi.org/10.1016/j.rineng.2026.109589): task-specific representation/encoding, learned and quantized models, compression.
- [2025 hardware survey](https://service.jices.cn/EN/10.20193/j.ices2097-4191.2025.0047); Cumbo et al. [2026 QHDC](https://doi.org/10.1038/s44335-026-00064-6): FPGA/ASIC/in-memory, physical circuit claims require gate-accurate simulator or hardware, input preparation and measured energy.

## Breadth register
Starting states are source coverage, not acceptance; see [machine register](COG03_HDC_RESEARCH_REGISTER.json).
| ID | Method | Starting state | Reference |
|---|---|---|---|
| V01 | BSC | recovered | models.py / TorchHD |
| V02 | MAP | recovered | models.py / TorchHD |
| V03 | HRR | recovered | models.py / TorchHD |
| V04 | FHRR | recovered | models.py / TorchHD |
| V05 | Binary sparse block codes | planned | TorchHD BSBC |
| V06 | Cyclic group representation | planned | TorchHD CGR |
| V07 | Modular composite representation | planned | TorchHD MCR |
| V08 | Vector-derived transformation binding | planned | TorchHD VTB |
| V09 | Tensor product representations | planned | Survey / NumPy reference |
| V10 | Matrix binding of additive terms | planned | Survey / NumPy reference |
| V11 | Sparse binary distributed representations: conjunction/disjunction | planned | Survey |
| V12 | Sparse binary distributed representations: context-dependent thinning | planned | Survey |
| V13 | Geometric analogue of HRR | planned | Survey |
| E01 | Random and indexed IID | recovered | core.py / lowdisc.py / TorchHD |
| E02 | Level, thermometer, circular, density | planned | TorchHD embeddings |
| E03 | Projection, sinusoid, fractional power | planned | TorchHD embeddings |
| E04 | Scrambled Sobol and Halton QMC | partial | lowdisc.py / SciPy QMC |
| E05 | Text, n-gram, random indexing and ordered encoding | recovered | text.py / TorchHD |
| E06 | Graph, tree, role/filler, sequence, FSA | partial | C08 / P21c / TorchHD structures |
| M01 | Item memory and cleanup | recovered | memory.py / TorchHD Memory |
| M02 | True Kanerva sparse distributed memory | partial | sdm.py precursor / TorchHD SparseDistributed |
| M03 | Two-tier associative store | partial | sdm.py / Teeters et al. |
| M04 | Hopfield and modern Hopfield cleanup | planned | TorchHD memory |
| M05 | Reversible incremental association | partial | hdc_index_lifecycle.py / historical C6 |
| R01 | Pair-enumeration decoder | recovered | resonator.py |
| R02 | Iterative resonator / beam factorization | partial | resonator.py / TorchHD |
| R03 | Compositional relational HDC | partial | P21c / C08 canonical verification |
| R04 | GraphHD and HD hashing | planned | 2024 review |
| L01 | Vanilla centroid | partial | TorchHD / historical P21 P24 |
| L02 | AdaptHD | planned | TorchHD |
| L03 | OnlineHD | planned | TorchHD |
| L04 | RefineHD / corrective prototype updates | planned | Historical guide; verify original algorithm |
| L05 | NeuralHD | partial | neuralhd.py precursor / TorchHD |
| L06 | DistHD | planned | TorchHD |
| L07 | CompHD | planned | TorchHD |
| L08 | SparseHD | planned | TorchHD |
| L09 | QuantHD | planned | TorchHD |
| L10 | LeHDC | planned | TorchHD |
| L11 | IntRVFL | planned | TorchHD |
| L12 | Learned projection / multi-prototype / continual and few-shot | planned | 2025 classification review / 2026 survey |
| H01 | Packed BSC/MAP, CPU SIMD and parallelism | partial | parallel.py / reported K4 |
| H02 | Stochastic-HD | partial | stochastic.py / Morris et al. |
| H03 | ARM, Raspberry Pi and FPGA | hardware-deferred | COG-08/09 |
| H04 | Quantum HDC | theory-partial | quantum.py / Cumbo et al. |
| H05 | OpenHD / GPU / ASIC / in-memory / neuromorphic | hardware-deferred | OpenHD / hardware survey |

## Redevelopment groups
- B — paired-input algebra fidelity. Recover corrected adapter and tests where possible (fresh reconstruction if originals missing); pin CPU TorchHD release and dependency/license manifest. Explicit family/dtype/dimension/block/seed/codebook hash, layout, normalization, ties, accumulators and inverse semantics. Native exact small independent references; compare same operands, not generator differences; keep intentional convention differences separate. Four recovered VSAs first, then remaining TorchHD and survey algebra coverage. Original tests immutable.
- C — encoders and capacity. Random, QMC with antipode/collision rejection, ordered/text/numeric and continuous encoders; dense/sparse/packed/quantized forms. Check seed replay, codebook and shape mismatch, counter overflow and explicit tie policies. Equal-D vs equal complete resident/working-memory budgets; dimensions 256–8192, selective high-D trials; 5–10 paired seeds and ≥200 confirmatory queries/cell around capacity knees. Distinguish clean/raw noise/encoded corruption; matched tasks and data.
- D — memory and factorization. Item cleanup, actual multi-location SDM, two-tier and Hopfield, reversible vs compact indexes; 1k/10k/100k change churn, crash/rebuild/continuation, stale/deleted negatives, true counter/journal bytes. Pair-search exhaustive oracle vs genuine iterative resonator and beam; unknown factors, superposed triples, convergence, abstention. Shared directed graph, nested and multi-hop unseen topology tests; exact witnesses, canonical revision/scope/tombstone and host-approved citation. No second canonical database; no approximate fact assertion. Exact graph/hash, nearest-key, ANN and ECC baselines as applicable.
- E — every registered learning family with method-specific training and equal data/preprocessing/tuning/augmentation; train-only model selection, held-out drift and OOD. Compare LR/SVM/RF/kNN and small MLP/random features. Start sklearn real digits/Wine/Breast Cancer, synthetic exact truth, public UCI HAR subject-disjoint sensor when obtained; broader UCI panel after pilots. No bulk uploads initially.
- F — CPU packed/vectorized parity, bounded threads, stochastic bitstream/sampling and analytic errors. ARM/FPGA portable bit-exact vectors now; physical Raspberry Pi energy COG-08, FPGA COG-09. OpenHD/GPU research only with device-specific license/deps; quantum physical/simulator requirements separate, retained as research rather than nonphysical shortcut.
- G — consolidated matched benchmark/ablation. Report task correctness, macro F1, recall/rank/capacity, uncertainty and false acceptance/abstention, complete process RSS and retained bytes (encoder, roles, codebook, counters, metadata, workspace, serialization), train/build/query p50/p95 wall/CPU, cold/warm and concurrent transformer contention. Per-task Pareto fronts, split and seed hashes, raw predictions and full reproducibility metadata. No multiplying counts of identical-seed platform results; no fabricated joules. Full same-SHA Windows/Linux test cohort including preserved COG-07/C08. Model efficacy COG-10 and Lu production integration COG-11 remain separate.

Do not arbitrarily discard a family due to one narrow negative result, and do not force all algorithms into one universal tensor or runtime route. Compare maintained implementations, recovered custom kernels, independent oracles and strong conventional baselines. Default-off research; only later task-qualified independent acceptance can justify promotion. P0 register established, no new runtime code or CI. Next B.

## 2026-11-17 frontier expansion

See [frontier research extension](COG03_HDC_FRONTIER_2026-11-17.md) for 40 additional individually tracked research directions (total 85). B1 retains the original staged algebra closeout; B2 adds GHRR and its recent flattened matrix inference method. C–G incorporate the additional encoding, capacity, reasoning, learning, uncertainty and computational research; no runtime or benchmark claims. Check new literature at each subgroup and final freeze, preserving explicit evidence limits and separate hardware/model efficacy gates.

## Owner-directed unified architecture

See [unified frontier engine direction](COG03_UNIFIED_FRONTIER_ENGINE.md): 85 literature entries feed a single typed hardware-aware HDC execution architecture and coherent task pipelines. FHRR preferred initial composition hypothesis; GHRR optional specialist, evidence decides. COG-03F defines hardware-ready operations and transfer-aware performance, physical FPGA COG-09. Native B1 local gate passed, remaining semantic/integration acceptance open.
