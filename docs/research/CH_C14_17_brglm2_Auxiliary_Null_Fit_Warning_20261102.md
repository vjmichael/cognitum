# CH-C14-17 — brglm2 auxiliary null-fit warning root cause

**2026-11-02 | Research diagnostic PASS; logistf BLOCKED; C14 scientific NO-GO.**

Inspected the installed **brglm2 0.9.2** namespace code. In `brglmFit`, after solving the main model, the null-deviance computation recursively calls the intercept-only `brglmFit` with `start=linkfun(mean(y))` if an intercept is present and offset is missing. All-zero binomial-logit data give `qlogis(0)=-Inf`, which fails the recursive fit and emits the algorithm-nonconvergence warning, although the *main* returned model can have `converged=TRUE`.

Reproduced on the frozen CH13 all-zero fixture with the real offline R 4.5.0 and actual `brglm2`:
- Ordinary full-model fit: `converged=TRUE`; auxiliary nonconvergence warning appears.
- Intercept-only fit initialized at -Inf: warning reproduced; finite-start zero coefficient: no algorithm-nonconvergence warning.
- Explicit zero-offset full-model fit: skips recursive null fit, emits no algorithm-nonconvergence warning and yields the **same three coefficients** (difference <1e-12). Other diagnostic warnings can remain.
- **5/5** new automated actual-R regression tests passed.

The CH16 global fail-closed rule is **not relaxed in production**. This is a reproducible *origin classification* of an auxiliary-fit warning, **not** permission to accept any warned numerical result, change C14, or claim scientific calibration. Validate main fit independently before any research reclassification.

**logistf still unavailable:** Uploaded `logistf_1.26.1.tar.gz` source declares `mice`, `mgcv`, `formula.tools`, `Matrix` imports. Only Matrix is in the isolated library; first three and transitive dependencies/compilers are still missing. No independently run `logistf` fit or complete two-package 16-fit gate. Existing 8-fixture `brglm2` coefficient screen is retained with the origin-specific caveat.

Local reproducibility archive `Cognitum_CH_C14_17_brglm2_Null_Fit_Origin_2026-11-02.zip` SHA256 `be9555e8861b6891ceaa3466786567c91d97eb94b614f8a8409020706756bcda`. Six payload checksums independently checked, contains R scripts, 3-row R diagnostic output, executable 5-test suite, README and detailed report. Requires prior CH13 fixture and isolated R runtime. No redistributed third-party packages. GitHub only research repo and evidence record.

**C14 scientific release remains NO-GO.**