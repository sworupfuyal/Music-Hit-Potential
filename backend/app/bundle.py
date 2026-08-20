"""Loading, caching and JSON serialisation of the trained model bundle.

The joblib bundle holds a fitted sklearn pipeline plus the metadata the UI needs
to build its input form and charts. It is cached in memory and reloaded whenever
the file on disk changes (i.e. after a training run).
"""

import math
import threading
from typing import Any

import joblib
import numpy as np

from .paths import BUNDLE_PATH

_lock = threading.Lock()
_cache: dict | None = None
_cache_mtime: float | None = None


def bundle_exists() -> bool:
    return BUNDLE_PATH.exists()


def get_bundle() -> dict:
    """Return the cached bundle, reloading it if the file changed on disk."""
    global _cache, _cache_mtime

    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(
            "No saved app model found yet. Train one to unlock predictions."
        )

    mtime = BUNDLE_PATH.stat().st_mtime
    with _lock:
        if _cache is None or _cache_mtime != mtime:
            _cache = joblib.load(BUNDLE_PATH)
            _cache_mtime = mtime
        return _cache


def invalidate_cache() -> None:
    """Drop the cached bundle so the next read picks up a freshly trained model."""
    global _cache, _cache_mtime
    with _lock:
        _cache = None
        _cache_mtime = None


def safe_float(value: Any) -> float | None:
    """Coerce to a JSON-safe float; NaN/inf become None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def bundle_metadata(bundle: dict) -> dict:
    """Everything the frontend needs about the model, minus the pipeline itself."""
    return {
        "exists": True,
        "model_name": bundle.get("model_name"),
        "f1_macro": safe_float(bundle.get("f1_macro")),
        "feature_columns": list(bundle.get("feature_columns", [])),
        "numeric_columns": list(bundle.get("numeric_columns", [])),
        "categorical_columns": list(bundle.get("categorical_columns", [])),
        "category_options": {
            key: list(values)
            for key, values in (bundle.get("category_options") or {}).items()
        },
        "numeric_defaults": {
            key: safe_float(value)
            for key, value in (bundle.get("numeric_defaults") or {}).items()
        },
        "feature_ranges": {
            key: [safe_float(pair[0]), safe_float(pair[1])]
            for key, pair in (bundle.get("feature_ranges") or {}).items()
        },
        "hit_profile": {
            key: safe_float(value) for key, value in (bundle.get("hit_profile") or {}).items()
        },
        "flop_profile": {
            key: safe_float(value) for key, value in (bundle.get("flop_profile") or {}).items()
        },
        "trained_on": bundle.get("trained_on"),
        "n_train_songs": bundle.get("n_train_songs"),
    }


def feature_importance(bundle: dict, top_n: int = 15) -> dict | None:
    """Top drivers of hit prediction, extracted from the fitted pipeline.

    Returns names/values ordered ascending (ready for a horizontal bar chart),
    or None when the estimator exposes no importances.
    """
    pipeline = bundle.get("model")
    if pipeline is None:
        return None

    try:
        pre = pipeline.named_steps["preprocessor"]
        model = pipeline.named_steps["model"]
        names = list(pre.get_feature_names_out())
    except Exception:
        return None

    if hasattr(model, "feature_importances_"):
        importances = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, "coef_"):
        importances = np.abs(np.asarray(model.coef_, dtype=float)).ravel()
    else:
        return None

    if len(importances) != len(names):
        return None

    order = np.argsort(importances)[::-1][:top_n][::-1]
    return {
        "names": [str(names[i]).split("__")[-1] for i in order],
        "values": [float(importances[i]) for i in order],
        "top_n": int(min(top_n, len(names))),
    }
