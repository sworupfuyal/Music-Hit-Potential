"""Filesystem locations shared across the backend."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "spotify.csv"
AUDIO_DIR = PROJECT_ROOT / "data" / "audio"
MODEL_DIR = PROJECT_ROOT / "models" / "saved_models"
BUNDLE_PATH = MODEL_DIR / "hit_app_bundle.joblib"

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
