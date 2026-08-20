"""Model training routines.

Ported unchanged in behaviour from the former Streamlit `app.py`: the dataset
path trains candidate models on the enriched Spotify CSV, and the audio path
trains on Librosa features extracted from local audio folders. Both persist the
same bundle shape to models/saved_models/hit_app_bundle.joblib.
"""

from pathlib import Path
from typing import Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from src.audio_features import FEATURE_NAMES, extract_from_bytes
from src.model import build_candidate_models, predict_with_scores, train_pipeline
from src.preprocessing import add_hit_label, clean_dataset, make_preprocessor

from .paths import AUDIO_DIR, AUDIO_EXTS, BUNDLE_PATH, DATA_PATH, MODEL_DIR

ProgressCallback = Callable[[int, int, str], None] | None

# Columns that must never reach the model: the label itself, chart outcomes that
# encode it, free-text identifiers, and the ordering helpers. Exposed at module
# level so the dataset/reports endpoints describe the same exclusions rather than
# keeping a second copy of this list.
LEAKAGE_COLUMNS = {
    "hit",
    "peak_position",
    "weeks_on_chart",
    "debut_rank",
    "song_display",
    "artist_display",
    "song",
    "artist",
    "track_name",
    "track_artist",
    "popularity",
    "track_popularity",
    "first_week",
    "__time_proxy__",
}


def prepare_model_frame(df: pd.DataFrame, clean: bool = True) -> pd.DataFrame:
    """Label, order chronologically, and reduce a raw frame to model features + hit.

    With `clean` set (the default) duplicates and impossible dates are removed first.
    That matters for the chronological split below: the source file carries dates as
    far ahead as 2075, and those rows would otherwise sort to the end and make up the
    held-out tail instead of genuinely recent releases.
    """
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    if clean:
        df, _ = clean_dataset(df)

    if "hit" not in df.columns:
        popularity_col = "popularity" if "popularity" in df.columns else "track_popularity"
        df = add_hit_label(df, popularity_col=popularity_col, threshold=70)

    if "first_week" in df.columns:
        # The source file can contain mixed date formats, so we coerce parsing errors.
        df["first_week"] = pd.to_datetime(df["first_week"], errors="coerce")
        df = df.sort_values("first_week").reset_index(drop=True)
    else:
        df["__time_proxy__"] = np.arange(len(df))

    leakage_cols = LEAKAGE_COLUMNS

    preferred_features = [
        # Librosa audio features (enriched dataset)
        "tempo",
        "energy",
        "loudness_db",
        "zcr",
        "spectral_centroid",
        "spectral_rolloff",
        "spectral_bandwidth",
        "chroma",
        *[f"mfcc_{i}" for i in range(1, 14)],
        # Spotify metadata features (enriched dataset)
        "track_popularity",
        "artist_popularity",
        "artist_followers",
        "duration_ms",
        "is_explicit",
        "release_year",
        "release_month",
        "num_artists",
        "primary_genre",
        # Legacy Spotify audio-features columns (original CSV)
        "danceability",
        "loudness",
        "valence",
        "acousticness",
        "speechiness",
        "instrumentalness",
        "liveness",
        "duration",
        "sentiment_polarity",
        "sentiment_subjectivity",
        "mentions",
        "spotify_genre",
        "playlist_genre",
        "playlist_subgenre",
        "genre",
    ]

    # The leakage set filters BOTH paths. Without this the whitelist would readmit
    # track_popularity, which the fallback label above is derived from — the model
    # would then be handed a near-deterministic copy of its own target.
    available_features = [
        c for c in preferred_features if c in df.columns and c not in leakage_cols
    ]
    if not available_features:
        available_features = [c for c in df.columns if c not in leakage_cols]

    return df[available_features + ["hit"]].copy()


def train_and_bundle_model(
    progress_callback: ProgressCallback = None,
    include_xgboost: bool = False,
) -> dict:
    """Train candidate models on the raw dataset and save the best as the app bundle."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    raw_df = pd.read_csv(DATA_PATH)
    model_df = prepare_model_frame(raw_df)

    split_idx = int(0.8 * len(model_df))
    x_train = model_df.iloc[:split_idx].drop(columns=["hit"])
    y_train = model_df.iloc[:split_idx]["hit"]
    x_test = model_df.iloc[split_idx:].drop(columns=["hit"])
    y_test = model_df.iloc[split_idx:]["hit"]

    numeric_columns = x_train.select_dtypes(include=["number"]).columns.tolist()
    categorical_columns = [c for c in x_train.columns if c not in numeric_columns]

    preprocessor = make_preprocessor(numeric_columns, categorical_columns)
    candidate_models = build_candidate_models()
    if not include_xgboost:
        candidate_models = {k: v for k, v in candidate_models.items() if k != "xgboost"}

    best_pipeline = None
    best_model_name = None
    best_f1 = -1.0

    total_models = max(len(candidate_models), 1)
    for idx, (model_name, estimator) in enumerate(candidate_models.items(), start=1):
        if progress_callback is not None:
            progress_callback(idx - 1, total_models, model_name)
        pipeline = train_pipeline(preprocessor, estimator, x_train, y_train)
        y_pred, _ = predict_with_scores(pipeline, x_test)
        score = f1_score(y_test, y_pred, average="macro", zero_division=0)

        if score > best_f1:
            best_f1 = score
            best_model_name = model_name
            best_pipeline = pipeline

    category_options = {}
    for col in categorical_columns:
        values = x_train[col].dropna().astype(str).unique().tolist()
        values.sort()
        category_options[col] = values

    numeric_defaults = {}
    for col in numeric_columns:
        numeric_defaults[col] = float(x_train[col].median())

    # Profiles for the radar chart: per-feature ranges and average hit/flop values.
    train_df = model_df.iloc[:split_idx]
    feature_ranges = {}
    for col in numeric_columns:
        feature_ranges[col] = (float(x_train[col].min()), float(x_train[col].max()))

    hit_rows = train_df[train_df["hit"] == 1]
    flop_rows = train_df[train_df["hit"] == 0]
    hit_profile = {col: float(hit_rows[col].mean()) for col in numeric_columns if len(hit_rows)}
    flop_profile = {col: float(flop_rows[col].mean()) for col in numeric_columns if len(flop_rows)}

    bundle = {
        "model": best_pipeline,
        "model_name": best_model_name,
        "feature_columns": x_train.columns.tolist(),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "category_options": category_options,
        "numeric_defaults": numeric_defaults,
        "feature_ranges": feature_ranges,
        "hit_profile": hit_profile,
        "flop_profile": flop_profile,
        "f1_macro": best_f1,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    if progress_callback is not None:
        progress_callback(total_models, total_models, best_model_name or "done")
    return bundle


def collect_audio_files(label_dir: Path) -> list[Path]:
    if not label_dir.exists():
        return []
    return [p for p in label_dir.iterdir() if p.suffix.lower() in AUDIO_EXTS]


def audio_library_counts() -> dict[str, int]:
    """Number of usable audio files in each label folder."""
    return {
        "hit": len(collect_audio_files(AUDIO_DIR / "hit")),
        "not_hit": len(collect_audio_files(AUDIO_DIR / "not_hit")),
    }


def train_from_audio_folders(progress_callback: ProgressCallback = None) -> dict:
    """Train a hit model from local audio in data/audio/{hit,not_hit}.

    Extracts the same Librosa features the upload tab produces, so predictions
    on uploaded files are scored on matching footing. Returns the saved bundle.
    """
    rows = []
    folders = [(1, AUDIO_DIR / "hit"), (0, AUDIO_DIR / "not_hit")]
    files = [(label, p) for label, folder in folders for p in collect_audio_files(folder)]

    if not files:
        raise FileNotFoundError(
            "No audio found. Add files to data/audio/hit/ and data/audio/not_hit/."
        )

    total = len(files)
    for idx, (label, path) in enumerate(files):
        if progress_callback is not None:
            progress_callback(idx, total, path.name)
        try:
            feats = extract_from_bytes(path.read_bytes())
        except Exception as exc:
            raise RuntimeError(f"Failed on {path.name}: {exc}") from exc
        feats["hit"] = label
        rows.append(feats)

    df = pd.DataFrame(rows)
    n_hit = int((df["hit"] == 1).sum())
    n_flop = int((df["hit"] == 0).sum())
    if n_hit == 0 or n_flop == 0:
        raise ValueError("Need at least one song in BOTH hit/ and not_hit/ folders.")

    feature_cols = list(FEATURE_NAMES)
    x = df[feature_cols].copy()
    y = df["hit"].copy()

    tiny = len(df) < 8 or min(n_hit, n_flop) < 2
    if tiny:
        x_train, y_train, x_test, y_test = x, y, x, y
    else:
        from sklearn.model_selection import train_test_split

        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.25, random_state=42, stratify=y
        )

    preprocessor = make_preprocessor(feature_cols, [])
    candidates = {k: v for k, v in build_candidate_models().items() if k != "xgboost"}

    best_pipeline, best_name, best_f1 = None, None, -1.0
    for name, est in candidates.items():
        pipeline = train_pipeline(preprocessor, est, x_train, y_train)
        score = f1_score(y_test, pipeline.predict(x_test), average="macro", zero_division=0)
        if score > best_f1:
            best_pipeline, best_name, best_f1 = pipeline, name, score

    ranges = {c: (float(x[c].min()), float(x[c].max())) for c in feature_cols}
    hit_profile = {c: float(df.loc[df["hit"] == 1, c].mean()) for c in feature_cols}
    flop_profile = {c: float(df.loc[df["hit"] == 0, c].mean()) for c in feature_cols}

    bundle = {
        "model": best_pipeline,
        "model_name": best_name,
        "feature_columns": feature_cols,
        "numeric_columns": feature_cols,
        "categorical_columns": [],
        "category_options": {},
        "numeric_defaults": {c: float(x[c].median()) for c in feature_cols},
        "feature_ranges": ranges,
        "hit_profile": hit_profile,
        "flop_profile": flop_profile,
        "f1_macro": best_f1,
        "trained_on": "local_audio",
        "n_train_songs": len(df),
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    if progress_callback is not None:
        progress_callback(total, total, best_name or "done")
    return bundle
