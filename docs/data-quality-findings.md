# Data Quality Findings

Findings from the v1.0.0 extraction run (2026-03-09, 3,948 companies) confirmed in
subsequent weekly refreshes. Numbers reflect the current `data/dist/` artifact.

## Foreign-Listed Companies (~39)

KRX lists ~39 foreign-incorporated companies in ticker range `900xxx`–`950xxx`.
Their `bizr_no` field in DART contains foreign registration numbers — non-Korean format,
non-10-digit. This is expected and not a data error.

**Consequence:** always exclude with `df[~df["ticker"].str.startswith("9")]` before any
BRN format validation or BRN-keyed join.

## Alphanumeric Tickers (SPACs, ~36)

SPACs and some recent listings have alphanumeric 6-character tickers (e.g. `0004V0`, `0015G0`).
KRX encodes the SPAC structure into the ticker string.

**Consequence:** validate tickers with `str.isalnum()`, NOT `str.isdigit()`. Any pipeline
that strips or rejects non-numeric tickers will silently lose ~36 companies.

## BRN Coverage

- 100% of domestic companies have a non-empty `bizr_no`
- Foreign-listed companies have non-standard entries (see above)

## CRN Coverage

- ~99% coverage overall
- ~1% empty: foreign-incorporated companies that have no Korean 법인등록번호
- These are a subset of (but not identical to) the foreign-listed group above

## Delisted Companies

`corp_cls=E` marks delisted companies. DART retains their records indefinitely.
1,181 of the ~3,949 rows are delisted. `is_listed` flag is False for these.
Their `market` field is empty string.
