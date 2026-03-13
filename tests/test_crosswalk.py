"""
test_crosswalk.py — Schema and quality tests for kr_corp_ids output

These tests are designed to run in CI against the committed dist/ artifacts.
They enforce the schema contract so that any consumer of the crosswalk can
rely on stable column names, formats, and coverage guarantees.

Run:
    pytest tests/
"""

import io
from pathlib import Path

import pandas as pd
import pytest

from src.constants import (
    CSV_FILENAME,
    PARQUET_FILENAME,
    REQUIRED_COLUMNS,
    VALID_CORP_CLS,
    VALID_MARKETS,
)

DIST = Path(__file__).parent.parent / "data" / "dist"
PARQUET = DIST / PARQUET_FILENAME
CSV = DIST / CSV_FILENAME


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df():
    if not PARQUET.exists():
        pytest.skip("kr_corp_ids.parquet not found — run build_crosswalk.py first")
    return pd.read_parquet(PARQUET)


@pytest.fixture(scope="module")
def df_csv():
    if not CSV.exists():
        pytest.skip("kr_corp_ids.csv not found — run build_crosswalk.py first")
    return pd.read_csv(CSV, dtype=str, encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

def test_parquet_exists():
    assert PARQUET.exists(), (
        "kr_corp_ids.parquet not found. Run: python src/build_crosswalk.py"
    )


def test_csv_exists():
    assert CSV.exists(), (
        "kr_corp_ids.csv not found. Run: python src/build_crosswalk.py"
    )


# ---------------------------------------------------------------------------
# Row count consistency
# ---------------------------------------------------------------------------

def test_parquet_csv_row_count_match(df, df_csv):
    assert len(df) == len(df_csv), (
        f"parquet has {len(df):,} rows but CSV has {len(df_csv):,} rows"
    )


def test_minimum_row_count(df):
    # Skip this check when the file is clearly a --sample run (< 100 rows).
    # The full run produces ~3,900 rows (active + delisted); enforce ≥ 1,000.
    if len(df) < 100:
        pytest.skip(f"Sample run detected ({len(df)} rows) — skipping minimum row count check")
    assert len(df) >= 1_000, (
        f"Only {len(df):,} rows — expected at least 1,000 companies"
    )


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_required_columns_present(df):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    assert not missing, f"Missing columns: {missing}"


# ---------------------------------------------------------------------------
# corp_code
# ---------------------------------------------------------------------------

def test_corp_code_no_nulls(df):
    null_count = df["corp_code"].isnull().sum()
    assert null_count == 0, f"{null_count:,} null corp_codes"


def test_corp_code_is_8_digits(df):
    bad = df[
        df["corp_code"].str.len().ne(8) | ~df["corp_code"].str.isdigit()
    ]
    assert len(bad) == 0, (
        f"{len(bad):,} corp_codes are not exactly 8 numeric digits:\n"
        f"{bad['corp_code'].head(5).tolist()}"
    )


def test_corp_code_no_duplicates(df):
    dupes = df["corp_code"].duplicated().sum()
    assert dupes == 0, f"{dupes:,} duplicate corp_code values"


# ---------------------------------------------------------------------------
# ticker
# ---------------------------------------------------------------------------

def test_ticker_format_where_present(df):
    # KRX tickers are 6 characters. Most are numeric, but SPACs and some recent
    # listings use alphanumeric codes (e.g. 0004V0, 0015G0). Allow both.
    has_ticker = df[df["ticker"] != ""]
    bad = has_ticker[
        has_ticker["ticker"].str.len().ne(6) | ~has_ticker["ticker"].str.isalnum()
    ]
    assert len(bad) == 0, (
        f"{len(bad):,} non-empty tickers are not 6 alphanumeric characters:\n"
        f"{bad['ticker'].head(5).tolist()}"
    )


# ---------------------------------------------------------------------------
# market
# ---------------------------------------------------------------------------

def test_market_values_valid(df):
    bad = df[~df["market"].isin(VALID_MARKETS)]
    assert len(bad) == 0, (
        f"{len(bad):,} rows with unexpected market value:\n"
        f"{bad['market'].value_counts().to_dict()}"
    )


def test_market_distribution_plausible(df):
    if len(df) < 100:
        pytest.skip(f"Sample run detected ({len(df)} rows) — skipping market distribution check")
    counts = df["market"].value_counts().to_dict()
    assert counts.get("KOSDAQ", 0) >= 100, (
        f"Unexpectedly few KOSDAQ companies: {counts}"
    )
    assert counts.get("KOSPI", 0) >= 50, (
        f"Unexpectedly few KOSPI companies: {counts}"
    )


# ---------------------------------------------------------------------------
# bizr_no (BRN)
# ---------------------------------------------------------------------------

def test_bizr_no_format_where_present(df):
    # Foreign companies listed on KRX do not have Korean 사업자등록번호.
    # KRX assigns tickers starting with '9' (900xxx, 950xxx) to foreign-incorporated
    # companies. Exclude them from the format check — their DART bizr_no entries
    # contain foreign registration numbers in non-standard formats.
    domestic = df[~df["ticker"].str.startswith("9")]
    filled = domestic[domestic["bizr_no"] != ""]
    if len(filled) == 0:
        pytest.skip("No domestic bizr_no values present — skipping format check")
    bad = filled[
        filled["bizr_no"].str.len().ne(10) | ~filled["bizr_no"].str.isdigit()
    ]
    assert len(bad) == 0, (
        f"{len(bad):,} domestic bizr_no values are not 10 numeric digits:\n"
        f"{bad['bizr_no'].head(5).tolist()}"
    )


def test_bizr_no_coverage_meaningful(df):
    filled_pct = (df["bizr_no"] != "").mean() * 100
    # DART company.json should return BRN for the overwhelming majority of companies.
    # If coverage drops below 50%, something is wrong with the extraction.
    assert filled_pct >= 50, (
        f"bizr_no coverage is only {filled_pct:.1f}% — expected ≥50%"
    )


# ---------------------------------------------------------------------------
# jurir_no (CRN)
# ---------------------------------------------------------------------------

def test_jurir_no_format_where_present(df):
    filled = df[df["jurir_no"] != ""]
    if len(filled) == 0:
        pytest.skip("No jurir_no values present — skipping format check")
    bad = filled[
        filled["jurir_no"].str.len().ne(13) | ~filled["jurir_no"].str.isdigit()
    ]
    assert len(bad) == 0, (
        f"{len(bad):,} jurir_no values are not 13 numeric digits:\n"
        f"{bad['jurir_no'].head(5).tolist()}"
    )


def test_jurir_no_coverage_meaningful(df):
    filled_pct = (df["jurir_no"] != "").mean() * 100
    assert filled_pct >= 50, (
        f"jurir_no coverage is only {filled_pct:.1f}% — expected ≥50%"
    )


# ---------------------------------------------------------------------------
# extracted_at
# ---------------------------------------------------------------------------

def test_extracted_at_no_nulls(df):
    null_count = df["extracted_at"].isnull().sum()
    assert null_count == 0, f"{null_count:,} null extracted_at values"


def test_extracted_at_is_iso_date(df):
    try:
        pd.to_datetime(df["extracted_at"], format="%Y-%m-%d")
    except Exception as exc:
        pytest.fail(f"extracted_at contains non-ISO-date values: {exc}")


# ---------------------------------------------------------------------------
# CSV encoding
# ---------------------------------------------------------------------------

def test_csv_utf8_sig_readable(df_csv):
    # Korean company names must survive the CSV round-trip
    assert "corp_name" in df_csv.columns
    # Check that at least one row contains a Korean character
    has_korean = df_csv["corp_name"].str.contains("[가-힣]", regex=True).any()
    assert has_korean, "No Korean characters found in corp_name — encoding may be broken"
