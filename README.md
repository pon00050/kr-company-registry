# kr-company-registry

Five Korean government agencies assign different IDs to the same company.
This table links them — for every company listed or delisted on Korean exchanges since DART records began.

| Stat | Value |
|---|---|
| Companies covered | 3,949 (active + delisted) |
| Active listed | 2,768 — KOSPI 841 · KOSDAQ 1,817 · KONEX 110 |
| Delisted (included) | 1,181 |
| BRN coverage | 100% of domestic companies |
| CRN coverage | ~99% (foreign-incorporated companies have none) |
| Refresh cadence | Weekly, automated (GitHub Actions) |

---

## The Problem

Korean capital markets data is fragmented across agencies that each use a different
company identifier:

| Identifier | Format | Assigned by | Used in |
|---|---|---|---|
| `corp_code` | 8-digit, zero-padded | FSS / DART | All DART financial filings |
| `ticker` (종목코드) | 6-digit alphanumeric | KRX | Stock prices, trading data |
| BRN (사업자등록번호) | 10-digit | NTS / 국세청 | Procurement (KONEPS), customs, tax |
| CRN (법인등록번호) | 13-digit | Ministry of Justice | Court records, 법인등기 |
| ISIN | KR + 10 alphanumeric | KSD / SEIBRO | Bond markets, CB/BW issuance |

These agencies were built with different mandates and have never been officially linked.
The result: connecting a company's DART financial filings to its KONEPS procurement
contracts — or tracing it through the corporate registry — requires a lookup table that
until now only commercial vendors (FnGuide, KOSCOM, Bloomberg) held as proprietary IP.
The same structural gap exists in Taiwan, Japan, and Hong Kong. This project provides
that link for Korea as open data.

---

## The Data

Two files are published in [`data/dist/`](data/dist/):

| File | Format | Opens in |
|---|---|---|
| `kr_corp_ids.csv` | CSV (UTF-8 BOM) | Excel, R, any spreadsheet tool |
| `kr_corp_ids.parquet` | Parquet (columnar) | Python / pandas / DuckDB |

### Schema

| Column | Description |
|---|---|
| `corp_code` | 8-digit DART identifier. Permanent — survives relisting and SPAC mergers. |
| `corp_name` | Korean legal company name, as registered in DART. |
| `ticker` | 6-character KRX ticker. Empty string for delisted companies. |
| `market` | `KOSPI` · `KOSDAQ` · `KONEX` · `""` (delisted) |
| `bizr_no` | BRN (사업자등록번호): 10 digits, no hyphens. Stable unless the company restructures. |
| `jurir_no` | CRN (법인등록번호): 13 digits, no hyphens. Permanent — assigned at incorporation. |
| `is_listed` | `True` if currently listed; `False` for delisted companies. |
| `corp_cls` | Raw DART code: `Y` = KOSPI · `K` = KOSDAQ · `N` = KONEX · `E` = delisted |
| `extracted_at` | Date of the most recent extraction run (YYYY-MM-DD). |

### Sample rows

| corp_code | corp_name | ticker | market | is_listed | bizr_no | jurir_no |
|---|---|---|---|---|---|---|
| 00126380 | 삼성전자 | 005930 | KOSPI | True | 1248100998 | 1301110006246 |
| 00185301 | 제이피아이헬스케어 | 0010V0 | KOSDAQ | True | 2038148897 | 1101110285787 |
| 00599230 | 평산차업집단유한공사 | 950010 | | False | CT114980 | |
| 00100258 | 에스마크 | 030270 | | False | 3038103040 | 1511110001366 |

Row 3 is a foreign-incorporated company (ticker starting with `9`): non-standard BRN,
no CRN. Exclude from BRN-based joins — see Limitations below.

### Identifier stability

| Identifier | Stable? | Changes on |
|---|---|---|
| `corp_code` | Permanent | Never |
| CRN (`jurir_no`) | Permanent | Never |
| BRN (`bizr_no`) | Stable | Corporate restructuring (분할, 합병, 폐업+재설립) |
| `ticker` | Changes | Relisting, SPAC merger, 우회상장 |

---

## Limitations

Read these before using the data in joins or published analysis.

- **Point-in-time snapshot, not a history.** Ticker changes from relisting or SPAC
  mergers are not tracked. For historical ticker histories, check KIND
  (한국거래소 상장법인목록) manually.

- **Delisted companies are included.** DART retains records for delisted companies
  indefinitely. 1,181 of the 3,949 rows are delisted. Use `is_listed = True` to
  filter to active listings only.

- **Foreign-listed companies have non-standard identifiers.** KRX lists ~39
  foreign-incorporated companies in the ticker range `900xxx`–`950xxx`. These
  companies have no Korean BRN — DART stores their foreign registration number in
  the `bizr_no` field, which is the wrong format for any KONEPS or customs join.
  They also have no CRN. Exclude them with
  `df[~df["ticker"].str.startswith("9")]` before any identifier-based join.

- **~36 tickers are alphanumeric.** KRX assigns 6-character alphanumeric codes
  (e.g. `0004V0`, `0015G0`) to SPACs and some recently listed companies. These are
  valid KRX identifiers, not data errors. Count updates with each weekly refresh.

- **Bond ISINs are not included.** ISINs for convertible bonds and bonds with
  warrants are maintained separately via the FSC API. See
  `kr-dart-pipeline/bond_isin_map.parquet`.

- **Court registry access is fee-based.** CRN enables lookup in the 법원 법인등기
  system, but that registry has no public API. Access is manual and fee-based.

---

## Get the Data

Both files are committed to this repository. A `git clone` is all you need —
no API key, no pipeline to run.

```bash
git clone https://github.com/pon00050/kr-company-registry.git
# data/dist/kr_corp_ids.csv  — open in Excel
# data/dist/kr_corp_ids.parquet  — load in Python or DuckDB
```

Check `extracted_at` to confirm when the data was last refreshed.

---

## Update Cadence

The crosswalk refreshes **automatically every week** via GitHub Actions
(Sunday 21:00 UTC = Monday 06:00 KST). Each run captures new listings
(신규 상장), delistings (상장 폐지), and corporate restructurings that change BRN.

Existing DART responses are cached, so weekly runs complete in seconds unless
new companies have appeared. `extracted_at` records the extraction date.

---

## Who Uses This

| Who | What they use it for |
|---|---|
| **Investigative journalists** | Connect a company's DART financial filings to its KONEPS procurement contracts; trace company networks through the corporate registry using CRN |
| **Academic researchers** | Build panel datasets linking DART disclosures, KRX price and volume data, and procurement patterns — identifiers that previously required separate lookup tables to join |
| **Regulators (FSS / NTS)** | Cross-system identity resolution across financial, tax, and procurement records for the same legal entity |
| **Foreign institutional investors** | Map DART corp_codes to KRX tickers for companies without English-language Bloomberg coverage |
| **Compliance / KYC teams** | BRN-based matching against KONEPS exclusion lists or sanctions databases |

---

## For Developers

### Programmatic access

Fetch directly from GitHub without cloning:

```python
import pandas as pd

df = pd.read_csv("https://raw.githubusercontent.com/pon00050/kr-company-registry/main/data/dist/kr_corp_ids.csv")
df = pd.read_parquet("https://raw.githubusercontent.com/pon00050/kr-company-registry/main/data/dist/kr_corp_ids.parquet")
```

### Common lookups

```python
import pandas as pd

df = pd.read_parquet("data/dist/kr_corp_ids.parquet")

# By ticker
df[df["ticker"] == "005930"]                          # Samsung Electronics

# By corp_code
df[df["corp_code"] == "00126380"]

# All KOSDAQ companies with BRN (excludes foreign-listed)
df[(df["market"] == "KOSDAQ") & (~df["ticker"].str.startswith("9"))]
```

```sql
-- DuckDB: join DART disclosures to KONEPS procurement records
SELECT c.corp_name, c.ticker, c.bizr_no, k.contract_amount
FROM 'data/dist/kr_corp_ids.parquet' c
JOIN 'koneps_contracts.parquet' k ON c.bizr_no = k.bizr_no
WHERE c.market = 'KOSDAQ'
ORDER BY k.contract_amount DESC;
```

### Running the extractor

```bash
git clone https://github.com/pon00050/kr-company-registry.git
cd kr-company-registry
cp .env.example .env        # add your DART_API_KEY
uv sync

uv run python src/kr_company_registry/build_crosswalk.py --sample 10  # smoke test
uv run python src/kr_company_registry/build_crosswalk.py               # full run (~90 min first time, ~10s from cache)
uv run python src/kr_company_registry/validate.py
uv run pytest tests/
```

| Flag | Default | Description |
|---|---|---|
| `--sample N` | None | Process only the first N companies |
| `--sleep S` | 0.5 | Seconds between DART API calls |
| `--force` | False | Re-fetch from DART even if cache exists |

DART API responses are cached under `data/raw/dart/<corp_code>.json` (gitignored).
A free DART API key is required to run the extractor — instant registration at
[opendart.fss.or.kr](https://opendart.fss.or.kr/intro/main.do).

### Data sources

| Identifier | Source | Endpoint |
|---|---|---|
| `corp_code`, `corp_name`, `bizr_no`, `jurir_no`, `corp_cls` | [DART](https://opendart.fss.or.kr) | `company.json` via [OpenDartReader](https://github.com/FinanceData/OpenDartReader) |
| `ticker`, market listing status | DART `corpCode.xml` | Same library |

`company.json` returns 20 fields per company; no field-selection parameter exists.
Raw responses are cached locally and never committed. Published output contains
only the 9 columns above.

### Relationship to krff-shell

This project is the infrastructure layer consumed by
[krff-shell](https://github.com/pon00050/krff-shell) at Phase 5, when the forensic
pipeline joins DART anomaly signals to KONEPS procurement and customs records via
BRN and CRN. It is maintained separately so it is useful to researchers and journalists
who have no interest in forensic scoring, and citable as a standalone open data release.

---

## License

**MIT.** Data extracted from DART is subject to FSS terms of service (public disclosure
data; generally permissive for research and information purposes).

---

## Contributing

Issues and pull requests welcome. If you find a BRN or CRN that looks wrong — wrong
length, clearly a different company — open an issue with the `corp_code` and what you
found in the DART portal.
