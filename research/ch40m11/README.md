# CH40-M.11 — OS-separated independent verifier and signed recovery anchor

**Date:** 2026-11-03 (America/Phoenix) / 2026-11-04 UTC  
**Status:** Linux research engineering acceptance; **C14 scientific release remains NO_GO**.

## Executed system, not a simulated permission check

On the real original 15 CH23/CH40-K case series, the unchanged CH40-M.10 independent rational verifier signed 15 durable per-case records covering **296 historical search child-bound checks**. A separate OS-owned anchoring authority advanced a chained, Ed25519-signed checkpoint custody ledger to **15/15**. Public-only M10 recovery rehashed the frozen original traces and both M9 journals per case, checked signer/source identity, and accepted all 15 receipts without recomputing the underlying mathematics. A second standalone public auditor validated the M10 and M11 signature chains and their exact linkage. This public auditor's result is `CRYPTOGRAPHIC_CHAIN_ONLY`—**not an independent mathematical re-proof**.

### Actual Linux process isolation

The trusted root research coordinator starts each principal as a distinct **host OS UID**:

- **25222 / producer:** only its staged, writable M9 search journals, plus read-only Python runtime;
- **25221 / verifier:** original frozen cases and audited source as read-only bind mounts, original journals read-only, private M10 signer read-only, verifier SQLite state writable;
- **25223 / anchor:** public verifier key and anchor service read-only, its separate private anchor-key/state directory writable.

All have an isolated **user, mount and network namespace**, **private tmpfs/chroot filesystem view**, **no-new-privileges**, **zero effective/permitted/bounding capabilities**, no mounted host `/proc`, and per-process CPU/address-space/file-descriptor limits. The trusted supervisor starts processes in new sessions and kills the **entire process group** on timeout. The Linux Landlock syscall was probed and returned `ENOSYS` in this execution environment; **Landlock is not claimed**. Separate OS identities and mount restrictions were tested against actual unauthorized reads/writes, TCP connection attempts, and mount/remount attempts. No native seccomp policy, cgroup tree enforcement, PID namespace, external vulnerability assessment, or Windows acceptance is claimed.

### Durable anchor/repair protocol

The verifier signs an M10 receipt and commits the entire checkpoint with SQLite. The anchor, which cannot read the verifier's signing key, receives the **signed committed row** through the trusted coordinator and verifies source key, canonical bytes, sequence, previous tip, receipt status, and the signature. It signs a separate custody event and atomically fsyncs and renames its own owner-only state. If the verifier is killed after SQLite commit but before anchor advancement, public-key-only M10 recovery validates the signed DB first, then the coordinator advances the missing anchored prefix. If the anchor is **ahead** of DB history, startup refuses: a valid older DB is not allowed to silently roll back the independently stored head. The anchor private key is excluded from all published artifacts.

### Tests and limitations

- **9/9** OS isolation/authorization/resource watchdog/rollback/modified journal tests passed in a standalone process.
- **2/2** real `SIGKILL` checkpoint/anchor-rename recovery tests passed in a separate process.
- **9/9** self-contained public signature-chain and adversarial tests passed in a separate process.
- **15/15** original frozen dataset records; **296/296** previously independently checked children authenticated against signer and original-input hashes.
- An early whole-run coordinator timed out after all 15 verifier records were durably signed but while the anchor lagged at two. The trusted public-only recovery reconciled all remaining records and authenticated the final 15/15 anchor. This is a **recovery** test, not a clean uninterrupted 15-case orchestration result. A previous combined unittest invocation stalled in the network/capability probe; the three isolated test groups above completed cleanly.
- Signed verification is only as trustworthy as the protected signer code/key and frozen case input provenance. The **trusted root coordinator** has ultimate access to both principals and is part of the trusted computing base. No protection is claimed against host-root compromise, anchor-UID compromise, hardware state rollback, host power loss, hostile kernel primitives, or malicious verifier code with access to its own signing key. The previous M10 SQLite implementation uses `synchronous=FULL` and rollback journal; power-failure durability has not been independently proven.
- An untrusted model-generated producer was **not** integrated; the producer role ran hostile access probes and owned staged M9 journals. Lu integration is unchanged and disabled. No global 0.05 gap closure, causal-identification promotion, or production-ready worker guarantee is implied.

### Read-only independently checkable public evidence

`M11_PUBLIC_CHAIN.json` contains the canonical M10 signed row bodies/signatures, the separate signed M11 anchor events, and the two public keys—**no private key and no full frozen datasets**. Check all 15 links without any filesystem privileges:

```bash
python public_audit_m11.py M11_PUBLIC_CHAIN.json \
  --expected-verifier-key-sha b066054cb3722921461bd476cf0963ebb9c5eb6bb49f323ddba292514c23abae \
  --expected-anchor-key-sha ea1ca12500f068cf3fd924910fbd27bea976f4056011b29161afbedca2b2aa71 \
  --expected-anchor-tip 50a82f01d0f2ae058db3b12eb109b8e27c892ef8958ec55e15c3236efd43d51b
```

The pins become an **external** trust reference only when independently retained (for example by the trusted GitHub commit and an operator's pinned digest), not when merely copied from the same untrusted evidence file.

### Research reproducibility

Prerequisites: Linux with user+mount+network namespace support and bind mounts, trusted root launch with `CAP_SETUID/CAP_SETGID`, `setpriv`, `unshare`, `mount`, Python 3.13, `cryptography`, and existing frozen CH40-M.8/M.9/M.10 files at `/mnt/data`. The trusted supervisor never modifies Lu; test sources have deliberate lab paths and hardcoded ephemeral research UID numbers.

```bash
sudo python /mnt/data/CH40M11/coordinator_m11.py --lab /mnt/data/CH40M11/new_research_lab
python -m unittest -v test_m11.OSBoundaryTests
python -m unittest -v test_m11.LiveCrashAnchorTests test_m11.LiveCrashVerifierTests
python -m unittest -v test_public_m11.PublicChainTests
```

The lab path must be **new** and the audit source/fixtures must match the pinned CH40-M.10 baseline. This command is an engineering test, not a recommended production installer. All private keys remain in owner-only private research directories and are **never archived**.

### Next gates

Source-independent hostile worker review; repeated clean 15-case suite runs with bounded child lifecycle; cgroup/PID/host-broker isolation on Linux and Windows Job Object/AppContainer equivalent; stronger write-ahead/fully durable power-failure accounting; key custody separated from a trusted root supervisor where possible; independent external antirollback service; equal-cost full C14 scientific benchmark. Scientific C14 remains **NO_GO**.
