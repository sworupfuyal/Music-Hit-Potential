"""Model status and interpretability endpoints."""

from fastapi import APIRouter, HTTPException

from ..bundle import bundle_exists, bundle_metadata, feature_importance, get_bundle

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("")
def read_model() -> dict:
    """Bundle metadata, or `exists: false` when no model has been trained yet."""
    if not bundle_exists():
        return {"exists": False, "error": None}

    try:
        bundle = get_bundle()
    except Exception as exc:
        # Mirrors the old app's warning when a stale bundle cannot be unpickled.
        return {"exists": False, "error": f"Existing saved bundle could not be loaded: {exc}"}

    return bundle_metadata(bundle)


@router.get("/importance")
def read_importance(top_n: int = 15) -> dict:
    """Top hit drivers pulled from the fitted pipeline, or `available: false`."""
    try:
        bundle = get_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    importance = feature_importance(bundle, top_n=top_n)
    if importance is None:
        return {"available": False}
    return {"available": True, **importance}
