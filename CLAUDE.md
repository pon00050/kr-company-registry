# kr-company-registry — Claude Code Instructions

Open identifier crosswalk for Korean listed companies. Links 5 company identifiers
(DART corp code, KRX ticker, BRN, CRN, market segment) across government silos.

## Ecosystem

Part of the Korean forensic accounting toolkit.
- Hub: `../forensic-accounting-toolkit/` | [GitHub](https://github.com/pon00050/forensic-accounting-toolkit)
- Task board: https://github.com/users/pon00050/projects/1
- Role: Foundation library
- Depends on: none (external: DART API)
- Consumed by: krff-shell (corp_code ↔ ticker mapping)

---

## Commands

```bash
# Install dependencies
uv sync

# Full extraction (first run ~90 min; re-run from cache ~10s)
uv run python src/kr_company_registry/build_crosswalk.py

# Extraction — sample mode (5 companies, for smoke testing)
uv run python src/kr_company_registry/build_crosswalk.py --sample 5

# Extraction — force re-fetch even if cache exists
uv run python src/kr_company_registry/build_crosswalk.py --force

# Validate outputs + write data/dist/summary.md
uv run python src/kr_company_registry/validate.py

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
~3,900 listed/delisted companies (updated weekly)
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
validate.py  (schema + quality checks → 13 checks)
    ▼
tests/test_crosswalk.py  (18 pytest tests)
```

Key source files:
- `src/kr_company_registry/build_crosswalk.py` — extraction pipeline
- `src/kr_company_registry/validate.py` — validation + summary generation
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
| `validate.yml` CI fails on fresh clone without committed `data/dist/` | Tests verify committed data, not built state | By design |

---

## Downstream Consumer

`krff-shell` Phase 5 joins this crosswalk to KONEPS procurement data and
customs records using `bizr_no` (BRN) and `jurir_no` (CRN). Foreign-listed companies
must be excluded before those joins.


---

**Working notes** (regulatory analysis, legal compliance research, or anything else not appropriate for this public repo) belong in the gitignored working directory of the coordination hub. Engineering docs (API patterns, test strategies, run logs) stay here.

---

## NEVER commit to this repo

This repository is **public**. Before staging or writing any new file, check the list below. If the content matches any item, route it to the gitignored working directory of the coordination hub instead, NOT to this repo.

**Hard NO list:**

1. **Any API key, token, or credential — even a truncated fingerprint.** This includes Anthropic key fingerprints (sk-ant-...), AWS keys (AKIA...), GitHub tokens (ghp_...), DART/SEIBRO/KFTC API keys, FRED keys. Even partial / display-truncated keys (e.g. "sk-ant-api03-...XXXX") leak the org-to-key linkage and must not be committed.
2. **Payment / billing data of any kind.** Card numbers (full or last-four), invoice IDs, receipt numbers, order numbers, billing-portal URLs, Stripe/Anthropic/PayPal account states, monthly-spend caps, credit balances.
3. **Vendor support correspondence.** Subject lines, body text, ticket IDs, or summaries of correspondence with Anthropic / GitHub / Vercel / DART / any vendor's support team.
4. **Named third-party outreach targets.** Specific company names, hedge-fund names, audit-firm names, regulator-individual names appearing in a planning, pitch, or outreach context. Engineering content discussing Korean financial institutions in a neutral domain context (e.g. "DART is the FSS disclosure system") is fine; planning text naming them as a sales target is not.
5. **Commercial-positioning memos.** Documents discussing buyer segments, monetization models, pricing strategy, competitor analysis, market positioning, or go-to-market plans. Research methodology and technical roadmaps are fine; commercial strategy is not.
6. **Files matching the leak-prevention .gitignore patterns** (*_prep.md, *_billing*, *_outreach*, *_strategy*, *_positioning*, *_pricing*, *_buyer*, *_pitch*, product_direction.md, etc.). If you find yourself wanting to write a file with one of these names, that is a signal that the content belongs in the hub working directory.

**When in doubt:** put the content in the hub working directory (gitignored), not this repo. It is always safe to add later. It is expensive to remove after force-pushing — orphaned commits remain resolvable on GitHub for weeks.

GitHub Push Protection is enabled on this repo and will reject pushes containing well-known credential patterns. That is a backstop, not the primary defense — write-time discipline is.
