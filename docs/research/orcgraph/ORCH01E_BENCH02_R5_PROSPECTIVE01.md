# COG-ORCH-01E-BENCH-02-R5-PROSPECTIVE-01 — durable source-first-seen operator custody

**Status:** precommitted source-only operational qualification; real 28-day prospective capture remains NOT STARTED. This is not a new KAN/HDC result, a publisher-signed first-availability claim, or installed MEL authorization.

## Why the additional collector was necessary

The accepted R5 study [original preregistration](ORCH01E_BENCH02_R5_PREREG.json), Git blob `02828d09afaf584a9b5cc8a66e0f2de917b48429`, still fixes three genuinely new NOAA stations **KBOS/KMSP/KPHX**, two separate source observers A/B, **10-minute** polling, **28 full UTC days** (336 train, 168 calibration, 168 test hours), 1/3/6h forecast horizons and 0/1/3/6/24h feature lags. Earlier R3/R4 negative results remain immutable.

The first R5 prototype supported successful NOAA HTTP 200 responses but did not durably record an **INTENT** before a network call, cannot alone prove continuity after restart, and did not archive every source failure or missed poll. Its original direct GitHub `/zip` artifact redirect had previously returned 401 even though the normal GitHub artifact downloader and original metadata API worked. No running daemon or automatically approved recurring collection existed. Those original failures and refusals must not be erased or reclassified as successful source-first-availability evidence.

A separate **operational protocol was preregistered before implementation** at `docs/research/orcgraph/ORCH01E_BENCH02_R5_PROSPECTIVE01_PREREG.json` (Git blob `4329f1e3281c7a7590cec5720dbca6a0c77c6e7f`, prereg commit `6dea4be2724e17c3d36d4bf18638b3cb7e63a0d2`). It cannot modify the original model, accepted source, original NOAA R3 data, relative RMSE denominators, or previous first-availability caveats.

## Durable, bounded native collector

`tools/orcbench02/prospective_r5_durable.py` implements an explicit one-shot operator command—**no background loop, Docker, service or timer installation**. The same command can be invoked by an independently approved host timer later; invoking it now does not approve that timer.

Before any request, it validates a canonical **HMAC-SHA256 operator grant** against a 32-byte OS-protected secret. Grant binds exact NOAA GET URI, original R5 source/protocol, A *or* B, original runtime code SHA, 10-minute cadence, activation, expiration after at most **4,032 per-lane slots**, operator identity and approval ID. Real activation is POSIX-only with a regular single-link, owner-matched mode-0600 key file and an owner-private journal directory; **Windows OS-backed key custody is not claimed**. Insecure or missing key, forged/expired/source-changed approval and duplicate slot abort before a network request. No approval/key is created or installed by this study.

Local custody is SQLite WAL, `synchronous=FULL`, transaction-bounded hash-chained append-only events with SQL UPDATE/DELETE refusal. Per 10-minute slot, an original `INTENT` is durably committed before its one allowed HTTP GET. Each returns one `OBSERVED` exact bounded original HTTP body, `ERROR` for 429/invalid station/non-JSON/network fault, or `INTERRUPTED` on restart after an unmatched intent. Every missed or late scheduled slot becomes a separate explicit `GAP`; no fabricated success, no retry within a slot, no filling skipped hours. Every exportable slot contains its complete actual event chain, original raw body (where applicable), SHA256 and terminal head. SQL custody alone is **not** evidence that an observation existed on the web before a forecast.

The fixed NOAA request is below the [AWC official API rate limit](https://aviationweather.gov/data/api/), which advises against accessing an endpoint more often than once per minute per thread. This source contract uses at most one GET every 10 minutes **per authorized observer**, no retries or bulk backfill.

## Independently authenticated third-party artifact and admission

`tools/orcbench02/prospective_r5_custody.py` accepts original one-file `poll.json` archives downloaded through GitHub's **supported `actions/download-artifact` path**, not the previously failing direct ZIP redirect. The **production verification entrypoint fetches GitHub Actions artifact metadata independently** from the fixed original repository API and checks its immutable artifact ID, `digest` SHA256 against the exact ZIP bytes, original workflow run ID, original runtime source SHA, expiration, name (lane + exact slot), authentic GitHub `created_at`, bounded ZIP/JSON and complete journal chain. A caller-provided plain JSON metadata dictionary is *never* sufficient to enter the production verification path. Each lane must have independent, distinct artifact and run IDs; the same NOAA upstream is correctly acknowledged as correlated, not two different data publishers.

Before feature admission, the verifier checks every exact 10-minute slot, source event indices and predecessor links from genesis, contiguous original time schedule, expected A/B pair, and **no gap/429/network failure in the 24-hour feature lookback**. It checks *all* archived NOAA station/hour variants: a later correction or duplicate causes conservative **refusal**, never silent replacement of a measurement. Each original feature must be present in both independent original source bodies and authenticated by both **GitHub-created ZIP timestamps at least one second before forecast issue**. Neither runner-local wall clock, advisory `receiptTime`, nor a local SQLite file can prove earlier publisher publication. The forecast admission never reveals a later test target and never issues installed MEL authorization.

## Qualification and limits

Native qualification includes unchanged historical R3, R4, full R4-R2-R3 and prior R5 security tests and new adversarial synthetic source tests on **Windows and Linux, Python 3.11 and 3.13**. Negative cases include invalid grants/key custody, replay, crash after INTENT, late and missing slots, 429, malformed response, wrong station, journal UPDATE/DELETE denial, forged GitHub digest/source SHA/time, same two-lane workflow identity, source correction, historical missingness, 25-hour feature-lag admission and a future artifact falsely claimed to predate issue. A separate fifth job verifies identical original JUnit case inventories, exact tested SHA and original source blobs across all four platforms.

**Important distinction:** Synthetic examples exercise an archived source/anchor trust boundary; no real two-run source capture has been externally attested in this task, and no real 28-day NOAA timeline has been created. The original manual capture workflow remains manual-only. The actual installed operator-approved scheduler and reliable each-slot publication to GitHub Actions (including their operational costs, retention, restart and independent host guarantees) are separate integration acceptance requirements before any scientific first-seen credential is granted.

At 2 lanes × 6 polls/hour × 24 hours/day × 28 days, the design calls for **8,064 original polls**, potentially **8,064 externally archived per-poll artifacts**. This needs separately approved runner/hosting budgets and retention, and is not silently launched by a successful synthetic CI run.

## Remaining steps

1. Independent exact-source source-only test qualification and reconciliation; retire single-use automatic CI after acceptance.
2. Provision two genuinely independent protected native source hosts, operator grants, fixed outbound network policy and **verified original GitHub per-poll publication adapter**, with installed restart/clock/retention tests. Keep default disabled until approved.
3. Collect and externally verify all source/negative/gap records across the 28-day prospective study. Accept missingness as failed eligibility, not replacement.
4. Freeze original method fits/selection before future heldout scoring, evaluate every predeclared site/horizon against strong classical baselines, with source-dependent uncertainty and full refusal denominators.
5. Independent HDC/KAN capacity and learning-curve studies on **new** observations; separately qualify FIN-01 installed MEL authority.
