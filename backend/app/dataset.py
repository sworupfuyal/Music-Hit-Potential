"""Aggregate statistics over the training dataset for the Dataset Explorer.

The raw CSV is 7.5 MB, so it is loaded once and cached by mtime (same approach as
`bundle.py`). Every endpoint returns pre-aggregated numbers — bins, correlations,
group counts — so the browser never receives 29k raw rows.
"""

import math
import threading
from datetime import datetime

import numpy as np
import pandas as pd

from .bundle import safe_float
from .paths import DATA_PATH
from .training import LEAKAGE_COLUMNS

_lock = threading.Lock()
_cache: pd.DataFrame | None = None
_cache_mtime: float | None = None

# Candidate genre-ish columns, cheapest (lowest cardinality) first.
GENRE_COLUMNS = ("playlist_genre", "playlist_subgenre", "genre", "spotify_genre")


def dataset_available() -> bool:
    return DATA_PATH.exists()


def get_dataframe() -> pd.DataFrame:
    """Return the cached dataset with lower-cased columns, reloading if it changed."""
    global _cache, _cache_mtime

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    mtime = DATA_PATH.stat().st_mtime
    with _lock:
        if _cache is None or _cache_mtime != mtime:
            frame = pd.read_csv(DATA_PATH, low_memory=False)
            frame.columns = [c.lower() for c in frame.columns]
            _cache = frame
            _cache_mtime = mtime
        return _cache


def _numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    """Numeric columns the model is allowed to see (leakage columns removed)."""
    return [
        c
        for c in df.select_dtypes(include=["number"]).columns
        if c not in LEAKAGE_COLUMNS
    ]


def _parsed_dates(df: pd.DataFrame) -> pd.Series | None:
    if "first_week" not in df.columns:
        return None
    return pd.to_datetime(df["first_week"], errors="coerce", format="mixed")


def summary() -> dict:
    """Shape, class balance, missingness and data-quality flags."""
    df = get_dataframe()
    n_rows = int(len(df))

    hit_counts = df["hit"].value_counts() if "hit" in df.columns else pd.Series(dtype=int)
    n_hits = int(hit_counts.get(1, 0))
    n_flops = int(hit_counts.get(0, 0))

    missing = {
        col: int(count)
        for col, count in df.isna().sum().items()
        if count > 0
    }
    # Worst offenders first — that ordering is the story.
    missing_top = dict(sorted(missing.items(), key=lambda kv: kv[1], reverse=True)[:12])

    quality: list[dict] = []

    dates = _parsed_dates(df)
    date_range = None
    if dates is not None:
        valid = dates.dropna()
        if len(valid):
            date_range = {"min": str(valid.min().date()), "max": str(valid.max().date())}
            future = int((valid > pd.Timestamp(datetime.now())).sum())
            if future:
                quality.append({
                    "severity": "serious",
                    "label": "Impossible release dates",
                    "detail": (
                        f"{future:,} rows ({future / n_rows:.0%}) have a first_week in the "
                        f"future, latest {valid.max().date()}. Training sorts on this column "
                        f"and takes the last 20% as the test set, so these rows would "
                        f"otherwise make up the holdout instead of genuinely recent "
                        f"releases. They are now excluded before the split by "
                        f"clean_dataset(); this panel reads the raw file, so the counts "
                        f"here describe the source data rather than what the model sees."
                    ),
                })
        unparsed = int(dates.isna().sum())
        if unparsed:
            quality.append({
                "severity": "warning",
                "label": "Unparseable dates",
                "detail": f"{unparsed:,} rows have a first_week that could not be parsed.",
            })

    # Audio features missing together is the single biggest gap in this dataset.
    audio_cols = [c for c in ("danceability", "energy", "loudness", "tempo") if c in df.columns]
    if audio_cols:
        all_missing = int(df[audio_cols].isna().all(axis=1).sum())
        if all_missing:
            quality.append({
                "severity": "serious",
                "label": "Rows with no audio features",
                "detail": (
                    f"{all_missing:,} rows ({all_missing / n_rows:.1%}) are missing every "
                    f"audio feature. Median imputation fills them, so those predictions "
                    f"rest on metadata alone."
                ),
            })

    duplicates = int(df.duplicated().sum())
    if duplicates:
        quality.append({
            "severity": "warning",
            "label": "Duplicate rows",
            "detail": f"{duplicates:,} fully duplicated rows.",
        })

    for col in GENRE_COLUMNS:
        if col in df.columns:
            distinct = int(df[col].nunique())
            coverage = float(df[col].notna().mean())
            if distinct > 500:
                quality.append({
                    "severity": "warning",
                    "label": f"High-cardinality `{col}`",
                    "detail": (
                        f"{distinct:,} distinct values (stored as stringified lists). "
                        f"One-hot encoding these is why genre combinations dominate the "
                        f"feature-importance chart."
                    ),
                })
            if coverage < 0.5:
                quality.append({
                    "severity": "warning",
                    "label": f"Sparse `{col}`",
                    "detail": f"Only {coverage:.0%} of rows have a value.",
                })

    return {
        "rows": n_rows,
        "columns": int(df.shape[1]),
        "hits": n_hits,
        "flops": n_flops,
        "hit_rate": safe_float(n_hits / n_rows) if n_rows else None,
        "numeric_features": _numeric_feature_columns(df),
        "date_range": date_range,
        "missing_top": missing_top,
        "missing_total": int(sum(missing.values())),
        "duplicates": duplicates,
        "quality": quality,
    }


def feature_distribution(feature: str, bins: int = 30) -> dict:
    """Shared-edge histogram of one numeric feature, split by hit vs flop."""
    df = get_dataframe()

    if feature not in df.columns:
        raise ValueError(f"Unknown feature: {feature}")
    if not pd.api.types.is_numeric_dtype(df[feature]):
        raise ValueError(f"Feature is not numeric: {feature}")

    series = df[feature]
    valid = series.dropna()
    if valid.empty:
        raise ValueError(f"Feature has no values: {feature}")

    bins = max(5, min(int(bins), 80))
    edges = np.histogram_bin_edges(valid, bins=bins)
    centers = ((edges[:-1] + edges[1:]) / 2).tolist()

    def counts_for(mask: pd.Series) -> list[int]:
        subset = series[mask].dropna()
        counts, _ = np.histogram(subset, bins=edges)
        return [int(c) for c in counts]

    has_label = "hit" in df.columns
    hit_counts = counts_for(df["hit"] == 1) if has_label else []
    flop_counts = counts_for(df["hit"] == 0) if has_label else []

    return {
        "feature": feature,
        "bin_centers": [safe_float(c) for c in centers],
        "bin_width": safe_float(edges[1] - edges[0]) if len(edges) > 1 else None,
        "hit_counts": hit_counts,
        "flop_counts": flop_counts,
        "missing": int(series.isna().sum()),
        "stats": {
            "mean": safe_float(valid.mean()),
            "median": safe_float(valid.median()),
            "std": safe_float(valid.std()),
            "min": safe_float(valid.min()),
            "max": safe_float(valid.max()),
        },
        "hit_mean": safe_float(series[df["hit"] == 1].mean()) if has_label else None,
        "flop_mean": safe_float(series[df["hit"] == 0].mean()) if has_label else None,
    }


def correlations() -> dict:
    """Pearson correlation over model-visible numeric features, plus the label."""
    df = get_dataframe()
    columns = _numeric_feature_columns(df)
    if "hit" in df.columns:
        columns = columns + ["hit"]

    matrix = df[columns].corr(numeric_only=True)
    values = [
        [safe_float(matrix.iat[r, c]) for c in range(matrix.shape[1])]
        for r in range(matrix.shape[0])
    ]

    # Strongest |r| pairs, excluding the diagonal — a readable summary of the heatmap.
    pairs = []
    for r in range(matrix.shape[0]):
        for c in range(r + 1, matrix.shape[1]):
            value = matrix.iat[r, c]
            if value is not None and isinstance(value, float) and math.isfinite(value):
                pairs.append({
                    "a": matrix.index[r],
                    "b": matrix.columns[c],
                    "r": safe_float(value),
                })
    pairs.sort(key=lambda p: abs(p["r"] or 0), reverse=True)

    return {
        "labels": list(matrix.columns),
        "matrix": values,
        "top_pairs": pairs[:10],
        "note": "Leakage columns are excluded so this matches what the model sees.",
    }


def genre_distribution(column: str | None = None, top: int = 15) -> dict:
    """Volume and hit rate for the most common values of a genre column."""
    df = get_dataframe()

    if column is None:
        column = next((c for c in GENRE_COLUMNS if c in df.columns), None)
    if column is None or column not in df.columns:
        raise ValueError("No genre column available in this dataset.")

    top = max(3, min(int(top), 40))
    counts = df[column].value_counts().head(top)

    labels, volumes, rates = [], [], []
    for label, count in counts.items():
        subset = df.loc[df[column] == label, "hit"] if "hit" in df.columns else None
        labels.append(str(label)[:44])
        volumes.append(int(count))
        rates.append(safe_float(subset.mean()) if subset is not None else None)

    return {
        "column": column,
        "available_columns": [c for c in GENRE_COLUMNS if c in df.columns],
        "labels": labels,
        "volumes": volumes,
        "hit_rates": rates,
        "distinct": int(df[column].nunique()),
        "coverage": safe_float(df[column].notna().mean()),
    }


def hit_rate_by_year(min_count: int = 10) -> dict:
    """Hit rate and release volume per year, from the chronological column."""
    df = get_dataframe()
    dates = _parsed_dates(df)
    if dates is None:
        raise ValueError("Dataset has no first_week column.")

    frame = pd.DataFrame({"year": dates.dt.year, "hit": df.get("hit")}).dropna(subset=["year"])
    grouped = frame.groupby("year")["hit"].agg(["count", "mean"]).reset_index()
    grouped = grouped[grouped["count"] >= max(1, int(min_count))].sort_values("year")

    now_year = datetime.now().year
    return {
        "years": [int(y) for y in grouped["year"]],
        "counts": [int(c) for c in grouped["count"]],
        "hit_rates": [safe_float(m) for m in grouped["mean"]],
        "min_count": int(min_count),
        "current_year": now_year,
        "future_years": [int(y) for y in grouped["year"] if y > now_year],
    }
