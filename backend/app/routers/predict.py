"""Prediction endpoints: single row, batch CSV, Spotify track, local audio file."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from src.audio_features import extract_from_bytes

from ..bundle import get_bundle, safe_float
from ..inference import (
    audio_feature_map,
    batch_predict,
    build_model_input_from_feature_map,
    get_batch_csv,
    numeric_feature_echo,
    predict_probability,
    store_batch_csv,
    summarize_batch,
)
from ..schemas import (
    AudioPredictionResponse,
    PredictionResponse,
    SinglePredictRequest,
    SpotifyPredictionResponse,
    SpotifyPredictRequest,
)
from ..spotify_client import build_spotify_feature_row

router = APIRouter(prefix="/api/predict", tags=["predict"])


def _require_bundle() -> dict:
    try:
        return get_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/single", response_model=PredictionResponse)
def predict_single(payload: SinglePredictRequest) -> PredictionResponse:
    bundle = _require_bundle()
    try:
        model_input = build_model_input_from_feature_map(bundle, payload.features)
        probability = predict_probability(bundle, model_input)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PredictionResponse(
        probability=probability,
        features=numeric_feature_echo(bundle, model_input),
    )


@router.post("/batch")
async def predict_batch(file: UploadFile = File(...)) -> dict:
    bundle = _require_bundle()
    csv_bytes = await file.read()

    try:
        output = batch_predict(bundle, csv_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Batch prediction failed: {exc}") from exc

    return {
        "download_id": store_batch_csv(output),
        "filename": file.filename,
        **summarize_batch(output),
    }


@router.get("/batch/{download_id}/csv")
def download_batch(download_id: str) -> Response:
    csv_bytes = get_batch_csv(download_id)
    if csv_bytes is None:
        raise HTTPException(status_code=404, detail="Batch result expired. Re-upload the CSV.")

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="batch_hit_potential_predictions.csv"'
            )
        },
    )


@router.post("/spotify", response_model=SpotifyPredictionResponse)
def predict_spotify(payload: SpotifyPredictRequest) -> SpotifyPredictionResponse:
    bundle = _require_bundle()

    if not payload.client_id or not payload.client_secret:
        raise HTTPException(
            status_code=400,
            detail="Please provide Spotify Client ID and Client Secret.",
        )

    try:
        feature_map, display_info = build_spotify_feature_row(
            payload.track, payload.client_id, payload.client_secret
        )
        model_input = build_model_input_from_feature_map(bundle, feature_map)
        probability = predict_probability(bundle, model_input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # The radar/MFCC charts read the fetched feature map, matching the old app.
    features = {
        key: safe_float(value)
        for key, value in feature_map.items()
        if isinstance(value, (int, float))
    }
    return SpotifyPredictionResponse(
        probability=probability, features=features, display=display_info
    )


@router.post("/audio", response_model=AudioPredictionResponse)
async def predict_audio(file: UploadFile = File(...)) -> AudioPredictionResponse:
    bundle = _require_bundle()
    audio_bytes = await file.read()

    try:
        audio_feats = extract_from_bytes(audio_bytes)
    except (RuntimeError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {exc}") from exc

    try:
        feature_map = audio_feature_map(audio_feats)
        model_input = build_model_input_from_feature_map(bundle, feature_map)
        probability = predict_probability(bundle, model_input)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {exc}") from exc

    features = {
        key: safe_float(value)
        for key, value in feature_map.items()
        if isinstance(value, (int, float))
    }
    return AudioPredictionResponse(
        probability=probability,
        features=features,
        audio_features={k: safe_float(v) for k, v in audio_feats.items()},
    )
