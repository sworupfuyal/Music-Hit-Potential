"""Quick probe: do Spotify previews still work for our dataset?

Usage:
    python scripts/check_previews.py --client-id ID --client-secret SECRET
"""

import argparse
import base64
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    ap.add_argument("--sample", type=int, default=50)
    args = ap.parse_args()

    # token
    auth = base64.b64encode(f"{args.client_id}:{args.client_secret}".encode()).decode()
    tok = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if tok.status_code != 200:
        sys.exit(f"Auth failed ({tok.status_code}): {tok.text[:200]}")
    token = tok.json()["access_token"]

    df = pd.read_csv(ROOT / "data" / "raw" / "spotify_songs.csv")
    ids = df["track_id"].dropna().unique()[: args.sample]

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        "https://api.spotify.com/v1/tracks?ids=" + ",".join(ids),
        headers=headers, timeout=20,
    )
    if r.status_code != 200:
        sys.exit(f"/tracks failed ({r.status_code}): {r.text[:200]}")

    tracks = [t for t in r.json().get("tracks", []) if t]
    with_preview = sum(1 for t in tracks if t.get("preview_url"))
    total = len(tracks)
    pct = (with_preview / total * 100) if total else 0

    print(f"\nSampled {total} tracks")
    print(f"Previews available: {with_preview}/{total}  ({pct:.0f}%)")
    print("-" * 40)
    if pct >= 50:
        print("GOOD -> run scripts/enrich_dataset.py, then retrain. Local uploads will work.")
    elif pct > 0:
        print("PARTIAL -> enrichment works but on a smaller subset. Still usable.")
    else:
        print("ZERO previews -> Spotify is not serving audio. Enrichment can't get audio.")
        print("Fallback: train on your own local MP3 folder (I can build that).")


if __name__ == "__main__":
    main()
