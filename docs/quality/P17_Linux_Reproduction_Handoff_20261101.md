# Cognitum P17 — Linux-only component quality handoff

- Base: `Cognitum_P13_P14_P16_Linux_Only_2026-11-01.zip`.
- Run `python create_patch.py` to regenerate patch from exact mounted P16 source, or apply `patch -p1 < patches/P17_Linux_Quality_from_P16.patch` to a P16 checkout.
- `cognitum/` contains complete recovered development source, with HDC and SSM optimizations and **research-only** C14 diagnostics.
- `tests/` includes inherited Linux tests and 19 new P17 tests; run inherited worker tests in isolated groups because the monolithic run stalled.
- `run_quality_evidence.py`, `component_quality_evidence.json` give reproducible microbenchmark and synthetic causal evidence.
- `development_wheel/` contains `cognitum_core-0.1.0` **development** wheel; it is not a release.
- All Cognitum Windows engineering remains deferred. Lu is unchanged. P13/P14 live kernel acceptance remains blocked on this host.
