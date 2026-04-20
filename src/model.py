"""Model utilities for training and inference."""

from typing import Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

try:
	from xgboost import XGBClassifier
except ImportError:  # pragma: no cover
	XGBClassifier = None


def build_baseline_model(random_state: int = 42) -> LogisticRegression:
	"""Return the baseline logistic regression classifier."""
	return LogisticRegression(
		max_iter=2000,
		class_weight="balanced",
		random_state=random_state,
	)


def build_candidate_models(random_state: int = 42) -> dict[str, Any]:
	"""Return candidate models for comparison experiments."""
	models: dict[str, Any] = {
		"logistic_regression": build_baseline_model(random_state=random_state),
		"random_forest": RandomForestClassifier(
			n_estimators=300,
			max_depth=None,
			min_samples_split=2,
			class_weight="balanced",
			random_state=random_state,
			n_jobs=-1,
		),
	}

	if XGBClassifier is not None:
		models["xgboost"] = XGBClassifier(
			n_estimators=300,
			learning_rate=0.05,
			max_depth=6,
			subsample=0.9,
			colsample_bytree=0.9,
			random_state=random_state,
			eval_metric="logloss",
		)

	return models


def train_pipeline(preprocessor, estimator, x_train, y_train) -> Pipeline:
	"""Fit and return a preprocessing + model pipeline."""
	pipeline = Pipeline(
		steps=[
			("preprocessor", preprocessor),
			("model", estimator),
		]
	)
	pipeline.fit(x_train, y_train)
	return pipeline


def predict_with_scores(model: Pipeline, x_test):
	"""Predict labels and scores from a fitted pipeline."""
	y_pred = model.predict(x_test)

	if hasattr(model, "predict_proba"):
		y_score = model.predict_proba(x_test)[:, 1]
	elif hasattr(model, "decision_function"):
		y_score = model.decision_function(x_test)
	else:
		y_score = None

	return y_pred, y_score

