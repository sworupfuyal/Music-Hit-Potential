from pathlib import Path
import base64
import os
import re

import joblib
import numpy as np
import pandas as pd
import requests
import streamlit as st
from sklearn.metrics import f1_score

from src.model import build_candidate_models, predict_with_scores, train_pipeline
from src.preprocessing import add_hit_label, make_preprocessor


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "spotify.csv"
MODEL_DIR = PROJECT_ROOT / "models" / "saved_models"
BUNDLE_PATH = MODEL_DIR / "hit_app_bundle.joblib"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def _prepare_model_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    if "hit" not in df.columns:
        popularity_col = "popularity" if "popularity" in df.columns else "track_popularity"
        df = add_hit_label(df, popularity_col=popularity_col, threshold=70)

    if "first_week" in df.columns:
        # The source file can contain mixed date formats, so we coerce parsing errors.
        df["first_week"] = pd.to_datetime(df["first_week"], errors="coerce")
        df = df.sort_values("first_week").reset_index(drop=True)
    else:
        df["__time_proxy__"] = np.arange(len(df))

    leakage_cols = {
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
        "first_week",
        "__time_proxy__",
    }

    preferred_features = [
        "danceability",
        "energy",
        "loudness",
        "valence",
        "tempo",
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

    available_features = [c for c in preferred_features if c in df.columns]
    if not available_features:
        available_features = [c for c in df.columns if c not in leakage_cols]

    return df[available_features + ["hit"]].copy()


def train_and_bundle_model(progress_callback=None, include_xgboost: bool = False) -> dict:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    raw_df = pd.read_csv(DATA_PATH)
    model_df = _prepare_model_frame(raw_df)

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

    bundle = {
        "model": best_pipeline,
        "model_name": best_model_name,
        "feature_columns": x_train.columns.tolist(),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "category_options": category_options,
        "numeric_defaults": numeric_defaults,
        "f1_macro": best_f1,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    if progress_callback is not None:
        progress_callback(total_models, total_models, best_model_name or "done")
    return bundle


@st.cache_resource(show_spinner=False)
def load_saved_bundle() -> dict:
    return joblib.load(BUNDLE_PATH)


def build_single_row_input(bundle: dict) -> pd.DataFrame:
    st.subheader("Single Song Input")
    data = {}

    for col in bundle["feature_columns"]:
        if col in bundle["numeric_columns"]:
            default_value = bundle["numeric_defaults"].get(col, 0.0)
            data[col] = st.number_input(col, value=float(default_value), format="%.6f")
        else:
            options = bundle["category_options"].get(col, [])
            options = [""] + options
            data[col] = st.selectbox(col, options=options, index=0)

    return pd.DataFrame([data])


def extract_spotify_track_id(track_input: str) -> str:
    value = (track_input or "").strip()
    if not value:
        raise ValueError("Please provide a Spotify track URL, URI, or track ID.")

    if "open.spotify.com/track/" in value:
        match = re.search(r"track/([A-Za-z0-9]+)", value)
        if not match:
            raise ValueError("Could not parse track ID from Spotify URL.")
        return match.group(1)

    if value.startswith("spotify:track:"):
        return value.split(":")[-1]

    if re.fullmatch(r"[A-Za-z0-9]{22}", value):
        return value

    raise ValueError("Invalid Spotify input. Use a track URL, URI, or 22-char track ID.")


def get_spotify_access_token(client_id: str, client_secret: str) -> str:
    auth_raw = f"{client_id}:{client_secret}".encode("utf-8")
    auth_b64 = base64.b64encode(auth_raw).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {"grant_type": "client_credentials"}
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload, headers=headers, timeout=20)
    if response.status_code != 200:
        raise ValueError("Spotify token request failed. Check client ID and secret.")
    return response.json()["access_token"]


def spotify_get(url: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code != 200:
        raise ValueError(f"Spotify API request failed for {url}.")
    return response.json()


def build_spotify_feature_row(track_input: str, client_id: str, client_secret: str) -> tuple[dict, dict]:
    token = get_spotify_access_token(client_id, client_secret)
    track_id = extract_spotify_track_id(track_input)

    track_json = spotify_get(f"{SPOTIFY_API_BASE}/tracks/{track_id}", token)
    audio_json = spotify_get(f"{SPOTIFY_API_BASE}/audio-features/{track_id}", token)

    artist_id = track_json.get("artists", [{}])[0].get("id")
    artist_json = spotify_get(f"{SPOTIFY_API_BASE}/artists/{artist_id}", token) if artist_id else {}
    artist_genres = artist_json.get("genres", [])
    primary_genre = artist_genres[0] if artist_genres else ""

    feature_map = {
        "danceability": audio_json.get("danceability", 0.0),
        "energy": audio_json.get("energy", 0.0),
        "loudness": audio_json.get("loudness", 0.0),
        "valence": audio_json.get("valence", 0.0),
        "tempo": audio_json.get("tempo", 0.0),
        "acousticness": audio_json.get("acousticness", 0.0),
        "speechiness": audio_json.get("speechiness", 0.0),
        "instrumentalness": audio_json.get("instrumentalness", 0.0),
        "liveness": audio_json.get("liveness", 0.0),
        "duration": track_json.get("duration_ms", 0.0),
        "spotify_genre": primary_genre,
        "playlist_genre": primary_genre,
        "playlist_subgenre": primary_genre,
        "genre": primary_genre,
        "mentions": 0.0,
        "sentiment_polarity": 0.0,
        "sentiment_subjectivity": 0.0,
    }

    display_info = {
        "track_name": track_json.get("name", ""),
        "artist_name": track_json.get("artists", [{}])[0].get("name", ""),
        "album_name": track_json.get("album", {}).get("name", ""),
        "primary_genre": primary_genre,
        "track_id": track_id,
    }

    return feature_map, display_info


def build_model_input_from_feature_map(bundle: dict, feature_map: dict) -> pd.DataFrame:
    row = {}
    for col in bundle["feature_columns"]:
        if col in bundle["numeric_columns"]:
            row[col] = float(feature_map.get(col, bundle["numeric_defaults"].get(col, 0.0)))
        else:
            row[col] = str(feature_map.get(col, ""))
    return pd.DataFrame([row])


def batch_predict(bundle: dict, uploaded_file) -> pd.DataFrame:
    batch_df = pd.read_csv(uploaded_file)
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


def main() -> None:
    st.set_page_config(page_title="Music Hit Potential App", page_icon="music_note", layout="wide")
    st.title("Music Hit Potential App")
    st.caption("Predict hit potential from song features using your trained pipeline.")

    bundle = None
    if BUNDLE_PATH.exists():
        try:
            bundle = load_saved_bundle()
        except Exception as exc:
            st.warning(f"Existing saved bundle could not be loaded: {exc}")

    if bundle is None:
        st.info("No saved app model found yet. Train one to unlock predictions.")
        col_train, col_mode = st.columns([1, 1])
        with col_mode:
            include_xgboost = st.checkbox("Include XGBoost (slower)", value=False)
        with col_train:
            train_clicked = st.button("Train App Model", type="primary")

        if not train_clicked:
            st.stop()

        progress = st.progress(0.0)
        status = st.empty()

        def _on_progress(done, total, current):
            fraction = done / total if total else 1.0
            progress.progress(fraction)
            if done < total:
                status.info(f"Training model {done + 1}/{total}: {current}")
            else:
                status.success("Training complete.")

        try:
            with st.spinner("Training bundle from local dataset..."):
                bundle = train_and_bundle_model(progress_callback=_on_progress, include_xgboost=include_xgboost)
        except Exception as exc:
            st.error(f"Could not train app model: {exc}")
            st.stop()

        st.rerun()

    c1, c2 = st.columns(2)
    c1.metric("Selected Model", bundle["model_name"])
    c2.metric("Validation Macro F1", f"{bundle['f1_macro']:.4f}")

    with st.sidebar:
        st.subheader("Spotify API")
        default_client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
        default_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
        spotify_client_id = st.text_input("Client ID", value=default_client_id)
        spotify_client_secret = st.text_input("Client Secret", value=default_client_secret, type="password")

    tab_single, tab_batch, tab_spotify = st.tabs(["Single Prediction", "Batch Prediction", "Spotify URL/ID"])

    with tab_single:
        input_df = build_single_row_input(bundle)
        if st.button("Predict Hit Potential", type="primary"):
            proba = bundle["model"].predict_proba(input_df)[:, 1][0]
            label = int(proba >= 0.5)
            st.success(f"Hit potential: {proba * 100:.2f}%")
            st.write("Predicted class:", "Hit" if label == 1 else "Non-hit")

    with tab_batch:
        st.write("Upload a CSV with the same feature columns used during training.")
        uploaded_file = st.file_uploader("Batch CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                output = batch_predict(bundle, uploaded_file)
                st.dataframe(output.head(20), use_container_width=True)
                csv_data = output.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download predictions CSV",
                    data=csv_data,
                    file_name="batch_hit_potential_predictions.csv",
                    mime="text/csv",
                )
            except Exception as exc:
                st.error(str(exc))

    with tab_spotify:
        st.write("Predict from a Spotify track URL, URI, or track ID.")
        track_input = st.text_input(
            "Spotify Track",
            placeholder="https://open.spotify.com/track/<id> or spotify:track:<id>",
        )
        auto_predict = st.button("Fetch From Spotify And Predict", type="primary")

        if auto_predict:
            if not spotify_client_id or not spotify_client_secret:
                st.error("Please provide Spotify Client ID and Client Secret in the sidebar.")
            else:
                try:
                    feature_map, display_info = build_spotify_feature_row(
                        track_input, spotify_client_id, spotify_client_secret
                    )
                    model_input = build_model_input_from_feature_map(bundle, feature_map)
                    proba = bundle["model"].predict_proba(model_input)[:, 1][0]
                    label = int(proba >= 0.5)

                    st.success(f"Hit potential: {proba * 100:.2f}%")
                    st.write("Predicted class:", "Hit" if label == 1 else "Non-hit")
                    st.write("Track:", display_info["track_name"])
                    st.write("Artist:", display_info["artist_name"])
                    st.write("Album:", display_info["album_name"])
                    st.write("Primary genre:", display_info["primary_genre"])
                except Exception as exc:
                    st.error(str(exc))


if __name__ == "__main__":
    main()
