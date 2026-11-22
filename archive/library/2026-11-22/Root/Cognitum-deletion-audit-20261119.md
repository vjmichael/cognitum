# Cognitum storage cleanup — 2026-11-19

Scope: `/Cognitum` Library only; 771 files, 1,115,068,081 bytes. No deletions were performed. Size units in this report are decimal.

## A — Verified GitHub-backed removal candidates (28 files, 9,702,288 bytes)

Each exact match was verified by computing the Git blob ID from original Library bytes, then comparing with the immutable commit tree. For seven text files, the Git blob equals the Library file with exactly one final LF removed; append that LF for byte-identical restoration. Preserve the archive and historical research branch refs.

| Library path (relative to `/Cognitum`) | Bytes | GitHub restoration | Verification | Git blob ID |
|---|---:|---|---|---|
| `Development/CH_C14_23/results.jsonl` | 729,690 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/results.jsonl) | Exact bytes | `cf0fafcfaf1dd7f47da5cc6b80659470936ac435` |
| `Development/CH_C14_23/bounded_results.json` | 6,171 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/bounded_results.json) | Exact bytes | `ee91b407f854a299363f8897299851f817dc3336` |
| `Development/CH_C14_23/Engineering_Report_CH_C14_23.md` | 6,024 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/Engineering_Report_CH_C14_23.md) | Exact bytes | `2299da0a3e10f2ac66b22ae33b4214bf533196e2` |
| `Development/CH_C14_23/run.py` | 4,607 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/run.py) | Exact bytes | `83aa8d83e15c87669d279d4e479310e7661bf302` |
| `Development/CH_C14_23/ch22_pinned.py` | 4,583 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/ch22_pinned.py) | Exact bytes | `48ea7f7037afae9cf22a0e372e4bb4d7ba1aa8a4` |
| `Development/CH_C14_23/independent_audit.py` | 4,505 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/independent_audit.py) | Exact bytes | `71406e15bebded4f650ba3da502fb16032bde566` |
| `Development/CH_C14_23/bounded_global.py` | 3,633 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/bounded_global.py) | Exact bytes | `11b60c88829f34c5964503a3949ee8fc5ca8c254` |
| `Development/CH_C14_23/test_ch23.py` | 2,320 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/test_ch23.py) | Exact bytes | `e5618bac05384385914acd30032b3cb45a41924e` |
| `Development/CH_C14_23/frozen_protocol.json` | 1,453 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/frozen_protocol.json) | Exact bytes | `9b8116680882da476d78e9846229d89fa12d2215` |
| `Development/CH_C14_23/SHA256SUMS.json` | 1,076 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/SHA256SUMS.json) | Exact bytes | `38b92ab568ecd5965076283b85dd7888a777044f` |
| `Development/CH_C14_23/README.md` | 565 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/README.md) | Exact bytes | `4bbc0e2751b6f7bb0350bc1babe49ff6b1fe4ddb` |
| `Development/CH_C14_23/audit.json` | 480 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/audit.json) | Exact bytes | `27ce0fd2fc31c482d23acfdfabe26fa7e525e51c` |
| `Development/CH_C14_23/execution.log` | 175 | [Pinned file](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/research/ch_c14_23/execution.log) | Exact bytes | `efb2e66094e28fb6c6d986a143f36c3f9c73d35d` |
| `Development/CH_C14_28/CH28_EVIDENCE_TRANSFER.md` | 580,809 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_28/CH28_EVIDENCE_TRANSFER.md) | Restore one final LF | `ef771b2874e657951715620523dd1739b7e3949e` |
| `Development/CH_C14_29/Transport/CH29_equal_cpu_zip_transfer.md` | 652,829 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_29/Transport/CH29_equal_cpu_zip_transfer.md) | Restore one final LF | `95a406b75f0b3e75d5defb22eb14e02d00068d74` |
| `Development/CH_C14_29/Transport/CH29_final_sources_transfer.md` | 191,804 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_29/Transport/CH29_final_sources_transfer.md) | Restore one final LF | `96700bf956a9ea6644437fe7905cc777a2bb2568` |
| `Development/CH_C14_29/Transport/CH29_fixed_zip_transfer.md` | 649,417 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_29/Transport/CH29_fixed_zip_transfer.md) | Restore one final LF | `52c5e9130cf901a8504acc8a0783317c7ed6c9cd` |
| `Development/CH_C14_32/GITHUB_CH32_EVIDENCE_TRANSFER.md` | 1,221,339 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_32/GITHUB_CH32_EVIDENCE_TRANSFER.md) | Restore one final LF | `9ecd937d6bb563e9867a4fdf5e3c6d4fd485e653` |
| `Development/CH_C14_33/GITHUB_EVIDENCE_TRANSFER.md` | 1,402,623 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_33/GITHUB_EVIDENCE_TRANSFER.md) | Restore one final LF | `3efb750e423753c2724f7f45f3b2699009ea9ee3` |
| `Development/CH_C14_33/GITHUB_FINAL_SOURCE_TRANSFER.md` | 144,600 | [Pinned file](https://github.com/vjmichael/cognitum/blob/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots/Development/CH_C14_33/GITHUB_FINAL_SOURCE_TRANSFER.md) | Restore one final LF | `be07bee7ff0f8ccc30ec84c5c4e374fbf12369b9` |
| `Development/CH_C14_25/Cognitum_CH_C14_25_Original_CH23_MPFR_15_Cases_2026-11-02.zip` | 316,107 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_25/CH25_evidence_bundle.zip) | Exact bytes | `04d356b96ade2893e2e83a16e8d83ffff56f7e90` |
| `Development/CH_C14_27/CH_C14_27_Evidence_Original15.zip` | 341,733 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_27/CH27_evidence_bundle.zip) | Exact bytes | `ab390ee0cc9e5e2cd5ce8d115d9164efa2188a89` |
| `Development/CH_C14_28/CH_C14_28_Evidence_63_127_Original15.zip` | 435,576 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_28/CH28_evidence_bundle.zip) | Exact bytes | `7490a999b2d1de2acf61d82f6141837abac6e1a0` |
| `Development/CH_C14_29/CH29_equal_cpu_63_127_evidence.zip` | 489,575 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_29/CH29_equal_cpu_63_127_evidence.zip) | Exact bytes | `8d04dd889f6ff5600c3c4fe8f7a937296221cf3f` |
| `Development/CH_C14_29/CH29_fixed_63_127_evidence.zip` | 487,022 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_29/CH29_fixed_63_127_evidence.zip) | Exact bytes | `966f9e419494e916eb1cfe63a91d7d17a77d331b` |
| `Development/CH_C14_31/CH_C14_31_Progressive_Restart_Evidence.zip` | 55,677 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_31/CH31_evidence_bundle.zip) | Exact bytes | `cd34db86b85ca0c720bfef95e791dceda9e8b3b3` |
| `Development/CH_C14_32/Cognitum_CH_C14_32_Journal_Evidence_15_Original_CH23_2026-11-02.zip` | 915,966 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_32/CH32_journal_evidence_15_original_CH23.zip) | Exact bytes | `ee9edccf620fe7061e605e6a033da1b12e7bab87` |
| `Development/CH_C14_33/Cognitum_CH_C14_33_Evidence_15_OriginalCH23_2026-11-02.zip` | 1,051,929 | [Pinned file](https://github.com/vjmichael/cognitum/blob/e5c23c7abf3e87eb26f2ecbd3031681594541f82/research/ch_c14_33/CH33_evidence_15_original_CH23.zip) | Exact bytes | `67f41a29e152bf1aa9104f90198e9c642e0366f2` |

## B — Additional likely GitHub archive copies (not yet individually verified)

The archive branch contains 275 matching relative-path records (6,640,190 bytes), all exactly one byte smaller than the Library file. Some overlap with group A. Seven large transfer documents were checked and proved to differ only by a trailing newline; seven CH23 records also have exact originals on main. Do not delete the unverified remainder solely on that pattern. [Archive source tree](https://github.com/vjmichael/cognitum/tree/d6243923dcdca9a52927a4a9e10317efe40a0233/docs/archive/library-source-snapshots).

## C — Re-downloadable packages (373,431,562 bytes; conditional)

Keep the originals on a local drive if offline work remains important. All 12 upstream binary/source members of the three solver archives matched the recorded SHA-256 and byte length in Cognitum_Index_20261103.zip. Their original URLs and per-file hashes are in that small index. Current availability of every upstream package was not re-tested; the outer ZIP is not guaranteed to be reproduced byte-identically.

| Library path | Bytes | SHA-256 | Recovery |
|---|---:|---|---|
| `Packages/cifar-10-python.tar.gz` | 170,498,071 | `6d958be074577803d12ecdefd02955f39262c83c16fe9348329d7fe0b5c001ce` | [Official CIFAR source](https://www.cs.toronto.edu/~kriz/cifar.html); local MD5 matches published c58f30108f718f92721af3b95e74349a |
| `Packages/Cognitum_SCIP_20261103.zip` | 135,053,146 | `282572f0d67d92969579f3024145f91884833618e3e8d5f4dcfc11b605a53c61` | Cognitum_Index_20261103.zip manifest; restore verified upstream members by exact SHA-256 |
| `Packages/Cognitum_Ipopt_20261103.zip` | 47,515,711 | `9cda01141d5e3eeb1270564a13a53e8b0333e4307f9b16e1faf2be406b910f13` | Cognitum_Index_20261103.zip manifest; restore verified upstream members by exact SHA-256 |
| `Packages/Cognitum_FLINT_Arb_20261103.zip` | 20,364,634 | `97321a299454c2d60984b7caea6240265ad2ed79d5eb643b76fe43995bddcb25` | Cognitum_Index_20261103.zip manifest; restore verified upstream members by exact SHA-256 |

Keep the small index and checksum sidecars. A copy of the recovery manifest is provided separately.

## D — Further conditional cleanup: TrackEval (150,218,296 bytes)

Both Library archive hashes match the repository’s [pinned acceptance receipt](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/docs/integration/COG06E_LOCAL_TRACKEVAL_COMPATIBILITY.json). The archive bytes are not stored in Cognitum GitHub. Only remove after independently retrieving and hash-checking the replacement, or retaining a verified external copy.

| Library path | Bytes | SHA-256 | Restore source |
|---|---:|---|---|
| `Datasets/TrackEval/data.zip` | 149,957,160 | `148a4bdf56f8cb32f9bde4b3d70717242cbb2e61900ef0101abc4652e268f2a5` | https://omnomnom.vision.rwth-aachen.de/data/TrackEval/data.zip |
| `Datasets/TrackEval/TrackEval-master.zip` | 261,136 | `5a089bf3638d1f3a7ae8383ccebf774146f7b1ceca1de989a97b55c76248eb5c` | https://github.com/JonathonLuiten/TrackEval/tree/12c8791b303e0a0b50f753af204249e622d0281a |

## E — Retain until specifically verified

- CORe50 sample tar and CSVs: exact sampled dataset used in COG03F2, not merely a generic dataset.
- CH40F 101,868,937-byte original MPFR producer-certificate archive; original CH40E/G traces and witnesses. No equivalent complete archive verified in inspected GitHub trees.
- C15 checkpoint/test-kit ZIPs and historical Windows benchmarks: source branches exist, but complete archive contents, dependencies and evidence have not been proven redundant.
- IBEX source repair, remaining solver wheels, newer scientific wheelhouse in Shared Development Toolchain, provenance or signing records. Preserve until exact recovery or alternate custody is established.

No GitHub release assets were listed for this repository. The archive review is not an exhaustive scan of every branch or all historical commits. No files were deleted, moved or renamed.
