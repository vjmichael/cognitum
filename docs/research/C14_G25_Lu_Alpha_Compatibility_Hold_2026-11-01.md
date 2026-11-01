# Cognitum / Lu-Linux development boundary — authoritative correction

**Date:** 2026-11-01  
**Status:** User design decision; supersedes the earlier compatibility-review integration proposal in this file. Historical text is recoverable from Git history.

## Binding architecture decision

1. **Cognitum is its own project.** Cognitum is never merged into, coupled to, or integrated as an execution path inside Lu Core, on Windows or Linux. Lu's alpha release and Cognitum's scientific release have independent gates. Cognitum should not be required for Lu to install, load GGUF, chat, run native tools, or recover sessions.
2. **The Cognitum-specific Lu-Linux branch is a disposable development/test convenience**, authorized to accelerate local experiments. It is not the separate product's production architecture, does not become a second independent Lu application, and is not an acceptance substitute for Windows Lu. Its *base must always be the latest verified stable Lu build*, not a speculative draft PR, an unverified alpha, or a permanently diverging fork.
3. **Branch maintenance:** first establish the latest stable Lu release/ref and its exact commit SHA, then create/update the test branch from that verified stable commit. Keep any test-only changes isolated. If a newer stable release is established, advance the development branch deliberately from that stable base after reviewing conflicts and test results. Do not assert an alpha candidate is stable solely because it is newer.
4. **No Cognitum-to-Lu adapter project.** Do not implement a Cognitum Core Extension, signed-worker wrapper, native Protobuf route, registration, Lu UI exposure, or Lu-side worker authorization as part of Cognitum development unless the user separately and explicitly reverses this instruction. A standalone Cognitum research-host adapter or tests against copied host interfaces do not imply a Lu product integration.
5. **Isolation:** Cognitum's nonproduction G25 sensitivity-reporting and acceptance tests remain research within Cognitum's own environment. Any previous use of Lu-Linux in experiments is merely a local host/toolchain test fixture. Scientific acceptance decisions remain independent of Lu's Windows alpha or Linux stable branches.
6. **GitHub** is used as source repository and change ledger, not the development hub. No Lu source or build artifact was changed in issuing this correction.

## Historical review: what the earlier comparison did and did not show

Earlier source inspection compared draft Lu Windows PR #106 (`work/lu-mmproj-native-pairing-20261101` at `48d78669333131e343ab05eba6cb1e8d088a5f34`) with historical Lu-Linux extension tests. That inspection found unmerged Windows alpha work, Linux-only signed-worker execution, and an intentionally empty vanilla Lu DLC route table. Those factual observations may inform **Lu's own independent engineering**, but **they are not Cognitum integration requirements** and do not authorize development of a Cognitum-specific Windows worker.

The earlier report's suggested "Cognitum-to-Lu" implementation sequence and open integration gate were a mistaken interpretation of the user's design. **They are withdrawn.** Do not block Cognitum's completion on that gate; do not mark it failed or open in Cognitum's release matrix. It is **out of scope**.

## Acceptance bookkeeping

- Cognitum C14 G25 nonproduction standalone reporting tests: retain their recorded results and limitations, including scientific uncertainty calibration gates still open.
- Lu Windows alpha: independently owned by Lu work; its GGUF/MMProj/Vulkan/installer gates are not Cognitum prerequisites.
- Lu-Linux development branch: use only as a test environment based on the latest **verified stable** Lu revision; no silent merging into Lu core.
- Cognitum-to-Lu production integration: **not planned, not requested, and prohibited by current direction**.

This supersession preserves the original document in Git history for provenance, without carrying its invalid integration plan forward.
