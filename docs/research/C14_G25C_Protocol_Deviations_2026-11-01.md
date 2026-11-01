# G25C research protocol correction — 2026-11-01

The preregistered `model_variants` explicitly included `oracle_diagnostic`, a privileged known-nuisance reference, but the first full 6,000-fixture runner omitted it from interval receipts. Original baseline and fixed-ridge methods were computed and audited; their evidence is preserved under `results/G25C_initial_two_method_*`. This omission is a source/protocol mismatch and **must not be described as full preregistration compliance**.

Correction: implement the originally declared known-nuisance oracle as a **nondeployable diagnostic**, then re-run the exact same seeds while asserting baseline/ridge estimates and refusal decisions agree numerically with the archived initial run. This is a **post-first-run correction**, not independent replication, and must not be promoted as such. Bootstrap remains limited to the two fitted-nuisance methods because known oracle nuisance values do not require re-estimation. No other model, positive seed, threshold or acceptance gate is changed.

No production algorithm or Lu files are touched. Initial file hashes are recorded in `results/G25C_initial_source_digests.txt`.