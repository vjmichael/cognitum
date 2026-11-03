# CH40-D / local mathematical proof witness protocol v1

**Research status:** scoped acceptance only. **Scientific production release: NO_GO.**

CH40-D adds **new, independently checkable local witnesses** to the frozen
CH29 proof tree, drawn from original CH23 datasets and externally pinned via
CH39's reproducible ZIP SHA-256. Historical CH29/CH39 displayed upper bounds
are *not* retroactively certified, and CH39's live separate-UID attestor is
*not* changed. These are deliberately distinct verification gates.

## Trusted roots and source restrictions

- External CH39 archive SHA256: `9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.
- The pinned CH39 witness case mapping identifies each original CH33 checkpoint
  file and its CH32 journal head, case wrapper, original model and 127-node
  certificate. `verify_original40.decode_case` validates the external pins and
  canonical compressed certificate before the prototype producer runs.
- Every CH40-D witness includes original-case name, full certificate and model
  SHA-256, original node ID + SHA-256, exact box, source upper method, and
  explicitly research-only scope. Checker independently verifies identity and
  exact source node geometry, not a supplied filesystem path.

## What must be independently checkable

1. **Direct upper witness:** each likelihood-row enclosure, a verified positive
   Fisher determinant interval, and the resulting objective upper bound. The
   checker independently evaluates the binomial-logistic likelihood and
   positive-definite Fisher bounds, confirms that each stored interval contains
   its own result, then recomputes the cap using the *stored* enclosures.
2. **Coupled tangent witness:** a source-frozen SPD dual matrix index, every
   rational `p0` support point, outward intervals for `g(p0)`, `g'(p0)`, the
   probability range, each row's tangent majorant and the dual logdet constant.
   Checker verifies SPD and
   `g''(p)=-s/p²-(n-s)/(1-p)²-2k <= 0` with `k=n*x'Qx/2>0`,
   recomputes each row independently, verifies the trace includes it, and
   checks the published cap dominates the summed trace.
3. **Taylor witness:** exact midpoint, entire finite local box, outward
   enclosures for midpoint objective and score and box Hessian, and an order-2
   Taylor upper cap. Checker independently rederives the Firth-adjusted score
   and Hessian and sums the worst-case Taylor remainder from the *declared*
   outward intervals rather than trusting hidden producer numbers.
4. **Newton/Krawczyk witness:** strictly interior source/root box, midpoint,
   rational preconditioner, outward midpoint/box scores, full box Hessian,
   and Krawczyk enclosure. Checker recreates the Krawczyk image from the
   *published* enclosures and confirms a stationary-point exclusion,
   non-lossy strict contraction, or conservative no-gain outcome.
   **No Newton claim excludes boundary/global maxima.**

Each of these four checks uses a dedicated CH40-D verifier module that imports
**neither the CH40-B producer mathematical functions nor the CH23–CH39 MPFR
interval or BnB implementations**. Its direct/coupled arithmetic uses exact
rational algebra and separately widened libmpdec transcendental endpoints;
its Hessian derivative engine uses independently written 95-digit directed
Decimal interval operations. The CH40-B witness emitter uses its own 85-digit
Decimal IV and analytic derivatives. **Both paths ultimately depend on the
correctness of Python's libmpdec `exp/ln` implementation**. This is independent
mathematical source logic, not an independently verified transcendental C
runtime or a formal proof of libmpdec.

## Acceptance and exclusions

- All **15 frozen original CH23 cases** produced four locally verified claims;
  the final independent read-only audit rechecked all **60 proof objects**
  from the external pinned archive and their saved witness files.
- An independent suite of **36 positive and adversarial tests** passed,
  including forged tangent support, altered Fisher determinant, narrowed
  Taylor Hessian, forged Krawczyk contraction/exclusion and source pins.
- Five interior stationary-root contractions, two interior stationary-root
  exclusions and eight conservative no-gain diagnostics; *all separate from
  original 127-node historical producer trees*.
- Historical optimized display caps independently certified by these newly
  emitted local witnesses: **0**. They remain **unattested displays**; a new
  valid upper that is slightly larger does not certify a tighter old number.
- No original node-wide Taylor or Newton proof actions are inserted or assumed;
  15 selected direct node and 15 original coupled node local witnesses are
  generated, plus 15 tiny-box Taylor and Newton witnesses.
- No finite-root global 0.05 gap or unrestricted global optimum has been proved.
- **No live CH39 signer/attestor integration**. Signatures are not evidence of
  correct mathematics without this independent verifier's bounded receipt.
- Production Cognitum C14/G25, Lu, and existing accepted CH39/CH40-A/B/C
  source remain unchanged.

## Reproducibility

On Windows, extract the complete ZIP and run `RUN_CH40D_WINDOWS.cmd` (Python
3.11+; standard library only; no native MPFR DLL required). The launcher
reproduces all 15 original cases and runs an independent final audit. Results
are written under `CH40D_RESULTS/`, with the terminal report
`CH40D_FINAL_ACCEPTANCE.json`. New reports contain source and witness hashes;
original CH39 archive is verified before use and never modified.

For a development-host run:

```sh
python -m unittest discover -s tests -p test_witness40d.py -v
python batch40d.py --jobs 1
python finalize40d.py
```

## Remaining CH40-E gate

Instrument the *historical MPFR production-side* code to emit the same
complete local tangent/rounding/Taylor/Newton trace; run the independent
checker against those exact producer-specific enclosures and numeric caps.
Only after that passes, design a nonce-bound and signed research-scope receipt
handoff to the live CH39 five-account attestation service. Do not interpret
local certification as global optimality.
