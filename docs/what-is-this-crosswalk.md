# What Is This Crosswalk?

The kr-company-registry is an open identifier crosswalk linking five company identifiers
maintained in separate Korean government silos. No equivalent public table exists; commercial
vendors (FnGuide, KOSCOM, Bloomberg) hold internal versions as proprietary IP.

## The Five Identifiers

| Field | Format | Authority |
|---|---|---|
| `corp_code` | 8-digit zero-padded | FSS / DART (금융감독원) |
| `ticker` | 6-char alphanumeric | KRX (한국거래소) |
| `bizr_no` | 10-digit BRN | NTS (국세청, 사업자등록번호) |
| `jurir_no` | 13-digit CRN | Ministry of Justice (법인등록번호) |
| `market` | KOSPI / KOSDAQ / KONEX | KRX / DART |

## Why It Matters

- DART is the only public source that collocates all five identifiers in one API call.
- Without this crosswalk, joining procurement data (KONEPS, indexed by BRN) to securities
  filings (DART, indexed by corp_code) requires a proprietary lookup table.
- This crosswalk enables that join for all currently listed and delisted companies tracked by DART.

## Population

Numbers reflect the current `data/dist/` artifact; updated weekly by GitHub Actions.

- 115,421 total corps in DART; ~3,949 have a non-empty `stock_code` (i.e., ever listed)
- Active listed (KOSPI + KOSDAQ + KONEX): 2,768 — KOSPI 841 · KOSDAQ 1,817 · KONEX 110
- Delisted (`corp_cls=E`): 1,181

Check `extracted_at` in the parquet for the date of the most recent extraction run.
