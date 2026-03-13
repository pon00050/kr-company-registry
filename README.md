# kr-company-registry

**Open identifier crosswalk for Korean listed companies.**

Links five company identifiers that Korean government agencies maintain in separate,
incompatible silos — making KOSPI/KOSDAQ data joinable across financial filings,
procurement records, customs data, and court registries for the first time as public
infrastructure.

No Asian market has published an equivalent table. This is the first.

---

## The Problem

Korean capital markets data is fragmented across agencies that each use a different
company identifier:

| Identifier | Format | Assigned by | Used in |
|---|---|---|---|
| `corp_code` | 8-digit, zero-padded | FSS / DART | All DART financial filings |
| `ticker` (종목코드) | 6-digit numeric | KRX | Stock prices, trading data |
| BRN (사업자등록번호) | 10-digit | NTS / 국세청 | Procurement (KONEPS), customs, tax |
| CRN (법인등록번호) | 13-digit | Ministry of Justice | Court records, 법인등기 |
| ISIN | KR + 10 alphanumeric | KSD / SEIBRO | Bond markets, CB/BW issuance |

There is no official, publicly maintained table linking these identifiers. Commercial
data vendors (FnGuide, KOSCOM, Bloomberg) hold internal versions as proprietary IP.
The same structural gap exists in Taiwan, Japan, and Hong Kong — no Asian market has
solved it publicly.

**This project solves it for Korea.**

---

## The Output

Two files are published in [`data/dist/`](data/dist/):

| File | Format | Use |
|---|---|---|
| `kr_corp_ids.parquet` | Parquet (columnar) | Python / pandas / DuckDB |
| `kr_corp_ids.csv` | CSV (UTF-8 BOM) | Excel, R, any spreadsheet tool |

Both files are committed to this repository. You can access the data with a plain
`git clone` — no Python, no API key, no pipeline to run.

### Schema

| Column | Type | Description |
|---|---|---|
| `corp_code` | str | 8-digit DART identifier. Permanent — survives relisting. |
| `corp_name` | str | Korean legal company name (as registered in DART). |
| `ticker` | str | 6-digit KRX ticker. Empty string for unlisted companies. |
| `market` | str | `KOSPI` \| `KOSDAQ` \| `KONEX` \| `""` |
| `bizr_no` | str | BRN (사업자등록번호): 10 digits, no hyphens. Stable unless restructured. |
| `jurir_no` | str | CRN (법인등록번호): 13 digits, no hyphens. Permanent. |
| `corp_cls` | str | Raw DART code: `Y`=KOSPI, `K`=KOSDAQ, `N`=KONEX, `E`=ETC |
| `extracted_at` | str | ISO date of extraction run (YYYY-MM-DD). |

### Identifier stability reference

| Identifier | Stable? | Changes on |
|---|---|---|
| `corp_code` | Permanent | Never (survives relisting, SPAC merger) |
| CRN (`jurir_no`) | Permanent | Never (assigned at incorporation) |
| BRN (`bizr_no`) | Stable | Corporate restructuring (분할, 합병, 폐업+재설립) |
| `ticker` | Changes | Relisting, SPAC merger, 우회상장 |

---

## Quick Start

### Option A — Just use the data (no Python required)

```bash
git clone https://github.com/pon00050/kr-company-registry.git
# Open data/dist/kr_corp_ids.csv in Excel, or:
# Load data/dist/kr_corp_ids.parquet in pandas
```

### Option B — Python

```python
import pandas as pd

df = pd.read_parquet("data/dist/kr_corp_ids.parquet")

# Look up a company by ticker
print(df[df["ticker"] == "005930"])  # Samsung Electronics

# Look up by corp_code
print(df[df["corp_code"] == "00126380"])

# Get all KOSDAQ companies with BRN
kosdaq = df[(df["market"] == "KOSDAQ") & (df["bizr_no"] != "")]
print(f"{len(kosdaq):,} KOSDAQ companies with BRN")
```

### Option C — DuckDB (SQL)

```sql
-- Cross-reference DART disclosures with procurement records
-- (once you have a KONEPS dataset keyed by BRN)
SELECT
    c.corp_name,
    c.ticker,
    c.bizr_no,
    k.contract_amount,
    k.contract_date
FROM 'data/dist/kr_corp_ids.parquet' c
JOIN 'koneps_contracts.parquet' k
    ON c.bizr_no = k.bizr_no
WHERE c.market = 'KOSDAQ'
ORDER BY k.contract_amount DESC;
```

---

## Who Uses This

| User | What they do with it |
|---|---|
| **Investigative journalists** | Join DART financial data to KONEPS procurement records; trace company networks using CRN in corporate registry databases |
| **Academic researchers** | Build panel datasets linking DART disclosures (corp_code) to KRX price/volume (ticker) to procurement patterns (BRN) |
| **Regulators (FSS / NTS)** | Cross-system identity resolution; the same methodology the NTS used to recover ₩260B from 27 manipulation-network companies in March 2026 |
| **Foreign institutional investors** | Map unfamiliar DART corp_codes to tradeable KRX tickers; due diligence without a Korean-language Bloomberg subscription |
| **Compliance / KYC teams** | BRN-based matching against KONEPS exclusion lists, sanctions databases |

---

## Data Sources

| Identifier | Source | API |
|---|---|---|
| `corp_code`, `corp_name`, `bizr_no`, `jurir_no`, `corp_cls` | [DART (opendart.fss.or.kr)](https://opendart.fss.or.kr) | `company.json` endpoint via [OpenDartReader](https://github.com/FinanceData/OpenDartReader) |
| `ticker`, market listing status | DART `corpCode.xml` | Same library |

**A free DART API key is required to run the extractor.** The key is free and instant
at [opendart.fss.or.kr](https://opendart.fss.or.kr/intro/main.do). The published
`data/dist/` files require no API key to use.

**Note on API over-fetching:** `company.json` returns 20 fields per company (CEO name,
address, website, phone, fax, industry code, founding date, fiscal year-end, etc.).
OpenDartReader provides no field-selection parameter, so the full payload is always
returned. The raw responses are cached to `data/raw/dart/<corp_code>.json` (gitignored)
as an artifact of this constraint — not as intentional data collection. The published
output contains only the 8 identifier columns this project was designed to produce.
If you run the extractor, the cache files stay local and are never committed.

---

## Running the Extractor

```bash
# 1. Clone and install
git clone https://github.com/pon00050/kr-company-registry.git
cd kr-company-registry
cp .env.example .env        # add your DART_API_KEY
uv sync

# 2. Smoke test (10 companies, uses cached responses on re-run)
python src/build_crosswalk.py --sample 10

# 3. Full run (~1,700 companies, ~14 minutes on first run, ~10s from cache)
python src/build_crosswalk.py

# 4. Validate output
python src/validate.py

# 5. Run tests
pytest tests/
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--sample N` | None | Process only the first N companies (smoke test) |
| `--sleep S` | 0.5 | Seconds between DART API calls |
| `--force` | False | Re-fetch from DART even if cache exists |

DART API responses are cached under `data/raw/dart/<corp_code>.json` (gitignored).
Re-runs from cache complete in ~10 seconds without touching the API rate limit.

---

## Update Cadence

The crosswalk is refreshed **automatically every week** via GitHub Actions
(Sunday 21:00 UTC = Monday 06:00 KST). Each run captures:

- New listings (신규 상장)
- Delistings (상장 폐지)
- Corporate restructurings that change BRN

The workflow fetches only new companies from the DART API (existing responses are
cached), so each weekly run completes in seconds unless new listings have appeared.
`extracted_at` records the date of the most recent extraction run.

---

## Relationship to kr-forensic-finance

This project is the **infrastructure layer**. It is consumed by
[kr-forensic-finance](https://github.com/pon00050/kr-forensic-finance) as a data
input at Phase 5, when the forensic pipeline gains BRN and CRN for joining DART
anomaly signals to KONEPS procurement and customs records.

The crosswalk is maintained as a separate project so that:
- It can be updated independently of the forensic pipeline
- It is useful to researchers and journalists who have no interest in Beneish scores
- It is citable as a standalone open data contribution

---

## Limitations

- **Snapshot, not temporal:** `effective_from` / `effective_to` dates for ticker
  changes on relisting or SPAC mergers are not tracked. The table is a point-in-time
  snapshot. For historical ticker histories, check KIND (한국거래소 상장법인목록) manually.

- **Includes delisted companies:** DART retains `stock_code` entries for companies
  that have since been delisted. The dataset covers ~1,750 actively listed companies
  and ~2,200 delisted ones. Use `is_listed = True` to filter to active listings only.

- **SPAC and recent-listing tickers are alphanumeric:** KRX assigns 6-character
  alphanumeric tickers (e.g. `0004V0`, `0015G0`) to SPACs (스팩) and some recently
  listed companies. These are valid KRX identifiers. The dataset contains 35 such
  tickers as of the March 2026 extraction. Do not assume all tickers are numeric.

- **Foreign-listed companies have non-standard BRN:** KRX reserves the ticker range
  `900xxx`–`950xxx` for foreign-incorporated companies listed on Korean exchanges
  (~39 companies as of March 2026). These companies do not have Korean
  사업자등록번호 (BRN). Their `bizr_no` field in DART contains their foreign
  registration number verbatim — wrong length, potentially alphanumeric, and not
  usable for KONEPS or customs joins. Filter them out with
  `df[~df["ticker"].str.startswith("9")]` before any BRN-based join.

- **CRN (jurir_no) is empty for ~38 foreign-listed companies:** Same population as
  above. Korean 법인등록번호 does not apply to foreign-incorporated entities.

- **Bond ISINs are separate:** Bond ISINs (for CB/BW events) are maintained
  separately via the FSC API and are part of the kr-forensic-finance
  `bond_isin_map.parquet`. This crosswalk does not include them.

- **Court records:** CRN enables lookup in the 법원 법인등기 system, but that registry
  has no public API. Access is fee-based and manual.

---

## License

**MIT.** Data extracted from DART is subject to FSS terms of service (public disclosure
data; generally permissive for research and information purposes).

---

## Contributing

Issues and pull requests welcome. If you find a BRN or CRN that looks wrong (wrong
length, clearly a different company), please open an issue with the `corp_code` and
what you found in the DART portal.
