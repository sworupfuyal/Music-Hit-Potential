"""Data loading utilities for the music hit prediction project."""

from pathlib import Path

import pandas as pd


def get_project_root() -> Path:
	"""Return the project root based on the current file location."""
	return Path(__file__).resolve().parents[1]


def ensure_project_directories() -> None:
	"""Create key project directories if they are missing."""
	root = get_project_root()
	required = [
		root / "data" / "raw",
		root / "data" / "processed",
		root / "models" / "saved_models",
		root / "reports" / "figures",
		root / "reports" / "results",
	]
	for path in required:
		path.mkdir(parents=True, exist_ok=True)


def load_raw_csv(file_name: str) -> pd.DataFrame:
	"""Load a CSV file from data/raw."""
	csv_path = get_project_root() / "data" / "raw" / file_name
	if not csv_path.exists():
		raise FileNotFoundError(f"Raw data file not found: {csv_path}")
	return pd.read_csv(csv_path)


def save_processed_csv(df: pd.DataFrame, file_name: str, index: bool = False) -> Path:
	"""Save a DataFrame to data/processed and return the saved path."""
	ensure_project_directories()
	save_path = get_project_root() / "data" / "processed" / file_name
	df.to_csv(save_path, index=index)
	return save_path


def load_processed_csv(file_name: str) -> pd.DataFrame:
	"""Load a CSV file from data/processed."""
	csv_path = get_project_root() / "data" / "processed" / file_name
	if not csv_path.exists():
		raise FileNotFoundError(f"Processed data file not found: {csv_path}")
	return pd.read_csv(csv_path)