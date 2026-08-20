# Music Hit Prediction

## Project Goal
I built this project to predict whether a song is likely to become a hit using Spotify audio features and chart-related signals.

The app runs as two pieces: a **FastAPI** backend that owns the model and all feature extraction, and a **Next.js (TypeScript)** frontend that renders the UI and charts.

## Repository Structure
- `backend/app`: FastAPI service — routers, training jobs, Spotify lookups, inference.
- `frontend`: Next.js + TypeScript UI (App Router, Tailwind CSS, Plotly charts).
- `data/raw`: raw source files (Spotify API, Billboard, and similar sources).
- `data/processed`: cleaned and feature-engineered files used for modeling.
- `data/audio/{hit,not_hit}`: local audio used by the Spotify-free training path.
- `notebooks`: my step-by-step workflow from exploration to evaluation, ending with `06_tuning_and_validation.ipynb` (tuning, calibration, fairness).
- `src`: reusable Python modules for data loading, preprocessing, modeling, and evaluation — shared by the notebooks and the backend.
- `models/saved_models`: serialized trained model bundles.
- `reports/figures`: visual outputs.
- `reports/results`: metric tables and experiment outputs.
- `scripts`: CLI helpers (evaluation pipeline, dataset enrichment, audio training, thesis generation).

## My Typical Workflow
1. I place source data in `data/raw`.
2. I run `notebooks/01_data_exploration.ipynb` for EDA and sanity checks.
3. I preprocess and label data using `src/preprocessing.py`.
4. I train baseline and candidate models using `src/model.py`.
5. I evaluate performance with `src/evaluation.py`.
6. I save reports and final model artifacts.

## Quick Start

### 1. Backend (FastAPI)
```bash
python -m venv venv
venv\Scripts\activate          # Windows;  source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```
Run this from the project root. Interactive API docs: http://localhost:8000/docs

### 2. Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

The frontend reads the API location from `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). Copy `frontend/.env.local.example` to `frontend/.env.local` to change it.

For production: `npm run build && npm start`, and serve the API without `--reload`.

## App Behavior
The app uses `models/saved_models/hit_app_bundle.joblib`.

- If the bundle exists, the API loads and caches it, reloading automatically after a retrain.
- If the bundle does not exist, the UI shows a **Train App Model** button that trains from `data/raw/spotify.csv`.
- Four prediction modes: single song, batch CSV, Spotify URL/ID, and local audio file.

## API Endpoints
| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service, model and dataset availability |
| GET | `/api/model` | Bundle metadata (features, defaults, category options, profiles) |
| GET | `/api/model/importance` | Top hit drivers from the fitted pipeline |
| POST | `/api/predict/single` | Score one song from feature values |
| POST | `/api/predict/batch` | Score an uploaded CSV; returns KPIs, chart series, preview |
| GET | `/api/predict/batch/{id}/csv` | Download the full annotated CSV |
| POST | `/api/predict/spotify` | Fetch a track from Spotify and score it |
| POST | `/api/predict/audio` | Extract Librosa features from an upload and score it |
| GET | `/api/train/audio-library` | File counts in `data/audio/{hit,not_hit}` |
| POST | `/api/train/dataset` | Start dataset training (returns `job_id`) |
| POST | `/api/train/audio` | Start audio-folder training (returns `job_id`) |
| GET | `/api/train/jobs/{id}` | Poll training progress |

Training runs on a background thread; the UI polls the job endpoint for the progress bar.

## Reproducing the Evaluation

The full methodology — cleaning, temporal split, baselines, imbalance strategies, grid search,
calibration and fairness — runs from one command:

```bash
python scripts/run_experiments.py            # full grids, ~5 minutes
python scripts/run_experiments.py --fast     # reduced grids
python scripts/run_experiments.py --no-xgboost
```

It regenerates every file in `reports/results/` and prints explicit verdicts on the three
research hypotheses. `notebooks/06_tuning_and_validation.ipynb` runs the same pipeline with
narrative and saves figures to `reports/figures/`.

| Artefact | Contents |
| --- | --- |
| `cleaning_report.csv` | Rows dropped for duplicates and impossible dates, with before/after date ranges |
| `imbalance_comparison.csv` | None vs class-weighting vs SMOTE, 5-fold stratified CV |
| `model_comparison.csv` | Baselines plus tuned models, holdout metrics, CV mean/std, chosen parameters |
| `final_metrics.csv` | Metrics for the CV-selected model |
| `confusion_matrix.csv` | 2x2 on the temporal holdout |
| `eval_predictions.csv` | `y_true`, `y_pred`, `y_score`, `genre` |
| `calibration.csv` | Reliability-curve points and Brier score per model |
| `genre_group_metrics.csv` | Per-genre metrics at n>=30 (`_all.csv` is unfiltered) |
| `fairness_summary.csv` | Disparity statistics across the retained genres |

Two notes on validity. The source file contains `first_week` dates as far ahead as 2075; those
rows are removed by `clean_dataset()` before the chronological split, because sorting on a
corrupt date column otherwise fills the holdout with them instead of recent releases. And SMOTE
is applied inside an `imblearn` pipeline, so resampling is fitted per training fold and never
reaches a validation fold or the holdout.

## How I Retrain With a New Dataset
1. Replace `data/raw/spotify.csv` with my new dataset.
2. Make sure the dataset has either:
   - a `hit` column, or
   - a `popularity` (or `track_popularity`) column so `hit` can be auto-generated.
3. Delete the old model bundle: `models/saved_models/hit_app_bundle.joblib`
4. Start the backend and frontend, then click **Train App Model** in the app.

After training, a new bundle is saved to `models/saved_models/hit_app_bundle.joblib` and the API picks it up without a restart.

## Training From My Own Audio (Spotify-free)
1. Drop songs into `data/audio/hit/` and `data/audio/not_hit/`.
2. Either click **Train From Audio Folders** in the Local Audio File tab, or run `python scripts/train_from_audio.py`.

Requires ffmpeg on PATH for MP3/OGG/FLAC decoding (WAV works without it). Windows: `winget install ffmpeg`.

## Spotify Auto-Fetch Setup
1. Create a Spotify developer app: https://developer.spotify.com/dashboard
2. Copy Client ID and Client Secret.
3. Paste them into the **Settings** page in the app. They are kept in browser session storage only and sent to the backend per request.

## Target Definition
The label depends on what the dataset provides, and the distinction matters when writing up:

- **If the file already has a `hit` column** (as `data/raw/spotify.csv` does), that column is
  used directly. It is chart-derived, which is why `peak_position`, `weeks_on_chart` and
  `debut_rank` are excluded as leakage.
- **Otherwise** the label is generated as `popularity >= 70` (or `track_popularity`), via
  `add_hit_label()` in `src/preprocessing.py`. This is the fallback path only.

`track_popularity` is listed in `LEAKAGE_COLUMNS` precisely because the fallback derives the
label from it; feeding it back as a feature would hand the model a copy of its own target.

The threshold can be changed in the preprocessing logic based on future experiments.
