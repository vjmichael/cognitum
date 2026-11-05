# Cognitum Library reconciliation — 2026-11-04

This is a **partial, non-destructive import** from the ChatGPT Library folder `/Cognitum`, not a mirror of a Windows workstation directory.

## Source folders identified
- `/Cognitum/Checkpoints`: historical C15 source ZIP checkpoints and test kits.
- `/Cognitum/Development`: historical C14 and C15 experiments, source snapshots, patches, benchmark outputs, and evidence. Its listing extends beyond one page.
- `/Cognitum/Datasets`: MOT17 and TrackEval data.
- `/Cognitum/Packages`: downloaded solver/distribution archives, including large SCIP, Ipopt, FLINT/Arb and IBEX assets.
- `/Cognitum/Reference Docs`: HDC and KAN training guidance, preserved in `docs/research`.
- `/Cognitum/Win Env`: 473,759,744-byte Windows ISO.

## Imported as source documentation
- `docs/research/hdc-kan-training-guide-library-20261101.md` — exact Library training guidance, preserved as a research reference and **not** an accepted performance claim.
- `docs/archive/README-c14-p1-library-checkpoint-20261027.md` — dated historical development instructions. **Not current release status.**

## Not imported automatically
- Full historical checkpoint ZIPs and build artifacts: may be redundant, oversized, or contain generated dependencies.
- Third-party libraries, solver archives, operating-system ISO, and MOT17 data: avoid licensing, provenance, and repository-size issues.
- Research logs, attestations, private signing material, and public-key records: require a targeted security/provenance review before publication.
- Historical patch/snapshot source trees: require comparison against the unified C01–C19 branch to prevent reverting newer changes.

## Outstanding work
1. Inventory the remaining paginated Library entries and check per-file provenance and sensitivity.
2. Compare source-only files against the unified PR #81 tree using content hashes and explicit component mapping.
3. Import genuinely missing original sources/tests/docs on review branches; avoid overwriting newer source.
4. Keep large datasets and third-party archives outside the source repository; preserve reproducible fetch instructions and hashes instead.
5. If the user's intended folder is on a local Windows PC rather than ChatGPT Library, a separate provided archive or accessible desktop filesystem is required.

**This import is not a claim that all Cognitum Library files have been uploaded.**
