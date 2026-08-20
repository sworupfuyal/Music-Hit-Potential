"""Training endpoints. Runs happen on a background thread and report progress."""

from fastapi import APIRouter, HTTPException

from ..bundle import invalidate_cache, safe_float
from ..jobs import create_job, get_job, run_in_background
from ..paths import AUDIO_DIR, DATA_PATH
from ..schemas import JobStartedResponse, TrainDatasetRequest
from ..training import (
    audio_library_counts,
    collect_audio_files,
    train_and_bundle_model,
    train_from_audio_folders,
)

router = APIRouter(prefix="/api/train", tags=["train"])


def _summarize(bundle: dict) -> dict:
    return {
        "model_name": bundle.get("model_name"),
        "f1_macro": safe_float(bundle.get("f1_macro")),
        "trained_on": bundle.get("trained_on"),
        "n_train_songs": bundle.get("n_train_songs"),
    }


@router.get("/audio-library")
def read_audio_library() -> dict:
    """File counts in data/audio/{hit,not_hit} — drives the audio training panel."""
    counts = audio_library_counts()
    return {
        **counts,
        "ready": counts["hit"] > 0 and counts["not_hit"] > 0,
        "hit_dir": str(AUDIO_DIR / "hit"),
        "not_hit_dir": str(AUDIO_DIR / "not_hit"),
    }


@router.post("/dataset", response_model=JobStartedResponse)
def train_dataset(payload: TrainDatasetRequest) -> JobStartedResponse:
    if not DATA_PATH.exists():
        raise HTTPException(status_code=400, detail=f"Dataset not found at {DATA_PATH}")

    job_id = create_job("dataset")

    def describe(done: int, total: int, current: str) -> str:
        if done < total:
            return f"Training model {done + 1}/{total}: {current}"
        return "Training complete."

    def work(progress):
        bundle = train_and_bundle_model(
            progress_callback=progress, include_xgboost=payload.include_xgboost
        )
        invalidate_cache()
        return bundle

    run_in_background(job_id, work, describe, _summarize)
    return JobStartedResponse(job_id=job_id)


@router.post("/audio", response_model=JobStartedResponse)
def train_audio() -> JobStartedResponse:
    n_hit = len(collect_audio_files(AUDIO_DIR / "hit"))
    n_flop = len(collect_audio_files(AUDIO_DIR / "not_hit"))
    if n_hit == 0 or n_flop == 0:
        raise HTTPException(
            status_code=400,
            detail="Add at least one song to BOTH data/audio/hit/ and data/audio/not_hit/.",
        )

    job_id = create_job("audio")

    def describe(done: int, total: int, current: str) -> str:
        if done < total:
            return f"Extracting features {done + 1}/{total}: {current}"
        return "Training complete."

    def work(progress):
        bundle = train_from_audio_folders(progress_callback=progress)
        invalidate_cache()
        return bundle

    run_in_background(job_id, work, describe, _summarize)
    return JobStartedResponse(job_id=job_id)


@router.get("/jobs/{job_id}")
def read_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown training job.")
    return job
