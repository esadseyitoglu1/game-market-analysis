"""Cleans raw Kaggle CSV data from data/raw/ and writes analysis-ready CSVs to data/processed/.

Dataset source: artermiloff/steam-games-dataset (Kaggle)
  - games_march2025_cleaned.csv  → 90k+ games, March 2025 snapshot
  - games_may2024_cleaned.csv    → ~80k games, May 2024 snapshot (for trend analysis)

Key columns we care about:
  appid, name, release_date, price, genres, tags, developers, publishers,
  positive, negative, estimated_owners, pct_pos_total, num_reviews_total,
  average_playtime_forever, peak_ccu, windows, mac, linux
"""

from pathlib import Path

import ast
import logging
import pandas as pd

log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# Columns we actually need downstream — drop everything else to save RAM
KEEP_COLS = [
    "appid",
    "name",
    "release_date",
    "price",
    "genres",
    "tags",
    "developers",
    "publishers",
    "categories",
    "positive",
    "negative",
    "estimated_owners",
    "pct_pos_total",
    "num_reviews_total",
    "pct_pos_recent",
    "num_reviews_recent",
    "average_playtime_forever",
    "median_playtime_forever",
    "peak_ccu",
    "dlc_count",
    "achievements",
    "recommendations",
    "metacritic_score",
    "windows",
    "mac",
    "linux",
    "discount",
    "required_age",
    "short_description",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_list_col(series: pd.Series) -> pd.Series:
    """Safely parse a column that contains Python-literal lists/dicts stored as strings.

    Steam datasets often store genres/tags as stringified Python literals like:
        "['Action', 'Indie']"  or  "{'Action': 1234, 'Indie': 567}"
    We convert them to actual Python objects so downstream code can filter on them.
    """
    def _safe_eval(val):
        if pd.isna(val):
            return []
        try:
            result = ast.literal_eval(str(val))
            # Tags come as dicts {tag: vote_count} — return just the keys
            if isinstance(result, dict):
                return list(result.keys())
            return result if isinstance(result, list) else []
        except (ValueError, SyntaxError):
            return []

    return series.apply(_safe_eval)


def _parse_estimated_owners(series: pd.Series) -> pd.Series:
    """Convert 'X - Y' owner range strings to the midpoint integer.

    SteamSpy returns strings like '1000000 - 2000000'. We take the midpoint
    so the column becomes a numeric we can sort/correlate on.
    """
    def _midpoint(val):
        if pd.isna(val):
            return None
        try:
            parts = str(val).split(" - ")
            if len(parts) == 2:
                low, high = int(parts[0].replace(",", "")), int(parts[1].replace(",", ""))
                return (low + high) // 2
            return int(str(val).replace(",", ""))
        except ValueError:
            return None

    return series.apply(_midpoint)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_app_list(raw_path: str | Path) -> pd.DataFrame:
    """Load a Kaggle Steam CSV, keep relevant columns, and clean/normalize them.

    Steps:
    1. Load only the columns we need (saves RAM on 450+ MB files).
    2. Drop rows with no name or appid.
    3. Parse release_date to datetime.
    4. Parse genres/tags/categories from string literals to Python lists.
    5. Convert estimated_owners range string to numeric midpoint.
    6. Compute review_score = positive / (positive + negative).
    7. Ensure price is float (free games → 0.0).

    Returns a cleaned DataFrame ready for analyzer.py.
    """
    raw_path = Path(raw_path)
    log.info(f"Loading {raw_path.name} ...")

    # Read only the columns that exist in the file (guard against schema changes).
    # Normalize to lowercase first — may2024 uses 'AppID', march2025 uses 'appid'.
    raw_header = pd.read_csv(raw_path, nrows=0).columns.tolist()
    rename_map = {c: c.lower() for c in raw_header}          # {'AppID': 'appid', ...}
    available_lower = [c.lower() for c in raw_header]        # lowercase names
    cols_to_load_orig = [c for c in raw_header if c.lower() in KEEP_COLS]

    df = pd.read_csv(raw_path, usecols=cols_to_load_orig, low_memory=False)
    df.rename(columns=rename_map, inplace=True)              # unify to lowercase
    log.info(f"  Loaded {len(df):,} rows x {len(df.columns)} columns")

    # --- 1. Drop rows missing critical identifiers ---
    df = df.dropna(subset=["appid", "name"])
    df["appid"] = df["appid"].astype(int)

    # --- 2. Parse release_date ---
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"] = df["release_date"].dt.year.astype("Int64")

    # --- 3. Parse list/dict columns ---
    for col in ["genres", "tags", "categories"]:
        if col in df.columns:
            df[col] = _parse_list_col(df[col])

    # --- 4. Estimated owners → numeric midpoint ---
    if "estimated_owners" in df.columns:
        df["estimated_owners_mid"] = _parse_estimated_owners(df["estimated_owners"])

    # --- 5. Review score (0–100 scale, NaN if no reviews) ---
    if "positive" in df.columns and "negative" in df.columns:
        total = df["positive"] + df["negative"]
        df["review_score"] = (df["positive"] / total.replace(0, float("nan")) * 100).round(1)

    # --- 6. Price sanity check ---
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)

    log.info(f"After cleaning: {len(df):,} rows")
    return df


def filter_by_genre(df: pd.DataFrame, genre: str) -> pd.DataFrame:
    """Return only rows where `genre` appears in the parsed genres list.

    Example:
        shooter_df = filter_by_genre(df, 'Action')
        tds_df = filter_by_genre(df, 'Top-Down Shooter')  # tag-based
    """
    mask = df["genres"].apply(lambda g: genre in g if isinstance(g, list) else False)
    return df[mask].copy()


def filter_by_tag(df: pd.DataFrame, tag: str) -> pd.DataFrame:
    """Return only rows where `tag` appears in the parsed tags list.

    Tags are more granular than genres — use this to find niche categories
    like 'Top-Down Shooter', 'Roguelite', '2D', etc.
    """
    mask = df["tags"].apply(lambda t: tag in t if isinstance(t, list) else False)
    return df[mask].copy()


def save_processed(df: pd.DataFrame, filename: str) -> Path:
    """Write a cleaned DataFrame to data/processed/<filename>.

    We save as CSV (not parquet) to keep things simple and inspectable in Excel.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / filename
    df.to_csv(output_path, index=False)
    log.info(f"Saved -> {output_path}  ({len(df):,} rows)")
    return output_path


def run_pipeline(snapshot: str = "march2025") -> dict[str, Path]:
    """End-to-end pipeline: clean one or both snapshots and save to processed/.

    Args:
        snapshot: 'march2025', 'may2024', or 'both'

    Returns:
        Dict mapping snapshot name to output CSV path.
    """
    snapshots = {
        "march2025": "games_march2025_cleaned.csv",
        "may2024":   "games_may2024_cleaned.csv",
    }

    targets = snapshots if snapshot == "both" else {snapshot: snapshots[snapshot]}
    results = {}

    for name, filename in targets.items():
        raw_path = RAW_DIR / filename
        if not raw_path.exists():
            log.warning(f"[SKIP] {filename} not found in data/raw/")
            continue

        df = clean_app_list(raw_path)
        out_path = save_processed(df, f"steam_games_{name}.csv")
        results[name] = out_path

    return results
