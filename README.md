# Music Hit Prediction

## Project Goal
Predict whether a track is likely to become a hit using Spotify audio features and historical chart outcomes.

## Repository Structure
- data/raw: source files from Spotify API, Billboard, and other datasets.
- data/processed: cleaned and feature-engineered tables used for modeling.
- notebooks: sequential project workflow from exploration to evaluation.
- src: reusable Python modules for loading, preprocessing, modeling, and evaluation.
- models/saved_models: serialized trained models.
- reports/figures: visual outputs.
- reports/results: metric tables and experiment logs.

## Suggested Workflow
1. Collect and place source data in data/raw.
2. Run notebook 01 for EDA and label sanity checks.
3. Use src/preprocessing.py to generate labels, split data, and build preprocessor.
4. Train baseline and candidate models via src/model.py.
5. Evaluate global and subgroup performance with src/evaluation.py.
6. Save outputs to reports/results and selected models to models/saved_models.

## Quick Start
1. Create and activate a Python virtual environment.
2. Install dependencies from requirements.txt.
3. Start with notebooks/01_data_exploration.ipynb.

## Application Interface
Run the app from the project root:
1. `pip install -r requirements.txt`
2. `streamlit run app.py`

What the app does:
- Loads a saved model bundle from models/saved_models/hit_app_bundle.joblib.
- If the bundle does not exist, it trains one from data/raw/spotify.csv.
- Provides single-song and batch CSV hit potential prediction.
- Provides Spotify URL/ID auto-fetch prediction using Spotify Web API.

Spotify auto-fetch setup:
1. Create a Spotify developer app at https://developer.spotify.com/dashboard.
2. Copy Client ID and Client Secret.
3. Provide credentials in the app sidebar, or set environment variables:
	- SPOTIFY_CLIENT_ID
	- SPOTIFY_CLIENT_SECRET

## Initial Target Definition
Default label logic in the starter code:
- hit = 1 when popularity >= 70
- hit = 0 otherwise

You can change this threshold in src/preprocessing.py based on your final research criteria.
