"""Run the full evaluation methodology and regenerate every artefact in reports/results.

Executes, in order: Phase 2 cleaning, the temporal split, baselines, an imbalance-strategy
comparison under stratified k-fold CV, grid-search tuning per model family, holdout
evaluation, calibration, and the genre fairness analysis. Finishes by printing explicit
verdicts on the three research hypotheses.

Usage (from the project root):
    python scripts/run_experiments.py                 # full grids
    python scripts/run_experiments.py --fast          # smaller grids
    python scripts/run_experiments.py --no-xgboost    # skip XGBoost
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.metrics import confusion_matrix  # noqa: E402

from backend.app.training import prepare_model_frame  # noqa: E402
from src.evaluation import classification_metrics, metrics_by_group  # noqa: E402
from src.experiments import (  # noqa: E402
    build_baselines,
    calibration_table,
    compare_imbalance_strategies,
    fairness_summary,
    search_space,
    tune_model,
)
from src.preprocessing import (  # noqa: E402
    balanced_case_control_sample,
    canonical_genre,
    clean_dataset,
    make_preprocessor,
)

DATA_PATH = ROOT / "data" / "raw" / "spotify.csv"
RESULTS_DIR = ROOT / "reports" / "results"
MIN_GROUP_N = 30
TEST_FRACTION = 0.2


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="use reduced grids")
    parser.add_argument("--no-xgboost", action="store_true", help="skip XGBoost")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument(
        "--balanced",
        action="store_true",
        help="draw a 1:1 year/genre-matched case-control sample before training",
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # --- Phase 2: cleaning -------------------------------------------------
    banner("PHASE 2  Data cleaning")
    raw = pd.read_csv(DATA_PATH, low_memory=False)
    cleaned, report = clean_dataset(raw)
    for key, value in report.items():
        print(f"  {key:28} {value}")
    pd.DataFrame([report]).to_csv(RESULTS_DIR / "cleaning_report.csv", index=False)

    # Persist the cleaned frame so the sample can be inspected or reused elsewhere.
    processed_dir = ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(processed_dir / "spotify_clean.csv", index=False)
    print(f"  wrote data/processed/spotify_clean.csv ({len(cleaned):,} rows)")

    # --- Optional case-control sampling -----------------------------------
    suffix = ""
    frame = cleaned
    if args.balanced:
        banner("SAMPLING  1:1 case-control, matched on release year and genre")
        frame, sample_report = balanced_case_control_sample(cleaned)
        for key, value in sample_report.items():
            print(f"  {key:28} {value}")
        pd.DataFrame([sample_report]).to_csv(
            RESULTS_DIR / "sampling_report.csv", index=False
        )
        suffix = "_balanced"
        print()
        print("  NOTE: a balanced sample does not reflect real prevalence, so the")
        print("        probabilities it produces are not calibrated to the true base")
        print("        rate. Report discrimination from this run and calibration from")
        print("        the natural-prevalence run.")

    def out(name: str) -> Path:
        """Result path, namespaced so a balanced run never clobbers the natural one."""
        stem, ext = name.rsplit(".", 1)
        return RESULTS_DIR / f"{stem}{suffix}.{ext}"

    model_df = prepare_model_frame(frame, clean=False)
    print(f"\n  model frame: {model_df.shape[0]:,} rows x {model_df.shape[1]} columns")

    # --- Temporal split ----------------------------------------------------
    banner("PHASE 4  Temporal holdout split")
    split_idx = int((1 - TEST_FRACTION) * len(model_df))
    x_train = model_df.iloc[:split_idx].drop(columns=["hit"])
    y_train = model_df.iloc[:split_idx]["hit"]
    x_test = model_df.iloc[split_idx:].drop(columns=["hit"])
    y_test = model_df.iloc[split_idx:]["hit"]

    numeric = x_train.select_dtypes(include=["number"]).columns.tolist()
    categorical = [c for c in x_train.columns if c not in numeric]
    holdout_positive_rate = float(y_test.mean())

    print(f"  train {len(x_train):,} rows   positive rate {y_train.mean():.4f}")
    print(f"  test  {len(x_test):,} rows   positive rate {holdout_positive_rate:.4f}")
    print(f"  features: {len(numeric)} numeric, {len(categorical)} categorical")

    families = ["logistic_regression", "random_forest"]
    if not args.no_xgboost:
        families.append("xgboost")

    def preprocessor_factory():
        return make_preprocessor(numeric, categorical)

    # --- Baselines ---------------------------------------------------------
    banner("BASELINES  (the comparator H1 actually needs)")
    result_rows = []
    fitted: dict = {}

    for name, dummy in build_baselines().items():
        dummy.fit(x_train[numeric].fillna(0), y_train)
        predictions = dummy.predict(x_test[numeric].fillna(0))
        scores = (
            dummy.predict_proba(x_test[numeric].fillna(0))[:, 1]
            if hasattr(dummy, "predict_proba")
            else None
        )
        metrics = classification_metrics(y_test, predictions, scores)
        print(f"  {name:28} " + "  ".join(f"{k}={v:.4f}" for k, v in metrics.items()))
        result_rows.append({"model": name, "is_baseline": True, **metrics})

    # --- Phase 2: imbalance strategies under stratified k-fold CV ----------
    banner(f"PHASE 2/3  Imbalance strategies, {args.folds}-fold stratified CV")
    print("  SMOTE runs inside an imblearn pipeline, so it resamples training folds only.\n")
    imbalance = compare_imbalance_strategies(
        preprocessor_factory, x_train, y_train, families, n_splits=args.folds
    )
    imbalance.to_csv(out("imbalance_comparison.csv"), index=False)
    print()
    print(
        imbalance[
            ["model", "imbalance", "f1_macro_mean", "f1_macro_std", "roc_auc_mean", "accuracy_mean"]
        ].to_string(index=False, float_format=lambda v: f"{v:.4f}")
    )

    best_strategy = {
        family: imbalance[imbalance["model"] == family]
        .sort_values("f1_macro_mean", ascending=False)
        .iloc[0]["imbalance"]
        for family in families
    }
    print("\n  best imbalance strategy per family:", best_strategy)

    # --- Phase 3: grid search ---------------------------------------------
    banner(f"PHASE 3  Grid search, {args.folds}-fold stratified CV on the training split")
    tuned_summary = []
    for family in families:
        strategy = best_strategy[family]
        grid = search_space(family, args.fast)
        combos = int(np.prod([len(v) for v in grid.values()])) if grid else 1
        print(f"\n  {family} (imbalance={strategy}) — {combos} combinations x {args.folds} folds")
        t0 = time.time()
        search = tune_model(
            preprocessor_factory(),
            x_train,
            y_train,
            family,
            strategy,
            fast=args.fast,
            n_splits=args.folds,
        )
        elapsed = time.time() - t0
        index = int(search.best_index_)
        cv_mean = float(search.cv_results_["mean_test_score"][index])
        cv_std = float(search.cv_results_["std_test_score"][index])
        print(f"    best params : {search.best_params_}")
        print(f"    CV f1_macro : {cv_mean:.4f} +/- {cv_std:.4f}   ({elapsed:.0f}s)")

        model = search.best_estimator_
        fitted[family] = model
        predictions = model.predict(x_test)
        scores = model.predict_proba(x_test)[:, 1]
        metrics = classification_metrics(y_test, predictions, scores)
        print("    holdout     : " + "  ".join(f"{k}={v:.4f}" for k, v in metrics.items()))

        result_rows.append(
            {
                "model": family,
                "is_baseline": False,
                **metrics,
                "imbalance": strategy,
                "cv_f1_macro_mean": cv_mean,
                "cv_f1_macro_std": cv_std,
                "best_params": json.dumps(search.best_params_),
            }
        )
        tuned_summary.append(
            {"model": family, "cv_mean": cv_mean, "cv_std": cv_std, "holdout_f1": metrics["f1_macro"]}
        )

    # SMOTE must never have touched the holdout.
    assert float(y_test.mean()) == holdout_positive_rate, "holdout was modified"
    print(f"\n  holdout positive rate unchanged at {holdout_positive_rate:.4f} — no resampling leak")

    # --- Artefacts ---------------------------------------------------------
    banner("ARTEFACTS  reports/results")
    comparison = pd.DataFrame(result_rows)
    comparison.to_csv(out("model_comparison.csv"), index=False)
    print(f"  model_comparison.csv        {len(comparison)} rows")

    # Final model chosen on cross-validated score, never on the holdout.
    best = max(tuned_summary, key=lambda r: r["cv_mean"])
    best_name = best["model"]
    best_model = fitted[best_name]
    print(f"  selected by CV: {best_name} (CV f1_macro {best['cv_mean']:.4f})")

    predictions = best_model.predict(x_test)
    scores = best_model.predict_proba(x_test)[:, 1]
    final_metrics = classification_metrics(y_test, predictions, scores)
    pd.DataFrame([{"model": best_name, **final_metrics}]).to_csv(
        out("final_metrics.csv"), index=False
    )
    print("  final_metrics.csv")

    matrix = confusion_matrix(y_test, predictions)
    pd.DataFrame(
        matrix, index=["actual_0", "actual_1"], columns=["pred_0", "pred_1"]
    ).to_csv(out("confusion_matrix.csv"), index=True)
    print("  confusion_matrix.csv")

    # y_score was missing before, which is why ROC/PR had to be recomputed live.
    eval_df = pd.DataFrame(
        {
            "y_true": y_test.to_numpy(),
            "y_pred": predictions,
            "y_score": scores,
            "genre": x_test["genre"].to_numpy() if "genre" in x_test.columns else "unknown",
        }
    )
    eval_df.to_csv(out("eval_predictions.csv"), index=False)
    print("  eval_predictions.csv        (now includes y_score)")

    calibration = calibration_table(fitted, x_test, y_test)
    calibration.to_csv(out("calibration.csv"), index=False)
    briers = calibration.groupby("model")["brier_score"].first().to_dict()
    print("  calibration.csv             Brier: " + ", ".join(f"{k}={v:.4f}" for k, v in briers.items()))

    # Collapse the long tail before grouping so the metrics describe real cohorts.
    eval_df["genre_canonical"] = canonical_genre(eval_df["genre"], min_count=30).to_numpy()
    canonical = metrics_by_group(eval_df, "y_true", "y_pred", "genre_canonical")
    canonical.to_csv(out("genre_canonical_metrics.csv"), index=False)
    print(f"  genre_canonical_metrics.csv {len(canonical)} collapsed groups")

    groups = metrics_by_group(eval_df, "y_true", "y_pred", "genre")
    groups.to_csv(out("genre_group_metrics_all.csv"), index=False)
    kept = groups[groups["n_samples"] >= MIN_GROUP_N]
    kept.to_csv(out("genre_group_metrics.csv"), index=False)
    summary = fairness_summary(groups, MIN_GROUP_N)
    pd.DataFrame([summary]).to_csv(out("fairness_summary.csv"), index=False)
    print(f"  genre_group_metrics.csv     {len(kept)} groups at n>={MIN_GROUP_N}")
    print("  fairness_summary.csv")

    # --- Hypothesis verdicts ----------------------------------------------
    banner("HYPOTHESIS VERDICTS")
    majority = comparison[comparison["model"] == "baseline_majority_class"].iloc[0]
    random_row = comparison[comparison["model"] == "baseline_stratified_random"].iloc[0]
    tuned = comparison[~comparison["is_baseline"]]
    best_accuracy = tuned["accuracy"].max()
    best_acc_model = tuned.loc[tuned["accuracy"].idxmax(), "model"]

    print("H1  accuracy > 70% and beats a random baseline")
    print(f"      best tuned accuracy      {best_accuracy:.4f}  ({best_acc_model})")
    print(f"      stratified-random        {random_row['accuracy']:.4f}")
    print(f"      majority-class           {majority['accuracy']:.4f}")
    print(f"      > 70%?                   {'YES' if best_accuracy > 0.70 else 'NO'}")
    print(f"      beats random?            {'YES' if best_accuracy > random_row['accuracy'] else 'NO'}")
    print(
        f"      beats majority class?    {'YES' if best_accuracy > majority['accuracy'] else 'NO'}"
        "   <- the comparator that matters on an imbalanced target"
    )
    print(
        f"      macro F1 vs majority     {tuned['f1_macro'].max():.4f} vs {majority['f1_macro']:.4f}"
    )

    print("\nH2  ensembles (RF, XGBoost) outperform logistic regression")
    for row in sorted(tuned_summary, key=lambda r: r["cv_mean"], reverse=True):
        print(
            f"      {row['model']:22} CV f1_macro {row['cv_mean']:.4f} +/- {row['cv_std']:.4f}"
            f"   holdout {row['holdout_f1']:.4f}"
        )
    lr = next((r for r in tuned_summary if r["model"] == "logistic_regression"), None)
    ensembles = [r for r in tuned_summary if r["model"] != "logistic_regression"]
    if lr and ensembles:
        winner = max(ensembles, key=lambda r: r["cv_mean"])
        beats = winner["cv_mean"] > lr["cv_mean"]
        margin = abs(winner["cv_mean"] - lr["cv_mean"])
        overlapping = margin < (winner["cv_std"] + lr["cv_std"])
        print(f"      best ensemble beats LR?  {'YES' if beats else 'NO (H2 not supported)'}")
        print(
            f"      margin {margin:.4f} vs combined std {winner['cv_std'] + lr['cv_std']:.4f}"
            f" -> {'within noise' if overlapping else 'outside noise'}"
        )

    print("\nH3  measurable genre disparities")
    for key, value in summary.items():
        print(f"      {key:26} {value if not isinstance(value, float) else f'{value:.4f}'}")

    print(f"\nDone in {time.time() - started:.0f}s. Artefacts in {RESULTS_DIR}")


if __name__ == "__main__":
    main()
