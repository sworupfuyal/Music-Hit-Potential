"""Evaluation utilities for model performance and bias checks."""

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


def classification_metrics(y_true, y_pred, y_score=None) -> dict[str, float]:
	"""Return core classification metrics for binary hit prediction."""
	metrics = {
		"accuracy": accuracy_score(y_true, y_pred),
		"precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
		"recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
		"f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
	}

	if y_score is not None:
		metrics["roc_auc"] = roc_auc_score(y_true, y_score)

	return metrics


def metrics_by_group(
	frame: pd.DataFrame,
	y_true_col: str,
	y_pred_col: str,
	group_col: str,
) -> pd.DataFrame:
	"""Compute per-group accuracy and macro F1 for fairness analysis."""
	if group_col not in frame.columns:
		raise ValueError(f"Missing group column: {group_col}")

	rows = []
	for group_name, group_df in frame.groupby(group_col):
		y_true = group_df[y_true_col]
		y_pred = group_df[y_pred_col]
		rows.append(
			{
				"group": group_name,
				"n_samples": int(len(group_df)),
				"accuracy": accuracy_score(y_true, y_pred),
				"f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
			}
		)

	return pd.DataFrame(rows).sort_values("f1_macro", ascending=False)