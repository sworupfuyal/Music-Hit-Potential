"""Request/response models for the API."""

from typing import Any

from pydantic import BaseModel, Field


class SinglePredictRequest(BaseModel):
    """Raw form values keyed by feature column name (numbers or category strings)."""

    features: dict[str, Any] = Field(default_factory=dict)


class SpotifyPredictRequest(BaseModel):
    track: str
    client_id: str
    client_secret: str


class TrainDatasetRequest(BaseModel):
    include_xgboost: bool = False


class PredictionResponse(BaseModel):
    probability: float
    features: dict[str, float | None]


class SpotifyPredictionResponse(PredictionResponse):
    display: dict[str, Any]


class AudioPredictionResponse(PredictionResponse):
    audio_features: dict[str, float | None]


class JobStartedResponse(BaseModel):
    job_id: str
