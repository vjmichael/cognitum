# Cognitum — ChatGPT Library research and data archive

**Archive date:** 2026-11-22  
**Source:** the owner's ChatGPT Library, principally `/Cognitum/Development`, relevant Cognitum documents at `/`, and the `/KAN Restored` URL list.  
**Status:** archival evidence and research history. **Not an extension of the accepted Cognitum Core v1.0 product or a fresh scientific qualification.**

## Why this archive is separate

The owner's Cognitum Core v1.0 working source and scoped five-operation Python MEL adapter were accepted at exact source commit `9ecceabebbe65deb72fa151a0a34fe6921bc70ed` ([native evidence](https://github.com/vjmichael/cognitum/actions/runs/44990342955)). The owner subsequently locked and closed the project. This archive is a **separate data-only branch** and does not modify the frozen `release/cognitum-core-v1.0` snapshot or the implementation in `main`.

This historical Library material includes research plans, original architecture revisions, experiments, benchmarks, reports and proof/test observations. Historical reports can describe incomplete or rejected candidate experiments. Their presence here does **not** promote them to validated or deployed product features.

## Inventory

- **422 preserved original text/data records** across 15 JSON archive bundles:
  - `bundles/development-part-01.json` through `development-part-08.json`: 233 records from the historical Cognitum development folder (238 considered, 5 not copied).
  - `bundles/root-part-01.json` through `root-part-07.json`: 189 records from relevant Library root files (206 considered, 17 not copied in those bundles).
- **40 individually preserved original files**: 23 project architecture/benchmark/reference files, one KAN URL bibliography and 16 historical CH40C math-witness results. Two files excluded from the bundles because of text-reader size limits were recovered separately as full-size JSON files: the MEL compiled inventory and the 84-question Qwen benchmark set.
- **462 original Library records total** represented by the bundle entries and individually archived files. These are historical source-file *records*, not 462 independently qualified capabilities.

## Where to find things

- `Root/` — directly accessible original Markdown and JSON including the MEL architecture, HDC/KAN master register, original research charter, critical/strengthened revisions, source-informed architecture, mathematical reconciliation, the 84-question Qwen benchmark, MEL compiled inventory and selected test/benchmark results.
- `Cognitum/Development/CH_C14_40_C/CH40C_RESULTS_VERIFIED/` — 16 separate original mathematical witness and summary JSON files.
- `KAN Restored/Documents/List of urls.md` — original research links, without republishing the referenced scientific PDFs.
- `bundles/development-part-*.json` and `bundles/root-part-*.json` — original file data with preserved Library paths for reconstruction, grouped to keep the archival commit manageable.

## Bundle format and reconstruction

Every archive bundle uses `format: "cognitum-library-text-archive-v1"`. Its `records` are:
```json
{
  "path": "/Cognitum/Development/<historical-path>",
  "size_bytes": 1000,
  "text": "<original UTF-8 file content>"
}
```

The JSON string `text` contains the preserved original UTF-8 content, **not a summary**. `size_bytes` was checked against the Library file metadata before inclusion. A future restoration script can parse the bundle, remove the leading `/` from each `path`, and write `record["text"].encode("utf-8")` to the desired destination. Check destination paths against a fixed root and refuse escapes before writing. `excluded` records retain the names and reasons when the source reader could not supply reliable original bytes.

## Explicit non-uploads and remaining gaps

**Deliberately excluded as requested or unsuitable for a public code repository:**

- Python wheels, package/dependency directories, executables, installed software, source code bundles, setup scripts and old ZIP checkpoint/test kits.
- Keys, PEM material, passwords, tokens, private host diagnostic material and sensitive files.
- Third-party KAN research PDFs and the CORe50/MOT17/TrackEval raw dataset archives. Their publication rights and size should be handled at their original sources, not by silently copying them to this public repository.

**Source-text fidelity exceptions:** Several raw CSV files were delivered by the Library text reader as transformed spreadsheets rather than exact CSV bytes; other extremely long JSON files exceeded the reader's normal page cap, or content triggered a conservative sensitive-material check. These have **not** been uploaded as potentially corrupted partial files. See each bundle's `excluded` entries. Of the 22 candidate exclusions recorded by the bundles, the original MEL compiled inventory and Qwen 84-question evaluation data were later **recovered and uploaded individually**, leaving **20 candidate exclusions unresolved** (some may be redundant copies of already accepted research data). The Library still holds the original files.

This archive is not a completeness certificate for every file ever held in the Library, and no third-party redistribution license has been inferred. Relevant additional artifacts can be reviewed and archived later without changing Core v1.0.

## Product lock and interoperability

Cognitum Core v1.0 remains owner-accepted and frozen. Lu's actual loading of Cognitum, live model tool-selection and result publication are still reserved for the owner's own physical test; nothing in this research archive asserts that interoperability succeeded.
