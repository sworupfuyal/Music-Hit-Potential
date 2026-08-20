"""Evaluation artefacts for the Model Evaluation page.

Two sources feed this: the CSVs written by `scripts/run_experiments.py` into
reports/results/, and a live recomputation of ROC/PR curves. The curves are computed
live rather than read from `eval_predictions.csv` because they should describe the
model the app is actually serving, which may differ from the experiment's winner.
"""

import threading

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from .bundle import get_bundle, safe_float
from .paths import BUNDLE_PATH, DATA_PATH, PROJECT_ROOT
from .training import prepare_model_frame

RESULTS_DIR = PROJECT_ROOT / "reports" / "results"

_curves_lock = threading.Lock()
_curves_cache: dict | None = None
_curves_key: tuple | None = None

# Downsample curve points for transport; the shape is preserved at this density.
_MAX_CURVE_POINTS = 300


def _read_results_csv(name: str) -> pd.DataFrame:
    path = RESULTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{name} not found in reports/results. "
            "Run: python scripts/run_experiments.py"
        )
    return pd.read_csv(path)


def _thin(values: np.ndarray) -> list[float]:
    """Evenly sample a curve down to a transportable number of points."""
    if len(values) <= _MAX_CURVE_POINTS:
        return [safe_float(v) for v in values]
    idx = np.linspace(0, len(values) - 1, _MAX_CURVE_POINTS).astype(int)
    return [safe_float(v) for v in values[idx]]


def model_comparison() -> dict:
    """Candidate-model metrics, including the measured baseline rows.

    The baselines are what make the table readable: on this holdout, always predicting
    "not a hit" scores ~89% accuracy and so beats every trained model on that metric,
    which is why macro F1 is the selection metric. `scripts/run_experiments.py` writes
    them as real fitted DummyClassifier results rather than derived numbers.
    """
    frame = _read_results_csv("model_comparison.csv")

    metric_columns = [
        c
        for c in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "roc_auc")
        if c in frame.columns
    ]

    rows = []
    for record in frame.to_dict(orient="records"):
        baseline = bool(record.get("is_baseline", False)) or str(
            record["model"]
        ).startswith("baseline_")
        row = {
            "model": str(record["model"]),
            "metrics": {m: safe_float(record.get(m)) for m in metric_columns},
            "baseline": baseline,
        }
        # Tuning detail, present only for the tuned families.
        for key in ("imbalance", "best_params"):
            value = record.get(key)
            if isinstance(value, str) and value:
                row[key] = value
        cv_mean = safe_float(record.get("cv_f1_macro_mean"))
        if cv_mean is not None:
            row["cv_f1_macro_mean"] = cv_mean
            row["cv_f1_macro_std"] = safe_float(record.get("cv_f1_macro_std"))
        rows.append(row)

    # Baselines first so the reference is read before the candidates.
    rows.sort(key=lambda r: (not r["baseline"],))
    return {"metrics": metric_columns, "rows": rows}


def confusion_matrix() -> dict:
    """The stored 2x2 matrix plus the rates derived from it."""
    frame = _read_results_csv("confusion_matrix.csv")
    numeric = frame.select_dtypes(include=["number"])
    if numeric.shape != (2, 2):
        raise ValueError("confusion_matrix.csv is not a 2x2 matrix.")

    tn, fp = int(numeric.iat[0, 0]), int(numeric.iat[0, 1])
    fn, tp = int(numeric.iat[1, 0]), int(numeric.iat[1, 1])
    total = tn + fp + fn + tp

    def ratio(numerator: int, denominator: int) -> float | None:
        return safe_float(numerator / denominator) if denominator else None

    return {
        "matrix": [[tn, fp], [fn, tp]],
        "labels": {"actual": ["Not a hit", "Hit"], "predicted": ["Not a hit", "Hit"]},
        "counts": {"tn": tn, "fp": fp, "fn": fn, "tp": tp, "total": total},
        "rates": {
            "accuracy": ratio(tn + tp, total),
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "specificity": ratio(tn, tn + fp),
            "false_positive_rate": ratio(fp, fp + tn),
            "positive_rate": ratio(fn + tp, total),
        },
    }


def genre_metrics(min_n: int = 30) -> dict:
    """Per-genre fairness metrics, filtered to groups large enough to mean anything.

    Most groups are tiny: at n>=30 only 19 of 145 survive, and 102 of the excluded
    ones score a perfect F1 purely because their sample size is one or two. The filter
    is the point of this endpoint, and the excluded counts are returned so the UI can
    say so out loud rather than presenting 1.0 scores as real.
    """
    # The runner writes both: *_all.csv unfiltered, and the n>=30 view. Filter from
    # the unfiltered table so this endpoint's own min_n stays meaningful.
    try:
        frame = _read_results_csv("genre_group_metrics_all.csv")
    except FileNotFoundError:
        frame = _read_results_csv("genre_group_metrics.csv")
    min_n = max(1, int(min_n))

    kept = frame[frame["n_samples"] >= min_n].sort_values("f1_macro", ascending=False)
    excluded = frame[frame["n_samples"] < min_n]

    return {
        "min_n": min_n,
        "total_groups": int(len(frame)),
        "kept_groups": int(len(kept)),
        "excluded_groups": int(len(excluded)),
        "excluded_perfect_scores": int((excluded["f1_macro"] == 1.0).sum()),
        "groups": [
            {
                "group": str(record["group"]),
                "n_samples": int(record["n_samples"]),
                "accuracy": safe_float(record["accuracy"]),
                "f1_macro": safe_float(record["f1_macro"]),
            }
            for record in kept.to_dict(orient="records")
        ],
        "all_groups": [
            {"n_samples": int(r["n_samples"]), "f1_macro": safe_float(r["f1_macro"])}
            for r in frame.to_dict(orient="records")
        ],
    }


def curves() -> dict:
    """Recompute ROC and precision-recall curves on the holdout split.

    Rebuilds the exact frame and 80/20 chronological split that training used, then
    scores the test portion with the saved pipeline. Cached against the bundle and
    dataset mtimes so repeated page views are free.
    """
    global _curves_cache, _curves_key

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    key = (BUNDLE_PATH.stat().st_mtime, DATA_PATH.stat().st_mtime)
    with _curves_lock:
        if _curves_cache is not None and _curves_key == key:
            return _curves_cache

    bundle = get_bundle()
    model_df = prepare_model_frame(pd.read_csv(DATA_PATH, low_memory=False))

    split_idx = int(0.8 * len(model_df))
    test_df = model_df.iloc[split_idx:]
    if test_df.empty:
        raise ValueError("Holdout split is empty; dataset is too small.")

    y_true = test_df["hit"].to_numpy()
    features = [c for c in bundle["feature_columns"] if c in test_df.columns]
    missing = [c for c in bundle["feature_columns"] if c not in test_df.columns]
    if missing:
        raise ValueError(
            "The saved model expects columns this dataset no longer has: "
            + ", ".join(missing[:6])
        )

    scores = bundle["model"].predict_proba(test_df[features])[:, 1]

    if len(np.unique(y_true)) < 2:
        raise ValueError("Holdout split contains a single class; curves are undefined.")

    fpr, tpr, _ = roc_curve(y_true, scores)
    precision, recall, _ = precision_recall_curve(y_true, scores)

    result = {
        "n_test": int(len(y_true)),
        "positive_rate": safe_float(float(y_true.mean())),
        "roc": {
            "fpr": _thin(fpr),
            "tpr": _thin(tpr),
            "auc": safe_float(roc_auc_score(y_true, scores)),
        },
        "pr": {
            "recall": _thin(recall),
            "precision": _thin(precision),
            "average_precision": safe_float(average_precision_score(y_true, scores)),
        },
        "model_name": bundle.get("model_name"),
    }

    with _curves_lock:
        _curves_cache = result
        _curves_key = key
    return result
