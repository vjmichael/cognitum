# MATH-DISPLAY-01 — User-facing near-zero presentation

**Status:** independent candidate; 31/31 local tests passed on Python 3.13; user-facing settings UI not yet connected. This feature branch starts from SSM-09B native candidate SHA `5a9a03d7021581dce9d0fcb0e5f934231edf96f9` and does not move or modify that acceptance head.

## User interaction
Location when the future user-facing interface is implemented: **Settings → Mathematics → Display**.

- **Simplify tiny numbers:** switch, initially on for the everyday/default display.
- **Show values below:** displayed as `10⁻ˣ`, editable positive integer exponent `x`, default `3`, supported `1…308`.
- **Simplify OFF:** present the original numeric text in scientific or decimal notation as available (no precision added).
- **Simplify ON:** for finite nonzero approximate real numbers satisfying `abs(value) < 10^-x`, display **≈ 0**, never the unqualified exact zero. Equality to the cutoff is not suppressed.
- Always retain the **full original numeric value** for inspection/copying and user accessibility; zero values remain zeros. The setting is a presentation preference, not a computational tolerance, denoising rule, significance test, model hyperparameter or numerical convergence threshold.
- Fractions, exact mathematical objects, certificate values, complex numbers, NaN and infinities are never collapsed to zero. Formal evidence, safety/uncertainty claims, residuals, gradients, statistical tests, optimization and internal math must access untouched original data and cannot depend on this setting. Graph geometry and data-driven decisions must use original data, not displayed strings.
- Do not quietly classify a nonzero as exact zero. If display suppression matters to interpretation, show `≈ 0` and expose the original value on hover/detail/copy.
- One versioned, bounded JSON setting schema, strict type validation; immutable preference data; no third-party dependencies. User choice may be persisted by the eventual settings service; the research backend does not currently supply a UI/persistence service.
- Scientific users can switch simplifying **off**, or set a higher exponent. Higher exponent is a **display cutoff**; it does not increase the accuracy of the underlying float or model.

## Concrete examples (default cutoff 10^-3)

| Original value | Everyday display | Scientific display (switch off) |
| --- | --- | --- |
| `0.0008` | `≈ 0` | `0.0008` |
| `-0.0004` | `≈ 0` | `-0.0004` |
| `0.001` | `0.001` | `0.001` |
| `1e-10` | `≈ 0` | `1e-10` |
| Exact fraction `1/1000000000` | `1/1000000000` | `1/1000000000` |

**Engineering:** `cognitum/math_display.py`, `research_tests/math_display/test_precision.py`. Local 31/31 tests passed. Production UI controls, persistence wiring, accessibility/locale review, full repository and native Windows acceptance still pending. This independent feature must not be merged into the unchanged-SHA SSM-09B native qualification candidate before acceptance.

## SSM-09B native qualification relation

SSM-09B SHA `5a9a03d7021581dce9d0fcb0e5f934231edf96f9` remains frozen. At the time of this note GitHub reported no workflow runs for that SHA or the unchanged-SHA qualification ref, despite creating the reference. GitHub workflow_dispatch is not accessible through the current connector. An isolated local acceptance attempt failed test collection because `tools.cog04o` was absent from the partial checkout. Do not report the 391 native cases as executed/passing. Next action: launch the existing `Cognitum Python regression` workflow manually (workflow_dispatch) using `cognitum/ssm09b-native-qualification-20261120` on GitHub Actions, then reconcile all four Windows/Linux × Python 3.11/3.13 jobs against exact pinned source receipts.
