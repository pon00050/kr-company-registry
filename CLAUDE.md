# kr-company-registry — Claude Code Instructions

Open identifier crosswalk for Korean listed companies. Links 5 company identifiers
(DART corp code, KRX ticker, BRN, CRN, market segment) across government silos.

## Ecosystem

Part of the Korean forensic accounting toolkit.
- Hub: `../forensic-accounting-toolkit/` | [GitHub](https://github.com/pon00050/forensic-accounting-toolkit)
- Task board: https://github.com/users/pon00050/projects/1
- Role: Foundation library
- Depends on: none (external: DART API)
- Consumed by: kr-forensic-finance (corp_code ↔ ticker mapping)

---

## Commands

```bash
# Install dependencies
uv sync

# Full extraction (first run ~90 min; re-run from cache ~10s)
uv run python src/build_crosswalk.py

# Extraction — sample mode (5 companies, for smoke testing)
uv run python src/build_crosswalk.py --sample 5

# Extraction — force re-fetch even if cache exists
uv run python src/build_crosswalk.py --force

# Validate outputs + write data/dist/summary.md
uv run python src/validate.py

# Run tests
uv run pytest tests/ -v
```

Requires `DART_API_KEY` in `.env`. Free registration at opendart.fss.or.kr.

---

## Architecture

```
opendart.fss.or.kr
    │
    ▼
dart.corpCode.xml          (115,421 total corps)
    │   filter: stock_code != ""
    ▼
3,948 listed/delisted companies
    │
    ├── per-company: dart.company(corp_code)
    │       → 20 fields including bizr_no, jurir_no, corp_cls
    │       → JSON cached to data/raw/dart/<corp_code>.json  [gitignored]
    │
    ▼
data/dist/kr_corp_ids.parquet   [committed]
data/dist/kr_corp_ids.csv       [committed]
data/dist/summary.md            [committed, Obsidian-embeddable]
    │
    ▼
validate.py  (schema + quality checks → 18 assertions)
```

Key source files:
- `src/build_crosswalk.py` — extraction pipeline
- `src/validate.py` — validation + summary generation
- `tests/test_crosswalk.py` — pytest suite

---

## Conventions

### Ticker handling
- `ticker.startswith("9")` = foreign-listed on KRX (900xxx–950xxx range); ~39 companies.
  Their `bizr_no` contains foreign registration numbers — exclude from BRN format checks.
- SPACs and recent listings use **alphanumeric** tickers (e.g. `0004V0`, `0015G0`).
  Validate with `str.isalnum()`, NOT `str.isdigit()`.

### Identifier formats
| Field | Format | Notes |
|---|---|---|
| `corp_code` | 8 numeric digits | Zero-padded, unique, no nulls |
| `ticker` | 6 alphanumeric chars | Empty string for delisted |
| `bizr_no` | 10 numeric digits | Empty for foreign corps |
| `jurir_no` | 13 numeric digits | Empty for ~1% (foreign-incorporated) |
| `market` | KOSPI / KOSDAQ / KONEX / "" | Empty for delisted |

### Rate limits
- DART API: ≤10,000 calls/day (free tier)
- Per-company cache in `data/raw/dart/` means re-runs are cheap (~10s from cache)

### Data layout
- `data/raw/` — gitignored; reproducible via pipeline
- `data/dist/` — committed; the deliverable

---

## Known Gaps

| Gap | Why | Status |
|-----|-----|--------|
| Paths hardcoded in `build_crosswalk.py:58-60`, no `_paths.py` | Convention deviation; tests can't override paths via `tmp_path` | Unblocked — low priority |
| `validate.yml` CI fails on fresh clone without committed `data/dist/` | Tests verify committed data, not built state | By design |
| Test command in CLAUDE.md says `pytest tests/` (bare, no `uv run`) | Convention deviation vs ecosystem standard `uv run pytest tests/ -v` | Unblocked — fix above |

---

## Downstream Consumer

`kr-forensic-finance` Phase 5 joins this crosswalk to KONEPS procurement data and
customs records using `bizr_no` (BRN) and `jurir_no` (CRN). Foreign-listed companies
must be excluded before those joins.
