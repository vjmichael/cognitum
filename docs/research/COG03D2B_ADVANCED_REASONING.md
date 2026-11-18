# COG-03D2B — advanced factorization and relational reasoning

Accepted D2A source `6f21bb0e5957f567e2f86f181bcc2ac3feda0b82`; [run 44225450045](https://github.com/vjmichael/cognitum/actions/runs/44225450045), 18/18 successful. All 18 original ZIP SHA-256/CRC and 160 recorded hashes compared, 391 tests on each HDC platform. [Receipt](COG03D2A_RUN_44225450045_ACCEPTANCE.json). No local rerun of the native external proof/tracking libraries. New candidate reconstructs prior local D2B investigation after volatile scratch files were unavailable; no claim of preserving that unexported code. Recovered and checked all 65 previous source blobs against manifests locally and at repo head. All 418 dedicated tests (391 inherited, 27 D2B) pass locally, actual CPU TorchHD 5.8.4 including native BSBC positional binding. Local exact source-bound D2B dedicated wrapper and independent smoke passed, scratch Git SHA 165971f5b16ddb852ca7006aa700f7ba7cbb1649; full sequential hosted workflow pending, not a full local repository checkout. Existing canonical C08 and production routes unchanged, no host authority.

## Implemented references
- Shared-coordinate correlated MAP/FHRR codebooks (fraction explicitly shared, not measured Pearson correlation), multi-start coordinate beam and weighted two-object matching pursuit with positive least-squares residual correction. Equal weight can tie in greedy cleanup; explicitly abstain rather than arbitrary subtraction. Bounded exact joint equal-weight pair oracle checks uniqueness and residual. D2A models preserved.
- Compact binary SBC codebooks (uint16 positions), dense normalized GSBC PMF estimates, FFT circular correlation verified with scalar loop, L-infinity score equivalence (minimum selected mass for one-hot atom), threshold plus conditional random sampling and normalized bundle, capped search count under Cartesian budget. [Hersche et al.](https://doi.org/10.3233/NAI-240713) equations 1,3–10; no CNN training, large-scale optimized hyperparameter search or hardware reproduction. Detection threshold is not global uniqueness; exhaustive comparator and ties tested.
- [GraphHD](https://arxiv.org/abs/2205.07826)-inspired rank MAP encoding, PageRank/degree, tie-aware ranks and separate endpoint binding, exact-feature centroid control. Dynamic collision-resolved feature fingerprints use exact feature identities; do not identify isomorphic graphs or replace a conventional hash, not a reproduction of published HD hashing.
- [ARC-VSA](https://doi.org/10.1038/s44335-026-00100-5), author repo https://github.com/ijoffe/ARC-VSA-2025 pinned MIT c031a9c6b4885ab03b28fbfdcd97b6b3693df564. Independent finite 1D object DSL (left/right/reverse/color cycle) and FHRR scene ranker. Independent grid-array executor scores new input scenes. No author code imported, no reported ARC score; not equivalent budget for narrow exact-check caps, because ranking scores all programs. Full real Sort-of-ARC/1D-ARC/ARC-AGI panel retained for E/G.
- Exact supported two-hop rule hypothesis, distinct training starts and held-out entities with counterexamples lacking consequent edges; shared ordered-path FHRR candidate ranking and exact current antecedent/consequent witnesses. Not a proof of a universal rule, no assertion of new host facts, full actual PathHD LLM and real KG/analogy comparisons later.

## Paired five-seed results, fixed hyperparameters
Common 512 MiB address-space cap per independent seed (601–605), peak RSS 108056–109320 KiB including all arms/imports. This is neither equal measured RSS nor per-arm full working budget. Same stored codebooks within arm comparison; fixed seeds, synthetic and related cases, no statistical superiority. Report includes whole feature encoding and ARC ranking times, factor score/search counts, raw outcomes. No hardware energy.

FHRR D256, three factors with 8 or 16 symbols (512 or 4096 combinations), 40 cases per cell:
| Symbols | Shared coordinates | ReLU | Coordinate beam | Exhaustive |
|---:|---:|---:|---:|---:|
|8|0%|40|22|40|
|8|50%|40|40|40|
|8|85%|1|40|40|
|16|0%|40|4|40|
|16|50%|37|40|40|
|16|85%|0|40|40|

At 85% shared coordinates ReLU makes 79 incorrect proposals in 80 cases rather than abstaining, while beam performs well; independent codes expose beam failure (abstains). At 16 independent, ReLU 0.0913s/40 vs exhaustive 0.1663s/40, with 40/40 each; at 8 independent exhaustive is faster. Do not use score alone as verification; no unconditional route. Two-object weighted 2:1 mixtures, FHRR D256 and 25% shared coordinates, 60/60 fully recovered for iterative and exhaustive matching pursuit, no spurious; .5905s vs .0860s aggregate, work measures different counts, not identical kernel operations. Five separate equal-weight joint oracle cases 5/5 at 2016 pair checks each, not broad capacity qualification.

GSBC D512 (16 blocks x32), three factors, 40 cases per cell; uniform probability mixture noise not block corruption:
| Symbols | Noise | L-infinity | Dot | Exhaustive |
|---:|---:|---:|---:|---:|
|8|0|40|11|40|
|8|0.2|40|0|40|
|16|0|37|0|40|
|16|0.2|0|0|40|
|32|0|0|0|40|
|32|0.2|0|0|40|
All iterative misses abstained; no wrong proposals observed in this pilot. At 8 clean L-infinity 2616 searches vs 20480 exhaustive, but .0757s vs .0162s; for 32 even capped 100 sweeps not enough on tested fixed threshold. Store compact indices 768/1536/3072 B vs dense PMF state alone 12288 B; transient arrays excluded. No claim of generalized capacity or speed superiority.

Graph classification: train sizes 6..13, heldout sizes 14..19 star/path/cycle, 90 cases per arm. PageRank rank-exact and HDC both 90/90, degree rank-exact 65/90 and HDC 66/90, direct graph structural oracle 90/90. HDC rank encoding used 23.56 ms across all PageRank fixtures vs 0.398 ms exact rank feature encoding, common PageRank cost ~83.57 ms; score-only comparisons insufficient. 210 feature-fingerprint lookups matched exact dictionary, HDC 13.46ms vs dict 0.057ms. Exact feature equality is not graph identity. Real graph datasets and full GraphHD methods pending G.

Independent 1D DSL: 16 two-command ground-truth programs x5 seeds, two train/two held-out scenes. At full 20-program search universe, both arms solve 80/80. Symbolic arm 805 exact checks and .00471s, FHRR 80 checks but ranked 1600 programs (all 20 each), .13848s. With four exact-check cap symbolic 0/80 and FHRR 80/80 because FHRR already evaluated all 20 for ranking; NOT equal total work or evidence of advantage. Report negative full cost. Witness pipeline: 120 heldout entity queries, 80 observed exact antecedent+consequent witnesses, all 80 retained, zero wrong/missed, 40 cases lacked consequent and no conclusion published. HDC .02047s vs direct exact join .000759s. No established advantage, data synthetic fixed topology and role count.

## Evidence, disposition
Archive COG-03D2B_Advanced_Reasoning_Candidate.zip, SHA-256 4ab475f698a5db2d7f7d4c4cb9a63c5a3411a96b51c3ef35c473690ffa7d6c93, file file_00000000b53881fd8f71fcc32f6fbfa9. Five raw seed reports, RSS logs, 418-case test XML, D2B dedicated source-bound receipt, D2A archive reconciliation; combined pilot SHA-256 2aaca515079dcab64826db1138cb0866f46f685c482aeac65397d5c42a338154. All 85 research entries preserved, none newly declared accepted merely due to local results. Next close exact-SHA grouped acceptance, then E1 learning reference and training fidelity. Remaining exact paper benchmark reproductions, large correlated/unknown factor cases, real graphs, true ARC and actual LLM efficacy remain E–G/COG-10; no production. COG-03F hardware-ready protocol for concrete owner-ordered ALINX AC7K325B; verify board/carrier PCIe lane wiring, actual driver/DMA, resource/timing and physical benchmark in COG-09. No hardware verification or speed claim.
