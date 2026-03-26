"""
constants.py — Shared contract literals for kr-company-registry

Single source of truth for column names, valid value sets, and output filenames.
Import from here; never redeclare these literals in other modules.
"""

PARQUET_FILENAME = "kr_corp_ids.parquet"
CSV_FILENAME = "kr_corp_ids.csv"

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
