 Music Hit Prediction

 Project Goal
I built this project to predict whether a song is likely to become a hit using Spotify audio features and chart-related signals.

 Repository Structure
- data/raw: raw source files (Spotify API, Billboard, and similar sources).
- data/processed: cleaned and feature-engineered files used for modeling.
- notebooks: my step-by-step workflow from exploration to evaluation.
- src: reusable Python modules for data loading, preprocessing, modeling, and evaluation.
- models/saved_models: serialized trained model bundles.
- reports/figures: visual outputs.
- reports/results: metric tables and experiment outputs.

My Typical Workflow
1. I place source data in data/raw.
2. I run notebooks/01_data_exploration.ipynb for EDA and sanity checks.
3. I preprocess and label data using src/preprocessing.py.
4. I train baseline and candidate models using src/model.py.
5. I evaluate performance with src/evaluation.py.
6. I save reports and final model artifacts.

Quick Start
1. Create and activate a virtual environment.
2. Install dependencies:
	`pip install -r requirements.txt`
3. Run the app:
	`streamlit run app.py`

App Behavior
The app uses models/saved_models/hit_app_bundle.joblib.

- If the bundle exists, the app loads it.
- If the bundle does not exist, the app trains a new one from data/raw/spotify.csv.
- The app supports single prediction, batch CSV prediction, and Spotify URL/ID prediction.

 How I Retrain With a New Dataset
1. Replace data/raw/spotify.csv with my new dataset.
2. Make sure the dataset has either:
	- a hit column, or
	- a popularity (or track_popularity) column so hit can be auto-generated.
3. Delete the old model bundle:
	models/saved_models/hit_app_bundle.joblib
4. Run:
	`streamlit run app.py`
5. Click Train App Model in the app.

After training, a new bundle is saved to models/saved_models/hit_app_bundle.joblib.

Spotify Auto-Fetch Setup
1. Create a Spotify developer app: https://developer.spotify.com/dashboard
2. Copy Client ID and Client Secret.
3. Provide credentials in the app sidebar, or set environment variables:
	- SPOTIFY_CLIENT_ID
	- SPOTIFY_CLIENT_SECRET

 Target Definition
Current default label logic:
- hit = 1 when popularity >= 70
- hit = 0 otherwise

we can change this threshold in preprocessing logic based on future experiments.

