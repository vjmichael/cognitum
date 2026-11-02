# Cognitum Windows development deferral — November 1, 2026

**User decision:** P15 and **all other Windows-specific Cognitum engineering, integration, validation, and packaging work are DEFERRED until the user explicitly reauthorizes them.** No Windows activities are required to complete the current Linux P13 → P14 → P16 sequence.

Examples within scope:
- P15 Windows suspended-process/Job Object containment and descendant cleanup;
- Windows worker supervisor/host authorization and platform containment acceptance;
- Windows native installer/wheel/runtime acceptance, Windows-specific fixture/CI checks;
- Windows benchmarks, resource limits, Windows filesystems/ACLs and crash/recovery testing;
- Any Windows-related integration test with Lu.

This is a **priority/status decision, not a security waiver**. A Windows production path must remain unapproved/unverified; no Linux test attests Windows security. The scope is **Cognitum**; this document does not change Lu's independent Windows alpha work.

**Active sequence:** P13 Linux kernel containment validation, then P14 Linux independent recovery watchkeeper, then P16 Linux performance/reliability, followed by Cognitum component optimization.

**Important nuance:** P13/P14 live kernel approval needs a writable delegated cgroup-v2 test host. The present local host mounts cgroup-v2 read-only; fake/simulated tests cannot replace real containment acceptance.
