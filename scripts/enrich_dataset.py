"""Enrich spotify_songs.csv with Librosa audio features + Spotify metadata.

Usage:
    python scripts/enrich_dataset.py \
        --input  data/raw/spotify_songs.csv \
        --output data/processed/enriched_dataset.csv \
        --client-id  <SPOTIFY_CLIENT_ID> \
        --client-secret <SPOTIFY_CLIENT_SECRET> \
        [--limit 500]          # rows to process (omit for all)
        [--batch-size 50]      # Spotify API calls per batch

Requires: librosa, requests, pandas, ffmpeg on PATH (for MP3 decoding).
"""

import argparse
import base64
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio_features import extract_from_bytes, zero_features  # noqa: E402

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


# ---------------------------------------------------------------------------
# Spotify helpers
# ---------------------------------------------------------------------------

def get_token(client_id: str, client_secret: str) -> str:
    auth_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def spotify_get(url: str, token: str, retries: int = 3) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(retries):
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited — waiting {wait}s …")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            return {}
        return resp.json()
    return {}


def fetch_tracks_batch(track_ids: list[str], token: str) -> dict[str, dict]:
    """Fetch up to 50 tracks in one API call. Returns {track_id: track_json}."""
    url = f"{SPOTIFY_API_BASE}/tracks?ids={','.join(track_ids)}"
    data = spotify_get(url, token)
    result = {}
    for track in data.get("tracks") or []:
        if track:
            result[track["id"]] = track
    return result


def fetch_artists_batch(artist_ids: list[str], token: str) -> dict[str, dict]:
    """Fetch up to 50 artists in one API call. Returns {artist_id: artist_json}."""
    unique = list(dict.fromkeys(artist_ids))[:50]
    url = f"{SPOTIFY_API_BASE}/artists?ids={','.join(unique)}"
    data = spotify_get(url, token)
    result = {}
    for artist in data.get("artists") or []:
        if artist:
            result[artist["id"]] = artist
    return result


def download_preview(url: str) -> bytes | None:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def parse_release_date(date_str: str) -> tuple[int, int]:
    parts = (date_str or "").split("-")
    year = int(parts[0]) if parts and parts[0].isdigit() else 0
    month = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return year, month


def build_row(track: dict, artist: dict, audio_bytes: bytes | None) -> dict:
    if audio_bytes:
        try:
            audio_feats = extract_from_bytes(audio_bytes)
        except Exception as exc:
            print(f"    Librosa error: {exc}")
            audio_feats = zero_features()
    else:
        audio_feats = zero_features()

    release_date = track.get("album", {}).get("release_date", "")
    release_year, release_month = parse_release_date(release_date)

    genres = artist.get("genres", [])
    primary_genre = genres[0] if genres else ""

    return {
        **audio_feats,
        "track_popularity": track.get("popularity", 0),
        "artist_popularity": artist.get("popularity", 0),
        "artist_followers": (artist.get("followers") or {}).get("total", 0),
        "duration_ms": track.get("duration_ms", 0),
        "is_explicit": int(track.get("explicit", False)),
        "release_year": release_year,
        "release_month": release_month,
        "num_artists": len(track.get("artists", [])),
        "primary_genre": primary_genre,
        "has_preview": int(bool(track.get("preview_url"))),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Spotify dataset with audio features.")
    parser.add_argument("--input", default="data/raw/spotify_songs.csv")
    parser.add_argument("--output", default="data/processed/enriched_dataset.csv")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Tracks per API batch")
    args = parser.parse_args()

    input_path = PROJECT_ROOT / args.input
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    if args.limit:
        df = df.head(args.limit)

    if "track_id" not in df.columns:
        sys.exit("ERROR: input CSV has no 'track_id' column.")

    print(f"Loaded {len(df):,} rows from {input_path}")
    token = get_token(args.client_id, args.client_secret)
    print("Spotify token obtained.")

    # Deduplicate track IDs for API efficiency
    track_ids = df["track_id"].dropna().unique().tolist()
    print(f"Unique track IDs: {len(track_ids):,}")

    enriched: dict[str, dict] = {}
    batch = args.batch_size

    for start in range(0, len(track_ids), batch):
        chunk = track_ids[start: start + batch]
        print(f"  Fetching tracks {start + 1}–{min(start + batch, len(track_ids))} …")

        tracks = fetch_tracks_batch(chunk, token)

        # Collect artist IDs for this batch
        artist_id_map: dict[str, str] = {}  # track_id → artist_id
        for tid, track in tracks.items():
            aid = (track.get("artists") or [{}])[0].get("id")
            if aid:
                artist_id_map[tid] = aid

        artists = fetch_artists_batch(list(artist_id_map.values()), token)

        for tid, track in tracks.items():
            artist = artists.get(artist_id_map.get(tid, ""), {})
            preview_url = track.get("preview_url")
            audio_bytes = download_preview(preview_url) if preview_url else None
            enriched[tid] = build_row(track, artist, audio_bytes)

        # Refresh token every ~800 tracks (token expires in 3600s)
        if (start + batch) % 800 == 0:
            token = get_token(args.client_id, args.client_secret)

    enriched_df = pd.DataFrame.from_dict(enriched, orient="index")
    enriched_df.index.name = "track_id"
    enriched_df = enriched_df.reset_index()

    # Merge back with original CSV to keep playlist_genre, playlist_subgenre, etc.
    keep_cols = [
        "track_id", "track_name", "track_artist",
        "playlist_genre", "playlist_subgenre",
        "track_album_release_date",
    ]
    meta = df[[c for c in keep_cols if c in df.columns]].drop_duplicates("track_id")
    result = enriched_df.merge(meta, on="track_id", how="left")

    # Add hit label: track_popularity >= 70
    result["hit"] = (result["track_popularity"] >= 70).astype(int)

    result.to_csv(output_path, index=False)
    hit_rate = result["hit"].mean() * 100
    print(f"\nSaved {len(result):,} rows to {output_path}")
    print(f"Hit rate: {hit_rate:.1f}%  |  Features: {list(result.columns)}")


if __name__ == "__main__":
    main()
