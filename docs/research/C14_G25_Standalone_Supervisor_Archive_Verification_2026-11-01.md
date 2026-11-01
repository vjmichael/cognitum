# C14 G25 standalone cancellation — clean extraction and provenance check

**Date:** 2026-11-01  
**Scope:** independent Cognitum-only research. No Lu product or Core Extension integration.

- Artifact: `Cognitum_C14_G25_Standalone_Cancellation_E2E_2026-11-01.zip`
- ZIP SHA-256: `44a6634285c1bf131737abdca35a4be54d732aa1bc00964d84ad1801d52630fe`
- The ZIP CRC/integrity test passed. **All 28 payload members** matched their `SHA256SUMS.json` entries in a fresh extracted directory.
- The extracted, unchanged archive passed **68/68** host/guard/supervisor tests, including Linux hostile descendant cancellation and receipt tampering.
- The archive's `tools/audit_supervisor_parts.py` reproduced the complete frozen event accounting across 40 independent black-box subprocess cases: 32 numerical reports, 8 scientific refusals, four duplicate-ID negative controls, maximum numeric delta `2.220446049250313e-16`, no automatic causal certifications.
- The independent black-box acceptance was originally run in four bounded ten-case parts against a single final source SHA-256 `1fad033b4871be412463be7b0236d98805bf003b65a5f4a5c21060812368eeb6`.
- This is **hard process cancellation** tested with POSIX process groups, **not cooperative soft cancellation**. It is not a sandbox. Windows Job Object containment, installed Cognitum distribution smoke, scientific interval calibration and production promotion remain OPEN/FAIL as separately recorded.
- GitHub branch `cognitum/c14-g25-standalone-cancellation-20261101` stores the runnable source, frozen file checks and source-specific report; the complete synthetic receipt corpus is in the companion ZIP, not committed as a production package.

**Release decision:** research lifecycle and clean-extraction verification complete; no production algorithm or release promotion; Cognitum stays separate from Lu.
