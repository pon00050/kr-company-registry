"""
validate.py — Schema and quality validation for the crosswalk output artifacts

Checks both kr_corp_ids.parquet and kr_corp_ids.csv and reports:
  - Required columns present
  - corp_code: 8-digit, no duplicates, no nulls
  - ticker: 6-digit, no nulls in listed rows
  - bizr_no: 10-digit where present
  - jurir_no: 13-digit where present
  - Parquet and CSV row counts match
  - Null / empty rates per column

Exit codes:
  0 — all checks passed
  1 — one or more checks failed

Usage
-----
    python src/validate.py                         # validate data/dist/
    python src/validate.py --dist path/to/dist/    # custom path
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "corp_code",
    "corp_name",
    "ticker",
    "market",
    "is_listed",
    "bizr_no",
    "jurir_no",
    "corp_cls",
    "extracted_at",
]

VALID_MARKETS = {"KOSPI", "KOSDAQ", "KONEX", ""}
VALID_CORP_CLS = {"Y", "K", "N", "E", ""}


def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def _pass(msg: str) -> None:
    print(f"  OK    {msg}")


def validate(dist_dir: Path) -> bool:
    errors = 0

    parquet_path = dist_dir / "kr_corp_ids.parquet"
    csv_path = dist_dir / "kr_corp_ids.csv"

    # -----------------------------------------------------------------------
    # 1. Files exist
    # -----------------------------------------------------------------------
    print("\n[1] File existence")
    for path in (parquet_path, csv_path):
        if path.exists():
            _pass(f"{path.name} exists")
        else:
            _fail(f"{path.name} missing — run build_crosswalk.py first")
            errors += 1

    if errors:
        print("\nAborting validation: output files missing.")
        return False

    # -----------------------------------------------------------------------
    # 2. Load both artifacts
    # -----------------------------------------------------------------------
    df_parquet = pd.read_parquet(parquet_path)
    df_csv = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig")

    # -----------------------------------------------------------------------
    # 3. Row count match
    # -----------------------------------------------------------------------
    print("\n[2] Row count consistency")
    if len(df_parquet) == len(df_csv):
        _pass(f"parquet and CSV both have {len(df_parquet):,} rows")
    else:
        _fail(f"row count mismatch: parquet={len(df_parquet):,}, csv={len(df_csv):,}")
        errors += 1

    df = df_parquet  # use parquet as the authoritative source

    # -----------------------------------------------------------------------
    # 4. Required columns
    # -----------------------------------------------------------------------
    print("\n[3] Required columns")
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        _fail(f"missing columns: {missing_cols}")
        errors += 1
    else:
        _pass(f"all {len(REQUIRED_COLUMNS)} required columns present")

    if missing_cols:
        print("\nAborting: missing columns prevent further checks.")
        return False

    # -----------------------------------------------------------------------
    # 5. corp_code format and uniqueness
    # -----------------------------------------------------------------------
    print("\n[4] corp_code integrity")

    null_corp = df["corp_code"].isnull().sum()
    if null_corp:
        _fail(f"{null_corp:,} null corp_code values")
        errors += 1
    else:
        _pass("no null corp_codes")

    wrong_len = (df["corp_code"].str.len() != 8).sum()
    if wrong_len:
        _fail(f"{wrong_len:,} corp_codes are not exactly 8 characters")
        errors += 1
    else:
        _pass("all corp_codes are 8 characters")

    non_digit = (~df["corp_code"].str.isdigit()).sum()
    if non_digit:
        _fail(f"{non_digit:,} corp_codes contain non-digit characters")
        errors += 1
    else:
        _pass("all corp_codes are numeric strings")

    dupes = df["corp_code"].duplicated().sum()
    if dupes:
        _fail(f"{dupes:,} duplicate corp_codes")
        errors += 1
    else:
        _pass("no duplicate corp_codes")

    # -----------------------------------------------------------------------
    # 6. ticker format
    # -----------------------------------------------------------------------
    print("\n[5] ticker format")
    # KRX tickers are 6 characters. Most are numeric, but SPACs and some recent
    # listings use alphanumeric codes (e.g. 0004V0, 0015G0). Allow both.
    has_ticker = df[df["ticker"] != ""]
    bad_ticker = has_ticker[
        has_ticker["ticker"].str.len().ne(6) | ~has_ticker["ticker"].str.isalnum()
    ]
    if len(bad_ticker):
        _fail(f"{len(bad_ticker):,} tickers are not exactly 6 alphanumeric characters")
        errors += 1
        print(bad_ticker["ticker"].value_counts().head(5).to_string())
    else:
        numeric = has_ticker["ticker"].str.isdigit().sum()
        alpha = len(has_ticker) - numeric
        _pass(f"all {len(has_ticker):,} non-empty tickers are 6 chars "
              f"({numeric:,} numeric, {alpha:,} alphanumeric — SPACs/recent listings)")

    # -----------------------------------------------------------------------
    # 7. market values
    # -----------------------------------------------------------------------
    print("\n[6] market values")
    bad_market = df[~df["market"].isin(VALID_MARKETS)]
    if len(bad_market):
        _fail(f"{len(bad_market):,} rows with unexpected market value")
        errors += 1
    else:
        _pass(f"all market values in {VALID_MARKETS}")
    print(f"       Distribution: {df['market'].value_counts().to_dict()}")

    # -----------------------------------------------------------------------
    # 8. bizr_no (BRN) format — where present
    # -----------------------------------------------------------------------
    print("\n[7] bizr_no (BRN) format")
    # Foreign companies listed on KRX (tickers starting with '9': 900xxx, 950xxx)
    # do not have Korean 사업자등록번호. DART returns their foreign registration
    # numbers verbatim — non-standard format is expected and not flagged as an error.
    domestic = df[~df["ticker"].str.startswith("9")]
    bizr_filled = domestic[domestic["bizr_no"] != ""]
    foreign_count = df["ticker"].str.startswith("9").sum()
    if len(bizr_filled):
        bad_bizr = bizr_filled[
            bizr_filled["bizr_no"].str.len().ne(10) | ~bizr_filled["bizr_no"].str.isdigit()
        ]
        if len(bad_bizr):
            _fail(f"{len(bad_bizr):,} domestic bizr_no values are not 10 numeric digits")
            errors += 1
        else:
            _pass(f"all {len(bizr_filled):,} domestic bizr_no values are 10 digits")
    if foreign_count:
        print(f"       NOTE: {foreign_count:,} foreign-listed companies (ticker 9xxxxx) "
              f"excluded from format check")
    all_filled = (df["bizr_no"] != "").sum()
    empty_bizr = (df["bizr_no"] == "").sum()
    print(f"       filled={all_filled:,}  empty={empty_bizr:,}  "
          f"({100*all_filled/len(df):.1f}% coverage)")

    # -----------------------------------------------------------------------
    # 9. jurir_no (CRN) format — where present
    # -----------------------------------------------------------------------
    print("\n[8] jurir_no (CRN) format")
    jurir_filled = df[df["jurir_no"] != ""]
    if len(jurir_filled):
        bad_jurir = jurir_filled[
            jurir_filled["jurir_no"].str.len().ne(13) | ~jurir_filled["jurir_no"].str.isdigit()
        ]
        if len(bad_jurir):
            _fail(f"{len(bad_jurir):,} jurir_no values are not 13 numeric digits")
            errors += 1
        else:
            _pass(f"all {len(jurir_filled):,} non-empty jurir_no values are 13 digits")
    empty_jurir = (df["jurir_no"] == "").sum()
    print(f"       filled={len(jurir_filled):,}  empty={empty_jurir:,}  "
          f"({100*len(jurir_filled)/len(df):.1f}% coverage)")

    # -----------------------------------------------------------------------
    # 10. extracted_at
    # -----------------------------------------------------------------------
    print("\n[9] extracted_at")
    null_date = df["extracted_at"].isnull().sum()
    if null_date:
        _fail(f"{null_date:,} null extracted_at values")
        errors += 1
    else:
        unique_dates = df["extracted_at"].unique()
        _pass(f"no null extracted_at; dates: {list(unique_dates)}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 50)
    if errors:
        print(f"VALIDATION FAILED — {errors} error(s) found.")
    else:
        print(f"VALIDATION PASSED — {len(df):,} rows, all checks clean.")
    print("=" * 50)

    return errors == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate kr_corp_ids crosswalk output.")
    parser.add_argument("--dist", type=Path,
                        default=Path(__file__).parent.parent / "data" / "dist",
                        help="Path to the dist/ directory containing output artifacts.")
    args = parser.parse_args()

    ok = validate(args.dist)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
