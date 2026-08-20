"""Prediction helpers: single row, batch CSV, and local-audio feature maps."""

import io
import json
import threading
import uuid
from collections import OrderedDict

import pandas as pd

from .bundle import safe_float

# Batch results are held briefly so the browser can download the full annotated
# CSV without re-uploading and re-scoring the file.
_BATCH_RESULTS: "OrderedDict[str, bytes]" = OrderedDict()
_BATCH_LIMIT = 10
_batch_lock = threading.Lock()

LABEL_COLUMN_CANDIDATES = ("track_name", "song", "song_display", "track")


def build_model_input_from_feature_map(bundle: dict, feature_map: dict) -> pd.DataFrame:
    row = {}
    for col in bundle["feature_columns"]:
        if col in bundle["numeric_columns"]:
            row[col] = float(feature_map.get(col, bundle["numeric_defaults"].get(col, 0.0)))
        else:
            row[col] = str(feature_map.get(col, ""))
    return pd.DataFrame([row])


def predict_probability(bundle: dict, model_input: pd.DataFrame) -> float:
    return float(bundle["model"].predict_proba(model_input)[:, 1][0])


def numeric_feature_echo(bundle: dict, model_input: pd.DataFrame) -> dict[str, float | None]:
    """Numeric values actually fed to the model — drives the radar/MFCC charts."""
    row = model_input.iloc[0]
    return {
        col: safe_float(row[col])
        for col in bundle["numeric_columns"]
        if col in model_input.columns
    }


def audio_feature_map(audio_feats: dict) -> dict:
    """Wrap Librosa features with neutral metadata defaults for a local file.

    Metadata (popularity, followers, release date) is unknowable from a bare
    audio file, so those columns are zeroed exactly as the Streamlit app did.
    """
    return {
        **audio_feats,
        "track_popularity": 0.0,
        "artist_popularity": 0.0,
        "artist_followers": 0.0,
        "duration_ms": 0.0,
        "is_explicit": 0.0,
        "release_year": 0.0,
        "release_month": 0.0,
        "num_artists": 1.0,
        "primary_genre": "",
        # Legacy column names for backward compat
        "tempo": audio_feats["tempo"],
        "energy": audio_feats["energy"],
        "loudness": audio_feats["loudness_db"],
        "speechiness": audio_feats["zcr"],
        "duration": 0.0,
        "danceability": 0.0,
        "valence": 0.0,
        "acousticness": 0.0,
        "instrumentalness": 0.0,
        "liveness": 0.0,
        "spotify_genre": "",
        "playlist_genre": "",
        "playlist_subgenre": "",
        "genre": "",
        "mentions": 0.0,
        "sentiment_polarity": 0.0,
        "sentiment_subjectivity": 0.0,
    }


def _records(df: pd.DataFrame) -> list[dict]:
    """JSON-safe records (NaN becomes null)."""
    return json.loads(df.to_json(orient="records"))


def batch_predict(bundle: dict, csv_bytes: bytes) -> pd.DataFrame:
    batch_df = pd.read_csv(io.BytesIO(csv_bytes))
    batch_df.columns = [c.lower() for c in batch_df.columns]

    missing = [c for c in bundle["feature_columns"] if c not in batch_df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    x_batch = batch_df[bundle["feature_columns"]].copy()
    proba = bundle["model"].predict_proba(x_batch)[:, 1]
    pred = (proba >= 0.5).astype(int)

    output = batch_df.copy()
    output["hit_potential"] = proba
    output["predicted_hit"] = pred
    return output


def store_batch_csv(output: pd.DataFrame) -> str:
    download_id = uuid.uuid4().hex
    with _batch_lock:
        _BATCH_RESULTS[download_id] = output.to_csv(index=False).encode("utf-8")
        while len(_BATCH_RESULTS) > _BATCH_LIMIT:
            _BATCH_RESULTS.popitem(last=False)
    return download_id


def get_batch_csv(download_id: str) -> bytes | None:
    with _batch_lock:
        return _BATCH_RESULTS.get(download_id)


def summarize_batch(output: pd.DataFrame, preview_rows: int = 20, top_n: int = 10) -> dict:
    """KPIs, chart series and a preview table for a scored batch."""
    scores = output["hit_potential"]
    label_col = next((c for c in LABEL_COLUMN_CANDIDATES if c in output.columns), None)

    ranked = output.sort_values("hit_potential", ascending=False).head(top_n)
    ranked_labels = (
        ranked[label_col].astype(str).str.slice(0, 40).tolist()
        if label_col
        else [str(i) for i in ranked.index]
    )

    scatter = None
    if "danceability" in output.columns and "energy" in output.columns:
        scatter = {
            "x_label": "Danceability",
            "y_label": "Energy",
            "x": [safe_float(v) for v in output["danceability"]],
            "y": [safe_float(v) for v in output["energy"]],
            "score": [float(v) for v in scores],
        }

    return {
        "total": int(len(output)),
        "predicted_hits": int(output["predicted_hit"].sum()),
        "avg_score": float(scores.mean()) * 100,
        "top_score": float(scores.max()) * 100,
        "label_column": label_col,
        "scores": [float(v) for v in scores],
        "ranked": {
            "labels": ranked_labels,
            "scores": [float(v) for v in ranked["hit_potential"]],
        },
        "scatter": scatter,
        "preview_columns": output.columns.tolist(),
        "preview_rows": _records(output.head(preview_rows)),
    }
