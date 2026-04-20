"""Preprocessing utilities for hit prediction."""

from typing import Iterable

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

