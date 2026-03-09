# Changelog

All notable changes to the kr-company-registry crosswalk are documented here.

---

## [1.0.0] — 2026-03-09

### First production extraction

**Extraction stats**
- Total companies extracted: **3,948** (all DART entries with a non-empty `stock_code`)
- Active listed (KOSPI + KOSDAQ + KONEX): ~1,750
- Delisted (corp_cls = E, retained by DART): ~2,200
- First run time: ~90 minutes (3,948 companies × ~1.37 s/call including network latency)
- Re-run time from cache: ~10 seconds
- BRN (`bizr_no`) coverage: **100%** of domestic companies
- CRN (`jurir_no`) coverage: **99%** (foreign-listed companies have no Korean CRN)

**Data quality discoveries and resolutions**

| # | Discovery | Resolution |
|---|---|---|
| 1 | **35 SPAC / recent-listing tickers are alphanumeric** (e.g. `0004V0`, `0015G0`) — KRX assigns 6-character codes that include letters for SPACs and some new listings. Initial validation used `str.isdigit()` and incorrectly flagged these. | Changed to `str.isalnum()` in `validate.py` and `tests/test_crosswalk.py`. Documented in README Limitations. |
| 2 | **~39 foreign-incorporated companies listed on KRX** (ticker range `900xxx`–`950xxx`) do not hold Korean 사업자등록번호. DART returns their foreign registration numbers verbatim — wrong length, sometimes alphanumeric. Initial BRN validation flagged 36 of these as format errors. | Added ticker-prefix exclusion: companies with `ticker.startswith("9")` are excluded from BRN format checks. Same in validate.py and tests. Documented in README Limitations. |
| 3 | **~38 foreign-listed companies also have empty CRN** — Korean 법인등록번호 does not apply to foreign-incorporated entities. | Documented in README Limitations. CRN format check already skips empty values; no code change needed. |
| 4 | **Sample-mode tests were failing on size assertions** — `test_minimum_row_count` and `test_market_distribution_plausible` expected ≥1,000 rows but `--sample 5` produces 5 rows. | Added `if len(df) < 100: pytest.skip(...)` guards to both tests. Full runs are still enforced. |
| 5 | **`.gitignore` `dist/` pattern matched `data/dist/`** — prevented `git add data/dist/`. | Changed `dist/` to `/dist/` (root-anchored) so only a top-level `/dist/` folder is excluded, not `data/dist/`. |

**API behavior confirmed**
- `OpenDartReader.corp_codes` returns 115,421 total corporations; 3,948 have a non-empty `stock_code`
- `dart.company(corp_code)` returns 20 fields per company (CEO name, address, phone, fax, industry code, founding date, fiscal year-end, etc.) — no field-selection parameter exists
- The full JSON payload is cached to `data/raw/dart/<corp_code>.json` as an artifact of this constraint, not intentional data collection
- The published output contains only the 8 columns this project was designed to produce

### Files changed
- `src/build_crosswalk.py` — added `is_listed` boolean; removed is_listed from market mapping logic
- `src/validate.py` — alphanumeric ticker check; foreign-ticker BRN exclusion; full coverage reporting
- `tests/test_crosswalk.py` — same fixes; sample-mode skip guards
- `README.md` — expanded Limitations section; added API over-fetching note; updated schema table
- `data/dist/kr_corp_ids.parquet` — first production artifact (183,517 bytes, 3,948 rows)
- `data/dist/kr_corp_ids.csv` — first production artifact (UTF-8 BOM, 3,948 rows)
- `uv.lock` — pinned dependency versions
