"""Librosa-based audio feature extraction from raw audio bytes.

MP3 decoding (Spotify previews) requires ffmpeg on PATH.
Install: https://ffmpeg.org/download.html  (Windows: winget install ffmpeg)
"""

import io

import numpy as np

FEATURE_NAMES: list[str] = [
    "tempo",
    "energy",
    "loudness_db",
    "zcr",
    "spectral_centroid",
    "spectral_rolloff",
    "spectral_bandwidth",
    "chroma",
    *[f"mfcc_{i}" for i in range(1, 14)],
]


def extract_from_bytes(audio_bytes: bytes, sr: int = 22050) -> dict[str, float]:
    """Extract audio features from raw audio bytes using librosa.

    Works with any format ffmpeg can decode (MP3, WAV, OGG, etc.).
    Raises RuntimeError with a helpful message if ffmpeg is missing.
    """
    try:
        import librosa  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("Install librosa: pip install librosa") from exc

    try:
        y, sample_rate = librosa.load(io.BytesIO(audio_bytes), sr=sr, mono=True)
    except Exception as exc:
        raise RuntimeError(
            "Audio decoding failed. Spotify previews are MP3 — install ffmpeg and "
            "add it to your PATH, then restart the app. "
            "Windows: winget install ffmpeg  |  Error: " + str(exc)
        ) from exc

    tempo_arr, _ = librosa.beat.beat_track(y=y, sr=sample_rate)
    rms = librosa.feature.rms(y=y)
    zcr = librosa.feature.zero_crossing_rate(y=y)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sample_rate)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sample_rate)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sample_rate)
    chroma = librosa.feature.chroma_stft(y=y, sr=sample_rate)
    mfccs = librosa.feature.mfcc(y=y, sr=sample_rate, n_mfcc=13)

    features: dict[str, float] = {
        "tempo": float(np.atleast_1d(tempo_arr)[0]),
        "energy": float(np.mean(rms)),
        "loudness_db": float(librosa.amplitude_to_db(rms).mean()),
        "zcr": float(np.mean(zcr)),
        "spectral_centroid": float(np.mean(centroid)),
        "spectral_rolloff": float(np.mean(rolloff)),
        "spectral_bandwidth": float(np.mean(bandwidth)),
        "chroma": float(np.mean(chroma)),
    }
    for i, coef in enumerate(mfccs, start=1):
        features[f"mfcc_{i}"] = float(np.mean(coef))

    return features


def zero_features() -> dict[str, float]:
    """Return zeroed features when audio is unavailable (no preview URL, ffmpeg missing, etc.)."""
    return {name: 0.0 for name in FEATURE_NAMES}
