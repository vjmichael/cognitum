# Cognitum standalone developer-alpha gate — first executable checkpoint

**State: portable preflight implemented; no alpha release yet.** This checkpoint implements `tools/alpha_preflight.py`, an ordinary subprocess smoke check of the real standalone Cognitum calculator CLI and disabled registry. The gate refuses to claim signed evidence, Lu integration, OS isolation, a production-ready plugin or a Windows installer.

## Alpha-oriented acceptance
1. Standalone core installs in a clean Python 3.11/3.13 environment.
2. `python -m cognitum registry` shows **no enabled or nominated capability by default**.
3. Explicitly enabling the trusted local calculator and calling `calc.rational` on `1/3+1/6` returns the exact rational result `1/2` with assumption-bound interpretation.
4. The preflight reports `PORTABLE_ALPHA_SMOKE_PASS_UNATTESTED` only after the real CLI checks; failures produce a nonzero process exit.
5. New evidence files use exclusive creation (no overwriting earlier results); cross-platform CI runs Python 3.11/3.13 on Windows and Linux.

## Still required before a distributable alpha

- Resolve the base source-import CI integration and missing fixtures in [PR #19](https://github.com/vjmichael/cognitum/pull/19).
- Freeze the minimum enabled first-party capability set and permissions; no automatic activation of research modules.
- Reproducible dependency lock and signed artifact provenance; Windows x86-64 distribution with a supported install/update/uninstall path.
- Windows host-managed worker security/authorization tests and diagnostics, including explicit cancellation/recovery.
- Product acceptance gates for a bounded end-to-end Protobuf call and disabled/missing-worker behavior.
- Run the actual native Windows acceptance runner and independently review its evidence. This preflight **is not** that test.

Cognitum remains a transformer augmentation layer; the existence of a reliable conventional solver is an asset, not a competitor. No Lu modifications are authorized here.
