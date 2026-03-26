# Code Walkthrough — kr-company-registry

How the three core files work together to produce the Korean company identifier crosswalk.

---

## The Big Picture

The project has one job: fetch company data from a government API and produce a clean, reliable table. The three files divide that job into three roles:

1. `src/build_crosswalk.py` — **produce** the data
2. `src/validate.py` — **verify** the data
3. `tests/test_crosswalk.py` — **enforce a contract** on the data

They are designed so that each one fails loudly rather than silently producing garbage.

```
DART API
    │
    ▼
build_crosswalk.py
    ├── cache (data/raw/dart/*.json)   ← short-circuits the API on re-runs
    └── outputs (data/dist/)
            │
            ├── validate.py            ← runs immediately after; exits 1 on error
            │       └── summary.md     ← side-effect for Obsidian embedding
            │
            └── test_crosswalk.py      ← runs in CI; enforces the contract permanently
```

---

## 1. `build_crosswalk.py` — The ETL Pipeline

This is an **Extract, Transform, Load** pattern — the standard structure for any data pipeline.

### Extract (two-stage fetch)

The DART API is hit in two passes. First, `_fetch_corp_list()` pulls a bulk list of all 115,000+ companies with their tickers in one call — this is fast. Then for each of the ~3,900 companies that have a ticker, `_fetch_company_detail()` makes a separate API call to get identifiers like BRN and CRN. That's the slow part (~90 minutes on a first run).

### Caching

`_load_cached()` and `_save_cache()` implement a **disk-based cache**. Every API response is written to `data/raw/dart/<corp_code>.json`. On subsequent runs, if the file exists, the network call is skipped entirely. This turns a 90-minute first run into a 10-second re-run — and means the 10,000 daily API call quota is only consumed once.

The cache also has a self-healing feature: if a JSON file is corrupt (`json.JSONDecodeError`), it deletes the file and re-fetches rather than propagating bad data downstream.

### Retry with backoff

`_fetch_company_detail()` wraps every API call in a `for attempt in range(3)` loop. If DART returns a rate-limit status code, it sleeps progressively longer (60s, 120s, 180s) before retrying. If the call raises any other exception, it waits 5 seconds and retries. This is **linear backoff** — essential for any code talking to an external API with usage limits.

### Transform

The raw API response is inconsistent — fields can be `None`, contain hyphens, or have irregular casing. The `build()` function normalises every field as it assembles each row:

```python
bizr_no = str(detail.get("bizr_no", "") or "").replace("-", "").strip()
```

The `or ""` handles the case where the field exists but is `None`. The `.replace("-", "")` strips hyphens that DART sometimes includes. The result is consistent regardless of what the API returns.

The `MARKET_MAP` dictionary (`{"Y": "KOSPI", "K": "KOSDAQ", ...}`) is a **lookup table** — a clean way to convert a single-letter code into a human-readable string without a chain of `if/elif` statements.

### Load

`write_outputs()` writes two formats: Parquet (columnar, fast for programmatic use) and CSV (human-readable, works in Excel). The CSV uses `utf-8-sig` encoding so that Excel can read Korean characters — without the BOM marker, Korean company names appear as garbage in Excel on Windows.

### CLI interface

`argparse` turns the script into a proper command-line tool with named flags (`--sample`, `--force`, `--sleep`). The `main()` function is kept thin — it just parses arguments and delegates to `build()` and `write_outputs()`. The actual logic lives in the other functions, making them independently testable.

---

## 2. `validate.py` — The Quality Gate

This runs after `build_crosswalk.py` and checks the output files. It uses an **error accumulation** pattern rather than failing on the first problem:

```python
errors = 0
# each check either increments errors or not
if errors:
    print(f"VALIDATION FAILED — {errors} error(s)")
```

This means all problems are reported in one run, not just the first one — much more useful when debugging.

The validator encodes **domain knowledge as code**. For example, it knows that tickers starting with `9` belong to foreign-listed companies whose BRNs won't be in Korean format, so it explicitly excludes them before checking BRN format. Without that rule, ~39 foreign companies would produce false failures on every run.

The `write_summary()` function at the end produces `data/dist/summary.md` — a Markdown file with key metrics. This follows the bridge pattern from the workspace framework: the pipeline writes a report, and Obsidian embeds it as a live view. Numbers are never hardcoded in notes.

---

## 3. `tests/test_crosswalk.py` — The Contract

The tests don't run the pipeline. They run against the **already-committed output files** in `data/dist/`. This is a deliberate design choice: the tests enforce that whatever is in the repo is valid, not that the pipeline can produce valid data from scratch.

This is **contract testing** — the tests define what downstream consumers (like `krff-shell`) are allowed to rely on. If someone changes the schema or identifier format silently, the tests catch it.

### Fixtures

`@pytest.fixture` with `scope="module"` loads the parquet and CSV files once per test session and shares them across all tests. This avoids reading the parquet file 18 separate times.

### Sample-mode guards

Two tests include a runtime branch:

```python
if len(df) < 100:
    pytest.skip(...)
```

This makes the test suite usable in two contexts: a fast smoke test (`--sample 5`) and a full production run. Without this guard, running sample mode would always fail the minimum-row-count test, making it useless for quick iteration.

### Encoding test

The final test checks something that is easy to break silently:

```python
has_korean = df_csv["corp_name"].str.contains("[가-힣]", regex=True).any()
```

A wrong encoding wouldn't raise an exception — it would produce garbled text that passes all the format checks. This test catches that specific failure mode.

---

## Key Principles

- **Separation of concerns** — build, validate, and test are three distinct programs with no circular dependencies
- **Idempotency** — re-running produces the same result; the cache makes it cheap
- **Fail loudly** — every layer exits non-zero or raises rather than silently continuing
- **Domain knowledge as code** — the foreign-ticker exclusion, the SPAC alphanumeric rule, the encoding choice are enforced in logic, not just noted in comments
- **Contract over implementation** — the tests guard the output schema, not how it was produced

### One notable trade-off

The tests depend on committed artifacts rather than generating fresh data. That's pragmatic given the 90-minute extraction time, but it means a bad dataset could be committed and the tests would validate the bad data. The validate step in CI closes that gap — it runs before the commit step in the workflow, so corrupt data never reaches `data/dist/`.
