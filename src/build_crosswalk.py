"""
build_crosswalk.py — Korean company identifier crosswalk builder

Extracts a five-identifier table for ALL companies that have ever had a KRX ticker
(actively listed + delisted) from DART's company.json endpoint and writes two artifacts:

    data/dist/kr_corp_ids.parquet   — columnar; for programmatic use
    data/dist/kr_corp_ids.csv       — CSV; for human review and git-clonable access

Coverage: ~3,900 companies (currently ~1,700 active + ~2,200 delisted).
Delisted companies are included because investigative and historical research requires
looking up companies that no longer trade.

Output schema
-------------
corp_code    str   8-digit zero-padded DART identifier (permanent)
corp_name    str   Korean legal name (as registered in DART)
ticker       str   6-digit KRX ticker (persists in DART after delisting)
market       str   KOSPI | KOSDAQ | KONEX | "" (empty = corp_cls E / other)
is_listed    bool  True if corp_cls in (Y, K, N) — actively traded as of extraction
bizr_no      str   BRN (사업자등록번호): 10-digit, no hyphens
jurir_no     str   CRN (법인등록번호): 13-digit, no hyphens
corp_cls     str   Raw DART corp_cls: Y=KOSPI, K=KOSDAQ, N=KONEX, E=ETC/delisted
extracted_at str   ISO date of extraction run (YYYY-MM-DD)

Usage
-----
    python src/build_crosswalk.py                  # all ~3,900 companies (~92 min first run)
    python src/build_crosswalk.py --sample 10      # smoke test (10 companies, ~14s)
    python src/build_crosswalk.py --sleep 0.3      # faster (watch rate limits)
    python src/build_crosswalk.py --force          # re-fetch even if cached

Rate limits
-----------
DART allows ~20,000 API calls/day. Design for ≤10,000/day.
Default sleep between calls: 0.5s → ~1,700 companies ≈ 14 minutes.
Responses are cached under data/raw/dart/<corp_code>.json.
Re-runs from cache complete in ~10 seconds.
"""

import argparse
import json
import logging
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from src.constants import CSV_FILENAME, PARQUET_FILENAME
from src._paths import PROJECT_ROOT as ROOT, DATA_RAW_DART as RAW_DART, DATA_DIST as DIST

# ---------------------------------------------------------------------------
# DART corp_cls → human-readable market name
# ---------------------------------------------------------------------------
MARKET_MAP = {
    "Y": "KOSPI",
    "K": "KOSDAQ",
    "N": "KONEX",
    "E": "",   # unlisted / ETC
}

# ---------------------------------------------------------------------------
# DART status codes
# ---------------------------------------------------------------------------
DART_STATUS_OK = "000"
DART_STATUS_NOT_FOUND = "013"
DART_STATUS_RATE_LIMIT = "020"


def _load_api_key() -> str:
    load_dotenv()
    key = os.getenv("DART_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "DART_API_KEY not set. Copy .env.example → .env and fill in your key."
        )
    return key


def _fetch_corp_list(dart) -> pd.DataFrame:
    """Return DART's full corp list as a DataFrame.

    Columns: corp_code (str), corp_name (str), stock_code (str), modify_date (str)
    stock_code is the 6-digit KRX ticker, or '' for unlisted companies.
    """
    logging.info("Fetching DART corp list (corpCode.xml)…")
    df = dart.corp_codes
    df["corp_code"] = df["corp_code"].astype(str).str.zfill(8)
    df["stock_code"] = df["stock_code"].fillna("").astype(str).str.strip()
    logging.info(f"  {len(df):,} total corps; {(df['stock_code'] != '').sum():,} have a ticker")
    return df


def _load_cached(corp_code: str) -> dict | None:
    cache_file = RAW_DART / f"{corp_code}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache_file.unlink()  # corrupt cache — delete and re-fetch
    return None


def _save_cache(corp_code: str, data: dict) -> None:
    RAW_DART.mkdir(parents=True, exist_ok=True)
    cache_file = RAW_DART / f"{corp_code}.json"
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_company_detail(dart, corp_code: str, sleep: float, force: bool) -> dict:
    """Call company.json for one corp_code, with disk caching and backoff."""
    if not force:
        cached = _load_cached(corp_code)
        if cached is not None:
            return cached

    for attempt in range(3):
        try:
            result = dart.company(corp_code)
            if result is None:
                return {}
            # OpenDartReader returns a pandas Series; convert to dict
            if hasattr(result, "to_dict"):
                result = result.to_dict()
            status = str(result.get("status", DART_STATUS_OK))
            if status == DART_STATUS_NOT_FOUND:
                return {}
            if status == DART_STATUS_RATE_LIMIT:
                wait = 60 * (attempt + 1)
                logging.warning(f"  Rate limit hit for {corp_code}. Waiting {wait}s…")
                time.sleep(wait)
                continue
            _save_cache(corp_code, result)
            time.sleep(sleep)
            return result
        except Exception as exc:
            logging.warning(f"  Attempt {attempt + 1} failed for {corp_code}: {exc}")
            time.sleep(5)

    logging.error(f"  All retries failed for {corp_code}. Skipping.")
    return {}


def build(sample: int | None = None, sleep: float = 0.5, force: bool = False) -> pd.DataFrame:
    """Build the crosswalk DataFrame.

    Parameters
    ----------
    sample : int | None
        If set, only process the first N listed companies (for smoke testing).
    sleep : float
        Seconds to wait between DART API calls.
    force : bool
        If True, re-fetch from DART even if a cache file exists.

    Returns
    -------
    pd.DataFrame with schema described in module docstring.
    """
    import OpenDartReader  # lazy import — blocks on network at import time

    api_key = _load_api_key()
    dart = OpenDartReader(api_key)

    corp_list = _fetch_corp_list(dart)

    # Process all companies that have ever had a KRX ticker (active + delisted)
    listed = corp_list[corp_list["stock_code"] != ""].copy()
    if sample:
        listed = listed.head(sample)
        logging.info(f"Sample mode: processing {len(listed)} companies.")

    rows = []
    today = date.today().isoformat()

    for _, row in tqdm(listed.iterrows(), total=len(listed), desc="Fetching company details"):
        corp_code = row["corp_code"]
        detail = _fetch_company_detail(dart, corp_code, sleep=sleep, force=force)

        bizr_no = str(detail.get("bizr_no", "") or "").replace("-", "").strip()
        jurir_no = str(detail.get("jurir_no", "") or "").replace("-", "").strip()
        corp_cls = str(detail.get("corp_cls", "") or "").strip().upper()

        rows.append({
            "corp_code": corp_code,
            "corp_name": str(row.get("corp_name", "") or "").strip(),
            "ticker": str(row["stock_code"]).strip(),
            "market": MARKET_MAP.get(corp_cls, ""),
            "is_listed": corp_cls in ("Y", "K", "N"),
            "bizr_no": bizr_no,
            "jurir_no": jurir_no,
            "corp_cls": corp_cls,
            "extracted_at": today,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("corp_code").reset_index(drop=True)
    return df


def write_outputs(df: pd.DataFrame) -> None:
    DIST.mkdir(parents=True, exist_ok=True)

    parquet_path = DIST / PARQUET_FILENAME
    csv_path = DIST / CSV_FILENAME

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compatibility

    logging.info(f"Written: {parquet_path}  ({len(df):,} rows)")
    logging.info(f"Written: {csv_path}  ({len(df):,} rows)")

    # Quick null summary
    null_rates = df.isnull().mean().mul(100).round(1)
    empty_rates = (df == "").mean().mul(100).round(1)
    print("\n--- Null / empty rates ---")
    for col in df.columns:
        n = null_rates[col]
        e = empty_rates.get(col, 0.0)
        if n > 0 or e > 0:
            print(f"  {col:15s}  null={n:.1f}%  empty={e:.1f}%")
    print(f"\nTotal rows: {len(df):,}")
    bizr_filled = (df["bizr_no"] != "").sum()
    jurir_filled = (df["jurir_no"] != "").sum()
    print(f"bizr_no filled: {bizr_filled:,} / {len(df):,}")
    print(f"jurir_no filled: {jurir_filled:,} / {len(df):,}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="Build the Korean company identifier crosswalk.")
    parser.add_argument("--sample", type=int, default=None,
                        help="Process only the first N listed companies (smoke test).")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Seconds between DART API calls (default: 0.5).")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch from DART even if cache exists.")
    args = parser.parse_args()

    df = build(sample=args.sample, sleep=args.sleep, force=args.force)
    write_outputs(df)


if __name__ == "__main__":
    main()
