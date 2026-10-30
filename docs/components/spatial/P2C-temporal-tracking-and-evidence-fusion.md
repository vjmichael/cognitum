# Cognitum C15 / T1 / P2C — Temporal identity tracking and evidence fusion

**Status:** offline reference milestone, bounded and read-only. **Scope:** Cognitum only. Prior P2B snapshot and Lu/GitHub untouched. C14 real-LLM evaluation remains deferred.

## 1. Research question

Can short trajectory histories, a motion uncertainty model, and caller-supplied discriminative features improve proposal rankings after occlusion or crossing **without converting a plausible association into a verified physical identity**?

The P2C reference answers a narrow version only: it demonstrates a bounded, exact top-K association algorithm with deliberate limits. It **does not** provide trained perception, calibrated confidence, independently authenticated history or physical identity assurance. No real tracked video or sensor data was used.

## 2. Methods and priors

A track has up to eight strictly increasing tick-indexed world-position samples with optional synthetic numerical descriptors (2–8 dimensions). Its most recent sample must match the read-only scene snapshot's object position and tick exactly. This restricts accidental history/snapshot mismatch **but cannot establish truth for earlier samples**. Detections are anonymous, same-tick world-coordinate proposals.

**Constant velocity:** for two most recent samples, `v = (p_t - p_(t-1)) / (tick_t - tick_(t-1))`, with prediction `p_hat = p_t + v * delta_tick`. A one-sample history uses zero velocity. This uses *ticks*, not calibrated physical seconds. It is not a Kalman filter.

**Uncertainty heuristic:** `sigma_pred = hypot(sigma_obs, sigma_process * delta_tick)`. The positional ranking cost is `0.5 * (distance(z, p_hat) / sigma_pred)^2`. This is **not** validated positional coverage and omits full state covariance and acceleration uncertainty. Per-track category and observation-source equality, finite values, motion gates and a max-gap limit are required.

**Feature ranking:** externally supplied descriptor vectors are L2-normalized, and the optional cost is `descriptor_weight * (1 - cosine_similarity) / 2`. It is an **untrained, unauthenticated feature**—not a true learned re-identification embedding. Identical or missing descriptors and long gaps trigger conservative ambiguity when there are competing assignments.

**Assignment:** total cost sums motion + descriptor terms, with a fixed unmatched penalty. Exhaustive one-to-one enumeration is capped at six detections and six tracks; at most eight lowest-cost hypotheses are returned. `exp(-cost)` weights are normalized **only within retained top K** and are **not calibrated probabilities**.

**Trust:** scene hash, conversation scope, task/trace/request strings, duplicate/tick/version controls, descriptive anomaly warnings and deterministic arithmetic replay exist. Neither a digest nor replay can authenticate supplied sensor/feature/history evidence. Proposal remains read-only; no scene ID update, user consent or tool authority is generated.

Prior art: DeepSORT combines motion with learned association metrics (https://arxiv.org/abs/1703.07402); ByteTrack explores low-confidence detection association (https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/315_ECCV_2022_paper.php); HOTA separates detection/association/localization properties (https://pmc.ncbi.nlm.nih.gov/articles/PMC7881978/). P2C implements **none** of these full trackers. SciPy Hungarian (`linear_sum_assignment`) is the independent last-position baseline for the synthetic study, not a claim of matching a production SORT/DeepSORT system.

## 3. Experiment: 200 seeded single-transition fixtures

40 seeds for each of five deliberately tiny constructed scenarios, 2 objects and 2 detections per fixture. Ground-truth IDs are visible **only** to the evaluator. Handcrafted 2D descriptors are injected; there is no camera, real feature encoder, noise distribution fitting or independent dataset. The trials rank 80 physical identities per scenario.

| Scenario | P2C top-ranked correct | Last-position Hungarian correct | Marked ambiguous / 40 | Interpretation |
| --- | ---: | ---: | ---: | --- |
| velocity_cross | 80/80 | 0/80 | 0/40 | velocity prediction beats nearest position under clean history |
| appearance_swap | 80/80 | 0/80 | 0/40 | discriminative supplied features override proximity under clean features |
| indistinguishable_swap | 0/80 | 0/80 | 40/40 | numerical top-rank wrong but ambiguity correctly flagged |
| long_occlusion | 80/80 | 0/80 | 40/40 | correct top-rank in constructed trajectory but conservatively ambiguous |
| spoofed_descriptor | 0/80 | 0/80 | 0/40 | **failure:** confident candidate can be WRONG if features are malicious or incorrect |

### Interpretation

- **Positive:** independent motion and descriptor cues can correct position-only ranking in carefully constructed crossings and swaps. Exact assignment and simple uncertainty accumulation can be verified offline.
- **Critical failure:** spoofing or corruption of untrusted descriptors can produce a wrong candidate **without an ambiguity warning**. There is no model-side cryptographic or statistical way to authenticate a caller-supplied feature without a trusted acquisition and provenance system. `CANDIDATE_ONLY` does not mean identity is verified.
- **False confidence control:** matching features do not imply posterior calibration; even a clean synthetic test is not an external validation set. Positional sigma is a heuristic, not a confidence interval.
- **Do not conflate:** 0/80 correct physical identity ranking under identical descriptors is not detection failure; 40/40 ambiguity is useful abstention but not solved tracking. This is one transition, not a multi-step association quality benchmark. Thus we do **not** claim HOTA/IDF1/MOTA or realistic identity-switch rates or recovery-latency scores.
- **Performance:** trial elapsed times recorded on this container for exploratory diagnostics only; no performance baseline for Windows/real sensor workloads.

## 4. Deterministic checks and adversarial gate

New `cognitum/spatial_temporal_tracking.py` and `proto/cognitum/spatial/v1/temporal.proto` add a **research-only** response. `verify_proposal` re-executes the deterministic algorithm and compares exact Protobuf wire bytes. It detects edits to proposed IDs, scalar costs and the `grants_authority` flag; it does **not** sign or validate real-world observations. Test suite includes null/mismatched features, stale/mixed ticks, forged context scope/hash, forged response, movement history mismatch, forbidden source/category transfers, truncated horizons, resource limits and one-to-one matching.

Selected validation on Linux Python 3.13.5 with protobuf 6.33.6 and SciPy 1.17.0: **C15 94/94**; C13 139 passed, two optional skips; C14 615 passed, 37 optional skips; **52/52** Protobuf schemas independently compiler verified; 200/200 study fixtures. All completed suites: zero failures. No unrestricted historical suite rerun.

## 5. Open research gates

1. **P2D:** use independently labeled real/motion-capture or standardized MOT sequences with actual frame times and physically meaningful covariance; compute IDSW, IDF1, HOTA, association precision/recall, abstention, recovery delay and resource costs. Compare calibrated Kalman+Hungarian, JPDA, ByteTrack, DeepSORT/appearance and learned CAPS challengers fairly under fixed settings.
2. **Evidence admission:** signed sensor/camera provenance, host-scope replay journal, trusted descriptor extraction, tamper detection and explicit identity promotion policy belong to an independently enforced boundary; do not add it by quietly mutating P1 scenes.
3. **Adaptive uncertainty:** include acceleration, pose covariance, camera frames, occlusion visibility models, descriptor reliability drift and calibration holdouts. Cross-sensor re-ID remains unsolved.
4. **Next C15 tracks:** T2 part–whole reasoning and T3 occupied/free/unknown volumetric representations may proceed independently of real-world tracking gate.

**Files:** `tools/run_c15_p2c_temporal_study.py`, `P2C-temporal-study-evidence.json`, `P2C-functional-test-evidence.json`, `tests/test_c15_p2c_temporal_tracking.py`.
