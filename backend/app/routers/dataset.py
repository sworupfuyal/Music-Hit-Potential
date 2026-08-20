"""Dataset Explorer endpoints. Everything returned is pre-aggregated."""

from fastapi import APIRouter, HTTPException, Query

from .. import dataset

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/summary")
def read_summary() -> dict:
    return _guard(dataset.summary)


@router.get("/distributions")
def read_distribution(
    feature: str = Query(..., min_length=1),
    bins: int = Query(30, ge=5, le=80),
) -> dict:
    return _guard(dataset.feature_distribution, feature=feature, bins=bins)


@router.get("/correlations")
def read_correlations() -> dict:
    return _guard(dataset.correlations)


@router.get("/genres")
def read_genres(
    column: str | None = Query(None),
    top: int = Query(15, ge=3, le=40),
) -> dict:
    return _guard(dataset.genre_distribution, column=column, top=top)


@router.get("/hit-rate-by-year")
def read_hit_rate_by_year(min_count: int = Query(10, ge=1, le=1000)) -> dict:
    return _guard(dataset.hit_rate_by_year, min_count=min_count)
