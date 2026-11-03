# Cognitum CH40-J — durable five-UID research runner

**2026-11-03: engineering tests PASS; scientific release NO_GO.**

This phase extends CH40-H/I with a bounded writer-side coordinator (1–4 concurrent requests, default 2), signer-UID verified read-only snapshots, SQLite FULL-sync per-case checkpoints rebuilt from the signed chain, a durable `publication40j.json` intent journal, verified same-record roll-forward recovery, and PID/start-time/UID/command-checked orphan-service recovery. The signer UID 65534 and the independent attestor/math/checker UIDs remain separated. A successful socket response cannot make a checkpoint without independent signature-chain verification.

**Acceptance evidence:** 51/51 tests passed (38 inherited and 13 new), including four actual `SIGKILL` publication-boundary tests, forged-checkpoint refusal, skip-on-resume, bounded parallelism, and a hard-killed-coordinator auto-reap/restart with all four restricted services relaunched. The full package was independently extracted and all 51 tests passed again; all 15 original source-trace SHA-256 pins matched.

**Not complete:** zero new live 15-case signed records; the uninterrupted mathematical replay and independent verification of 15 new live signatures are pending. These engineering tests do not certify global optimality, close the finite-root 0.05 gap, establish off-host trust-tip anchoring, or validate physical power-loss storage barriers.

**Reproducible package:** `Cognitum_CH40J_Durable_Resumable_Five_UID_Research_2026-11-03.zip` (SHA-256 `32d678d0854ec0514a27243f703e8c73965447e0d21befcee3097fbd6b9f62bf`). This package was generated in the conversation environment and is not automatically stored by this GitHub commit.

Run inside extracted package on an isolated Linux environment:

```bash
sudo python3 source/harness40j.py --state-dir /persistent/ch40j --workers 2
```

Restart with the **same** state directory to resume. Its signer private keys must remain securely preserved until independently anchored output has been exported. See the included README for isolation and limitations.
