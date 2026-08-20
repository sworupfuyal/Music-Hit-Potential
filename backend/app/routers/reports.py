"""Model evaluation endpoints: stored metric tables plus live ROC/PR curves."""

from fastapi import APIRouter, HTTPException, Query

from .. import reports

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _guard(fn, *args, **kwargs):
    """Translate the analysis layer's exceptions into HTTP responses."""
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/model-comparison")
def read_model_comparison() -> dict:
    return _guard(reports.model_comparison)


@router.get("/confusion-matrix")
def read_confusion_matrix() -> dict:
    return _guard(reports.confusion_matrix)


@router.get("/genre-metrics")
def read_genre_metrics(min_n: int = Query(30, ge=1, le=5000)) -> dict:
    return _guard(reports.genre_metrics, min_n=min_n)


@router.get("/curves")
def read_curves() -> dict:
    return _guard(reports.curves)
