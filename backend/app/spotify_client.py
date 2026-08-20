"""Spotify Web API lookups and feature-row construction.

Ported from the former Streamlit app: client-credentials auth, track/artist
metadata, and Librosa features pulled from the 30-second preview when one exists.
"""

import base64
import re

import requests

from src.audio_features import extract_from_bytes, zero_features

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


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
        try:
            detail = response.json().get("error", {}).get("message", response.text[:200])
        except Exception:
            detail = response.text[:200]
        raise ValueError(
            f"Spotify API request failed for {url}. "
            f"Status {response.status_code}: {detail}"
        )
    return response.json()


def _parse_release_date(date_str: str) -> tuple[int, int]:
    parts = (date_str or "").split("-")
    year = int(parts[0]) if parts and parts[0].isdigit() else 0
    month = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return year, month


def build_spotify_feature_row(
    track_input: str, client_id: str, client_secret: str
) -> tuple[dict, dict]:
    token = get_spotify_access_token(client_id, client_secret)
    track_id = extract_spotify_track_id(track_input)

    track_json = spotify_get(f"{SPOTIFY_API_BASE}/tracks/{track_id}", token)

    artist_id = (track_json.get("artists") or [{}])[0].get("id")
    artist_json = spotify_get(f"{SPOTIFY_API_BASE}/artists/{artist_id}", token) if artist_id else {}
    artist_genres = artist_json.get("genres", [])
    primary_genre = artist_genres[0] if artist_genres else ""

    release_date = track_json.get("album", {}).get("release_date", "")
    release_year, release_month = _parse_release_date(release_date)

    # --- Librosa audio features from 30-second preview ---
    preview_url = track_json.get("preview_url")
    audio_warning: str | None = None

    if preview_url:
        try:
            audio_bytes = requests.get(preview_url, timeout=20).content
            audio_feats = extract_from_bytes(audio_bytes)
        except RuntimeError as exc:
            audio_feats = zero_features()
            audio_warning = str(exc)
        except Exception as exc:
            audio_feats = zero_features()
            audio_warning = f"Audio extraction failed: {exc}"
    else:
        audio_feats = zero_features()
        audio_warning = "No 30-second preview is available for this track on Spotify."

    duration_ms = float(track_json.get("duration_ms", 0))

    feature_map: dict = {
        # Librosa audio features
        **audio_feats,
        # Spotify metadata
        "track_popularity": float(track_json.get("popularity", 0)),
        "artist_popularity": float(artist_json.get("popularity", 0)),
        "artist_followers": float((artist_json.get("followers") or {}).get("total", 0)),
        "duration_ms": duration_ms,
        "is_explicit": float(int(track_json.get("explicit", False))),
        "release_year": float(release_year),
        "release_month": float(release_month),
        "num_artists": float(len(track_json.get("artists", []))),
        "primary_genre": primary_genre,
        # Legacy column names kept for backward compat with models trained on old CSV
        "duration": duration_ms,
        "loudness": audio_feats.get("loudness_db", 0.0),
        "spotify_genre": primary_genre,
        "playlist_genre": primary_genre,
        "playlist_subgenre": primary_genre,
        "genre": primary_genre,
        "danceability": 0.0,
        "valence": 0.0,
        "acousticness": 0.0,
        "speechiness": audio_feats.get("zcr", 0.0),
        "instrumentalness": 0.0,
        "liveness": 0.0,
        "mentions": 0.0,
        "sentiment_polarity": 0.0,
        "sentiment_subjectivity": 0.0,
    }

    album_images = track_json.get("album", {}).get("images") or []

    display_info = {
        "track_name": track_json.get("name", ""),
        "artist_name": (track_json.get("artists") or [{}])[0].get("name", ""),
        "album_name": track_json.get("album", {}).get("name", ""),
        "primary_genre": primary_genre,
        "track_id": track_id,
        "audio_warning": audio_warning,
        "album_image": album_images[0].get("url") if album_images else None,
        "preview_url": preview_url,
    }

    return feature_map, display_info
