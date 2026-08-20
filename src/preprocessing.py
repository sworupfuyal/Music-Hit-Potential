"""Preprocessing utilities for hit prediction."""

from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def add_hit_label(
	df: pd.DataFrame,
	popularity_col: str = "popularity",
	threshold: int = 70,
	target_col: str = "hit",
) -> pd.DataFrame:
	"""Create a binary hit label from a popularity score column."""
	if popularity_col not in df.columns:
		raise ValueError(f"Missing required column: {popularity_col}")

	labeled = df.copy()
	labeled[target_col] = (labeled[popularity_col] >= threshold).astype(int)
	return labeled


def temporal_split(
	df: pd.DataFrame,
	time_col: str,
	target_col: str = "hit",
	test_size: float = 0.2,
):
	"""Split a dataset by time to reduce leakage.

	If the time column is unavailable, this function falls back to stratified random split.
	"""
	if target_col not in df.columns:
		raise ValueError(f"Missing target column: {target_col}")

	if time_col not in df.columns:
		x = df.drop(columns=[target_col])
		y = df[target_col]
		return train_test_split(x, y, test_size=test_size, random_state=42, stratify=y)

	ordered = df.sort_values(time_col).reset_index(drop=True)
	split_idx = int((1 - test_size) * len(ordered))

	train_df = ordered.iloc[:split_idx]
	test_df = ordered.iloc[split_idx:]

	x_train = train_df.drop(columns=[target_col])
	y_train = train_df[target_col]
	x_test = test_df.drop(columns=[target_col])
	y_test = test_df[target_col]
	return x_train, x_test, y_train, y_test


def make_preprocessor(
	numeric_features: Iterable[str],
	categorical_features: Iterable[str],
) -> ColumnTransformer:
	"""Build a sklearn preprocessor with numeric scaling and categorical encoding."""
	numeric_pipeline = Pipeline(
		steps=[
			("imputer", SimpleImputer(strategy="median")),
			("scaler", StandardScaler()),
		]
	)

	categorical_pipeline = Pipeline(
		steps=[
			("imputer", SimpleImputer(strategy="most_frequent")),
			("encoder", OneHotEncoder(handle_unknown="ignore")),
		]
	)

	return ColumnTransformer(
		transformers=[
			("num", numeric_pipeline, list(numeric_features)),
			("cat", categorical_pipeline, list(categorical_features)),
		]
	)

def clean_dataset(
	df: pd.DataFrame,
	time_col: str = "first_week",
	now: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict]:
	"""Apply the Phase 2 cleaning step: drop duplicates and impossible dates.

	Rows whose chronological column cannot be parsed, or which carry a date in the
	future, are removed. This matters because the temporal split sorts on that column
	and takes the tail as the test set: with corrupt future dates present, the holdout
	is drawn from those rows rather than from genuinely recent releases.

	Returns the cleaned frame and a report of every exclusion, so the counts can be
	quoted directly in the write-up.
	"""
	frame = df.copy()
	frame.columns = [c.lower() for c in frame.columns]
	column = time_col.lower()
	cutoff = pd.Timestamp(now) if now is not None else pd.Timestamp.now()

	report: dict = {
		"rows_in": int(len(frame)),
		"duplicates_dropped": 0,
		"unparseable_dates_dropped": 0,
		"future_dates_dropped": 0,
		"cutoff": str(cutoff.date()),
		"date_min_before": None,
		"date_max_before": None,
		"date_min_after": None,
		"date_max_after": None,
	}

	before = len(frame)
	frame = frame.drop_duplicates().reset_index(drop=True)
	report["duplicates_dropped"] = int(before - len(frame))

	if column in frame.columns:
		parsed = pd.to_datetime(frame[column], errors="coerce", format="mixed")
		valid_before = parsed.dropna()
		if len(valid_before):
			report["date_min_before"] = str(valid_before.min().date())
			report["date_max_before"] = str(valid_before.max().date())

		unparseable = parsed.isna()
		future = parsed > cutoff
		report["unparseable_dates_dropped"] = int(unparseable.sum())
		report["future_dates_dropped"] = int(future.sum())

		frame[column] = parsed
		frame = frame.loc[~(unparseable | future)].reset_index(drop=True)

		kept = frame[column].dropna()
		if len(kept):
			report["date_min_after"] = str(kept.min().date())
			report["date_max_after"] = str(kept.max().date())

	report["rows_out"] = int(len(frame))
	report["rows_dropped_total"] = report["rows_in"] - report["rows_out"]
	return frame, report

def canonical_genre(series: pd.Series, min_count: int = 100, other: str = "other") -> pd.Series:
	"""Collapse a long-tailed genre column to labels with enough support to analyse.

	Groups holding fewer than `min_count` tracks become a single "other" bucket. Without
	this, per-group fairness metrics are dominated by groups of one or two tracks that
	score exactly 0.0 or 1.0 by accident.
	"""
	values = series.fillna(other).astype(str)
	counts = values.value_counts()
	keep = set(counts[counts >= min_count].index)
	return values.where(values.isin(keep), other)


def balanced_case_control_sample(
	df: pd.DataFrame,
	label_col: str = "hit",
	time_col: str = "first_week",
	genre_col: str = "genre",
	random_state: int = 42,
) -> tuple[pd.DataFrame, dict]:
	"""Draw a 1:1 case-control sample, matching each hit to a non-hit from the same era.

	At the natural ~17% positive rate a classifier that always answers "not a hit" scores
	about 89% accuracy, so accuracy carries almost no information. Balancing restores it as
	a usable metric and makes results comparable with the published hit-prediction studies,
	which are generally run on balanced samples.

	Controls are matched on release year — and on genre where a same-year, same-genre
	candidate exists — so the model cannot separate the classes on production era or genre
	mix alone. Matching is done without replacement.

	The trade-off is that the resulting sample no longer reflects real-world prevalence, so
	predicted probabilities from it are not calibrated to the true base rate. Report
	discrimination on this sample and calibration on the natural-prevalence one.
	"""
	rng = np.random.default_rng(random_state)
	frame = df.copy()
	frame.columns = [c.lower() for c in frame.columns]

	years = pd.to_datetime(frame[time_col], errors="coerce").dt.year
	genres = (
		frame[genre_col].fillna("unknown").astype(str)
		if genre_col in frame.columns
		else pd.Series("unknown", index=frame.index)
	)

	hits = frame.index[frame[label_col] == 1]
	controls = frame.index[frame[label_col] == 0]

	# Pools of available controls, keyed by (year, genre) and by year alone.
	pairs: dict[tuple, list] = {}
	by_year: dict[object, list] = {}
	for idx in controls:
		pairs.setdefault((years[idx], genres[idx]), []).append(idx)
		by_year.setdefault(years[idx], []).append(idx)
	for pool in pairs.values():
		rng.shuffle(pool)
	for pool in by_year.values():
		rng.shuffle(pool)

	used: set = set()
	chosen: list = []
	matched_exact = matched_year_only = unmatched = 0

	for idx in hits:
		key = (years[idx], genres[idx])
		partner = None

		pool = pairs.get(key)
		while pool:
			candidate = pool.pop()
			if candidate not in used:
				partner = candidate
				matched_exact += 1
				break

		if partner is None:
			pool = by_year.get(years[idx])
			while pool:
				candidate = pool.pop()
				if candidate not in used:
					partner = candidate
					matched_year_only += 1
					break

		if partner is None:
			unmatched += 1
			continue

		used.add(partner)
		chosen.extend([idx, partner])

	sample = frame.loc[chosen].sort_values(time_col).reset_index(drop=True)
	report = {
		"hits_available": int(len(hits)),
		"controls_available": int(len(controls)),
		"matched_year_and_genre": int(matched_exact),
		"matched_year_only": int(matched_year_only),
		"hits_unmatched": int(unmatched),
		"rows_out": int(len(sample)),
		"positive_rate": float(sample[label_col].mean()) if len(sample) else 0.0,
	}
	return sample, report
