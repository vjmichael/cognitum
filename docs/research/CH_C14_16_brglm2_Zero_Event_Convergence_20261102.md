# CH-C14-16 — brglm2 all-zero outcome convergence diagnostics

**November 2, 2026 · Research-only diagnostic PASS · package-convergence unresolved · C14 scientific release NO-GO.**

The actual offline R 4.5.0 / `brglm2` 0.9.2 package environment was reused to investigate CH15's contradictory `brglmFit: algorithm did not converge` warning versus fit `converged=TRUE` on CH13's immutable all-zero fixture (SHA256 `8334e1b4eaa78ad98ae17ec528b2dc41d1927b2d063b7a9b25cf2c0aeb735d32`).

- Swept **36 deterministic all-zero configurations**: two estimation types (`AS_mean`, `MPL_Jeffreys`), epsilon 1e-4/1e-6/1e-8, slowit 1/.5/.25, maxit 100/500. **36/36 emitted the algorithm-nonconvergence warning**; 28 still exposed `converged=TRUE`; all coefficients finite. Increasing iteration budget did not clear warning.
- Varied outcomes with fixed X and the first 0, 1, 2, 5, 10 or 20 cases flagged positive (same source fixture, thus **not independent holdout datasets**). Four R configurations per outcome count: the **4/4 zero-event runs warned**, and **0/20 positive-event runs warned**.
- Independently reconstructed adjusted-score residuals in Python from recorded coefficients. Maximum infinity norm all-zero 1.7744e-4; nearby-event 4.6891e-4. These small numerical scores are not proof the R package converged cleanly. `AS_mean`/`MPL_Jeffreys` are different controls on related package machinery, **not independent package oracles**.
- A research-only fail-closed acceptance gate rejects any external-package nonconvergence warning irrespective of `converged=TRUE` or coefficient proximity; rejects fit errors, false flags and invalid/missing adjusted-score results. **6/6 new tests pass.** No production patch or auto fallback.
- Reproducibility archive: `Cognitum_CH_C14_16_brglm2_Zero_Event_Convergence_2026-11-02.zip`, SHA256 `b64d205f322a07ddfa3a7141ec392bbbe8cba0782a17fd5be4eb339e7af7a8e3`, **10/10 archive payload hashes checked**. Contains sweep scripts, all 60 outputs, read-only independent score audit, acceptance rule, tests and engineering report; deliberately excludes redistributed R packages.

**External `logistf` numerical equivalence remains blocked** on unprovided `mice`, `mgcv`, `formula.tools` and dependencies. Investigate warning origin/source and independent package convergence on the zero-event case before unblocking that one numerical-quality gate. G25 and original CH11/CH13 untouched; no Lu or Windows work. C14 scientific release **NO-GO**.
