"""Train a hit-prediction model directly from local audio files (CLI).

This is the Spotify-free path. It extracts the SAME Librosa features the app's
"Local Audio File" tab produces, so uploads are scored on matching footing.
The actual work lives in backend.app.training.train_from_audio_folders — this is
just a CLI wrapper (the web app exposes the same thing via a button in the Local
Audio tab).

Folder layout (drop your files here):
    data/audio/hit/*.mp3        <- songs you consider hits
    data/audio/not_hit/*.mp3    <- songs you consider non-hits

Usage:
    python scripts/train_from_audio.py

Requires ffmpeg on PATH for MP3 decoding (WAV works without it).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.training import train_from_audio_folders  # noqa: E402


def _progress(done: int, total: int, current: str) -> None:
    if done < total:
        print(f"  [{done + 1}/{total}] {current}")


def main() -> None:
    print("Extracting Librosa features from local audio…")
    try:
        bundle = train_from_audio_folders(progress_callback=_progress)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        sys.exit(str(exc))

    print(
        f"\nSaved model '{bundle['model_name']}' "
        f"(macro F1 {bundle['f1_macro']:.3f}) trained on {bundle['n_train_songs']} songs."
    )
    print("Reload the web app — Local Audio uploads now score on matching features.")


if __name__ == "__main__":
    main()
