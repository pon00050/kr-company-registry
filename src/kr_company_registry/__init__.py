"""
kr-company-registry — Open identifier crosswalk for Korean listed companies.

Public API
----------
load_crosswalk() -> pd.DataFrame
    Returns the full DART ↔ KRX ↔ BRN ↔ CRN crosswalk (~3,900 companies).

lookup(query, by="name") -> pd.DataFrame
    Find companies by name substring, ticker, corp_code, bizr_no, or jurir_no.

REQUIRED_COLUMNS, VALID_MARKETS, PARQUET_FILENAME
    Schema constants.
"""

from __future__ import annotations

import pandas as pd

from kr_company_registry._paths import DATA_DIST
from kr_company_registry.constants import (
    PARQUET_FILENAME,
    REQUIRED_COLUMNS,
    VALID_MARKETS,
)

__all__ = [
    "load_crosswalk",
    "lookup",
    "REQUIRED_COLUMNS",
    "VALID_MARKETS",
    "PARQUET_FILENAME",
]

_CROSSWALK_PATH = DATA_DIST / PARQUET_FILENAME


def load_crosswalk() -> pd.DataFrame:
    """Load the DART ↔ KRX ↔ BRN ↔ CRN crosswalk as a DataFrame.

    Returns
    -------
    pd.DataFrame
        Columns: corp_code, corp_name, ticker, market, is_listed,
                 bizr_no, jurir_no, corp_cls, extracted_at
        ~3,900 rows (active + delisted companies with KRX tickers).

    Raises
    ------
    FileNotFoundError
        If the crosswalk parquet has not been built yet.
        Run: python -m kr_company_registry.build_crosswalk
    """
    if not _CROSSWALK_PATH.exists():
        raise FileNotFoundError(
            f"Crosswalk not found at {_CROSSWALK_PATH}. "
            "Run: python -m kr_company_registry.build_crosswalk"
        )
    return pd.read_parquet(_CROSSWALK_PATH)


def lookup(query: str, by: str = "name") -> pd.DataFrame:
    """Find companies by a single field value.

    Parameters
    ----------
    query : str
        Value to search for.
    by : str
        Field to search. One of:
        - "name"      — substring match on corp_name (case-insensitive)
        - "ticker"    — exact 6-digit KRX ticker
        - "corp_code" — exact 8-digit DART corp_code
        - "bizr_no"   — exact 10-digit business registration number
        - "jurir_no"  — exact 13-digit corporate registration number

    Returns
    -------
    pd.DataFrame
        Matching rows, or empty DataFrame if none found.

    Examples
    --------
    >>> lookup("삼성전자", by="name")
    >>> lookup("005930", by="ticker")
    >>> lookup("00126380", by="corp_code")
    """
    df = load_crosswalk()

    if by == "name":
        mask = df["corp_name"].str.contains(query, case=False, na=False)
    elif by in ("ticker", "corp_code", "bizr_no", "jurir_no"):
        mask = df[by] == query
    else:
        raise ValueError(
            f"Unknown field '{by}'. Choose from: name, ticker, corp_code, bizr_no, jurir_no"
        )

    return df[mask].reset_index(drop=True)
