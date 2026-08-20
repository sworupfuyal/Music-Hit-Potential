"""Experiment harness for the methodology the research proposal commits to.

Covers four things that were previously unimplemented:

* **Baselines** — majority-class and stratified-random dummies, so accuracy can be
  judged against the right comparator on a 17% positive rate rather than against
  chance.
* **Imbalance strategies** — none / class-weighting / SMOTE, compared under
  stratified k-fold CV. SMOTE is placed inside an imblearn pipeline so resampling
  happens per training fold and never touches validation or holdout data.
* **Tuning** — GridSearchCV with StratifiedKFold, fitted on the training portion
  only; the temporal holdout stays sealed for final evaluation.
* **Calibration** — reliability curves and Brier scores for the fitted models.

Everything here is deliberately parameterised on the number of folds and grid size
so a full run can be traded against a fast run.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbalancedPipeline
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline

try:  # pragma: no cover - optional dependency
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover
    XGBClassifier = None

RANDOM_STATE = 42
SCORING = "f1_macro"

# Imbalance strategies compared. "balanced" is the project's existing behaviour.
IMBALANCE_STRATEGIES = ("none", "balanced", "smote")


# --- Baselines ------------------------------------------------------------


def build_baselines(random_state: int = RANDOM_STATE) -> dict[str, DummyClassifier]:
    """Reference classifiers that learn nothing.

    `majority_class` is the comparator that matters for an imbalanced target:
    predicting "not a hit" for everything already scores ~83% accuracy here, so any
    accuracy claim has to clear that, not the 50% a random baseline implies.
    """
    return {
        "baseline_majority_class": DummyClassifier(strategy="most_frequent"),
        "baseline_stratified_random": DummyClassifier(
            strategy="stratified", random_state=random_state
        ),
    }


# --- Estimators per imbalance strategy ------------------------------------


def build_estimator(
    family: str,
    strategy: str,
    y_train: pd.Series | np.ndarray | None = None,
    random_state: int = RANDOM_STATE,
) -> Any:
    """Return an unfitted estimator for one (family, imbalance strategy) pair.

    Class weighting is expressed differently per library: scikit-learn takes
    `class_weight="balanced"`, while XGBoost takes a `scale_pos_weight` ratio, so the
    "balanced" strategy is translated rather than skipped.
    """
    weighted = strategy == "balanced"

    if family == "logistic_regression":
        return LogisticRegression(
            max_iter=2000,
            class_weight="balanced" if weighted else None,
            random_state=random_state,
        )

    if family == "random_forest":
        return RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced" if weighted else None,
            random_state=random_state,
            n_jobs=-1,
        )

    if family == "xgboost":
        if XGBClassifier is None:
            raise ValueError("xgboost is not installed")
        scale = 1.0
        if weighted and y_train is not None:
            positives = float(np.sum(np.asarray(y_train) == 1))
            negatives = float(np.sum(np.asarray(y_train) == 0))
            scale = negatives / positives if positives else 1.0
        return XGBClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=random_state,
            eval_metric="logloss",
            scale_pos_weight=scale,
        )

    raise ValueError(f"Unknown model family: {family}")


def build_pipeline(
    preprocessor,
    estimator,
    strategy: str,
    random_state: int = RANDOM_STATE,
) -> Pipeline | ImbalancedPipeline:
    """Wrap preprocessing + estimator, inserting SMOTE when that strategy is active.

    Using imblearn's Pipeline is what keeps resampling honest: inside GridSearchCV it
    is applied to each training fold only, so no synthetic row can reach a validation
    fold or the holdout.
    """
    if strategy == "smote":
        return ImbalancedPipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("smote", SMOTE(random_state=random_state)),
                ("model", estimator),
            ]
        )
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", estimator)])


# --- Hyperparameter grids -------------------------------------------------

# Kept small on purpose: the point is to demonstrate tuned selection under
# stratified CV, not to exhaust the space. `fast` halves them again.
SEARCH_SPACES: dict[str, dict[str, list]] = {
    "logistic_regression": {"model__C": [0.01, 0.1, 1.0, 10.0]},
    "random_forest": {
        "model__n_estimators": [200, 400],
        "model__max_depth": [None, 12],
        "model__min_samples_leaf": [1, 5],
    },
    "xgboost": {
        "model__max_depth": [4, 6],
        "model__learning_rate": [0.05, 0.15],
        "model__n_estimators": [200, 400],
    },
}

FAST_SEARCH_SPACES: dict[str, dict[str, list]] = {
    "logistic_regression": {"model__C": [0.1, 1.0]},
    "random_forest": {"model__n_estimators": [200], "model__max_depth": [None, 12]},
    "xgboost": {"model__max_depth": [4, 6], "model__learning_rate": [0.05]},
}


def search_space(family: str, fast: bool = False) -> dict[str, list]:
    spaces = FAST_SEARCH_SPACES if fast else SEARCH_SPACES
    return spaces.get(family, {})


# --- Cross-validated comparison ------------------------------------------


def stratified_folds(n_splits: int = 5, random_state: int = RANDOM_STATE) -> StratifiedKFold:
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)


def compare_imbalance_strategies(
    preprocessor_factory,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    families: Iterable[str],
    strategies: Iterable[str] = IMBALANCE_STRATEGIES,
    n_splits: int = 5,
    random_state: int = RANDOM_STATE,
    verbose: bool = True,
) -> pd.DataFrame:
    """Stage A: hold hyperparameters fixed and vary only the imbalance strategy.

    Separating this from tuning keeps the run affordable — the alternative is a grid
    search per strategy per family, which multiplies out to thousands of fits.
    """
    from sklearn.model_selection import cross_validate

    rows = []
    folds = stratified_folds(n_splits, random_state)

    for family in families:
        for strategy in strategies:
            estimator = build_estimator(family, strategy, y_train, random_state)
            pipeline = build_pipeline(
                preprocessor_factory(), estimator, strategy, random_state
            )
            if verbose:
                print(f"  CV {family} / imbalance={strategy} …", flush=True)
            scores = cross_validate(
                pipeline,
                x_train,
                y_train,
                cv=folds,
                scoring=["f1_macro", "roc_auc", "accuracy"],
                n_jobs=1,
                error_score="raise",
            )
            rows.append(
                {
                    "model": family,
                    "imbalance": strategy,
                    "f1_macro_mean": float(np.mean(scores["test_f1_macro"])),
                    "f1_macro_std": float(np.std(scores["test_f1_macro"])),
                    "roc_auc_mean": float(np.mean(scores["test_roc_auc"])),
                    "roc_auc_std": float(np.std(scores["test_roc_auc"])),
                    "accuracy_mean": float(np.mean(scores["test_accuracy"])),
                    "accuracy_std": float(np.std(scores["test_accuracy"])),
                    "fit_seconds_mean": float(np.mean(scores["fit_time"])),
                    "n_splits": int(n_splits),
                }
            )

    return pd.DataFrame(rows).sort_values("f1_macro_mean", ascending=False)


def tune_model(
    preprocessor,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    family: str,
    strategy: str,
    fast: bool = False,
    n_splits: int = 5,
    random_state: int = RANDOM_STATE,
) -> GridSearchCV:
    """Stage B: grid search one family under stratified k-fold CV.

    Fitted on the training portion only — the temporal holdout is never seen here.
    """
    estimator = build_estimator(family, strategy, y_train, random_state)
    pipeline = build_pipeline(preprocessor, estimator, strategy, random_state)
    grid = search_space(family, fast)

    search = GridSearchCV(
        pipeline,
        param_grid=grid,
        scoring=SCORING,
        cv=stratified_folds(n_splits, random_state),
        n_jobs=1,
        refit=True,
        return_train_score=False,
        error_score="raise",
    )
    search.fit(x_train, y_train)
    return search


# --- Calibration ----------------------------------------------------------


def calibration_table(
    fitted_models: dict[str, Any],
    x_test: pd.DataFrame,
    y_test: pd.Series,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Reliability-curve points plus a Brier score per model.

    A model can rank well (decent AUC) and still be badly calibrated, which matters
    here because the app presents the score to users as a percentage.
    """
    rows = []
    for name, model in fitted_models.items():
        if not hasattr(model, "predict_proba"):
            continue
        scores = model.predict_proba(x_test)[:, 1]
        true_frequency, predicted_value = calibration_curve(
            y_test, scores, n_bins=n_bins, strategy="uniform"
        )
        brier = float(brier_score_loss(y_test, scores))
        for predicted, observed in zip(predicted_value, true_frequency):
            rows.append(
                {
                    "model": name,
                    "predicted_probability": float(predicted),
                    "observed_frequency": float(observed),
                    "brier_score": brier,
                    "n_bins": int(n_bins),
                }
            )
    return pd.DataFrame(rows)


# --- Fairness -------------------------------------------------------------


def fairness_summary(group_metrics: pd.DataFrame, min_n: int = 30) -> dict:
    """Disparity statistics over groups large enough to be meaningful.

    Filtering is the whole point: with no minimum, groups of one or two samples score
    exactly 0.0 or 1.0 and swamp any real disparity signal.
    """
    kept = group_metrics[group_metrics["n_samples"] >= min_n]
    excluded = group_metrics[group_metrics["n_samples"] < min_n]

    summary = {
        "min_n": int(min_n),
        "groups_total": int(len(group_metrics)),
        "groups_kept": int(len(kept)),
        "groups_excluded": int(len(excluded)),
        "excluded_with_perfect_f1": int((excluded["f1_macro"] == 1.0).sum()),
    }

    if len(kept):
        best = kept.loc[kept["f1_macro"].idxmax()]
        worst = kept.loc[kept["f1_macro"].idxmin()]
        summary.update(
            {
                "f1_best_group": str(best["group"]),
                "f1_best": float(best["f1_macro"]),
                "f1_worst_group": str(worst["group"]),
                "f1_worst": float(worst["f1_macro"]),
                "f1_disparity": float(best["f1_macro"] - worst["f1_macro"]),
                "f1_mean": float(kept["f1_macro"].mean()),
                "f1_std": float(kept["f1_macro"].std()),
            }
        )

    return summary
