# Music Hit Prediction — Project Context Brief

**Purpose of this file.** It is a complete, verified factual record of the implemented project,
written to be used as a prompt for generating thesis documentation. Every number here was read
directly from the artefacts in `reports/results/` or computed from the code, not recalled.

**How to use it.** Paste this file into a model along with an instruction such as:

> Using only the facts in this brief, write the [Methodology / Results / Discussion /
> Limitations] chapter of my final-year dissertation. Do not invent numbers. Where a claim is
> marked as a limitation or caveat, preserve it rather than smoothing it over.

**Rules for anything generated from this brief**

1. Never state a metric that does not appear here.
2. Two experimental runs exist (natural prevalence and matched case-control). Every reported
   number must say which run it came from.
3. Where this brief flags a caveat, the caveat travels with the number.
4. `hit` is defined by chart appearance in the source dataset, not by a popularity threshold.

---

## 1. Research framing

**Aim.** Design and develop a machine learning classifier that predicts the hit potential of
music tracks from audio features, and critically evaluate its performance, fairness and ethical
implications.

**Research questions**

- **RQ1** — To what extent can audio features predict commercial hit potential?
- **RQ2** — Which combination of features and algorithms performs best on a held-out temporal
  test set?
- **RQ3** — What are the ethical implications of deploying algorithmic hit prediction, and how
  might such systems perpetuate bias against underrepresented artists and genres?

**Hypotheses**

- **H1** — Models will exceed 70% accuracy, outperforming a random baseline.
- **H2** — Ensembles (random forest, XGBoost) will outperform logistic regression.
- **H3** — Models trained on historically biased chart data will show measurable disparities
  across genres.

---

## 2. Data

### 2.1 Source

`data/raw/spotify.csv` — 29,488 rows, 29 columns. The file arrives pre-collected; it was **not**
gathered live through the Spotify Web API during this project (see §7.1).

The label `HIT` ships with the dataset and is chart-derived — the file also carries
`PEAK_POSITION`, `WEEKS_ON_CHART` and `DEBUT_RANK`, all excluded as leakage. A fallback rule
(`popularity >= 70`) exists in code but **never fires on this dataset** because `HIT` is present.

### 2.2 Cleaning (`src/preprocessing.clean_dataset`)

| Measure | Value |
| --- | --- |
| Rows in | 29,488 |
| Exact duplicates removed | 78 |
| Unparseable dates removed | 0 |
| **Impossible (future) dates removed** | **11,159** |
| Rows out | **18,251** |
| Date range before | 1976-01-03 → **2075-12-27** |
| Date range after | 1976-01-03 → 2021-05-29 |

**Why this matters.** Training sorts on `first_week` and takes the final 20% as the test set.
With 38% of rows dated in the future, those corrupt rows sorted to the end and formed almost the
entire holdout. Every metric produced before this fix was measured on a test set of corrupt-dated
records. This is a primary finding, not housekeeping.

### 2.3 Remaining data-quality issues (surfaced in the app, not fixed)

| Issue | Scale |
| --- | --- |
| Rows missing every audio feature | 5,069 (17.2%) — median-imputed, so those predictions rest on metadata alone |
| `playlist_genre` / `playlist_subgenre` coverage | 12% |
| `spotify_genre` cardinality | 2,640 distinct values, stored as stringified lists |
| `genre` cardinality | 514 distinct, 89.2% coverage |

The high genre cardinality explains why one-hot genre combinations dominate the feature-importance
chart: the model largely learns genre priors.

### 2.4 Feature schema

The model consumes **17 features** (13 numeric + 4 categorical):

```
tempo, energy, danceability, loudness, valence, acousticness, speechiness,
instrumentalness, liveness, duration, sentiment_polarity, sentiment_subjectivity,
mentions, spotify_genre, playlist_genre, playlist_subgenre, genre
```

**Excluded as leakage** (`backend/app/training.LEAKAGE_COLUMNS`): `hit`, `peak_position`,
`weeks_on_chart`, `debut_rank`, `popularity`, `track_popularity`, `first_week`, and all identity
columns.

**Not available in this dataset** (28 further features the pipeline supports): the 21 Librosa
audio features (`loudness_db`, `zcr`, `spectral_centroid`, `spectral_rolloff`,
`spectral_bandwidth`, `chroma`, `mfcc_1`…`mfcc_13`) and the Spotify metadata block
(`artist_popularity`, `artist_followers`, `duration_ms`, `is_explicit`, `release_year`,
`release_month`, `num_artists`, `primary_genre`). **No artist-level signal exists at all**, which
matters because the cited literature finds artist popularity dominant.

---

## 3. Methodology implemented

CRISP-DM. Orchestrated by `scripts/run_experiments.py`; reusable logic in `src/experiments.py`.

- **Split** — 80/20 chronological on cleaned `first_week`. The holdout is sealed: used only for
  final evaluation, never for tuning or model selection.
- **Preprocessing** — median imputation + `StandardScaler` (numeric); most-frequent imputation +
  `OneHotEncoder(handle_unknown="ignore")` (categorical). Encoded width: 2,816 columns.
- **Class imbalance** — three strategies compared per family: none, `class_weight="balanced"`,
  and **SMOTE**. SMOTE runs inside an `imblearn.pipeline.Pipeline`, so it resamples each training
  fold only. Verified: holdout positive rate unchanged, asserted in code.
- **Tuning** — `GridSearchCV` with `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`,
  scoring `f1_macro`, fitted on the training split only.
- **Model selection** — by cross-validated macro F1, never by holdout score.
- **Evaluation** — accuracy, macro precision/recall/F1, ROC-AUC, confusion matrix, reliability
  curves + Brier scores, per-genre fairness with a minimum-group-size filter.

### Algorithms

| Family | Tuned grid | Selected (natural run) |
| --- | --- | --- |
| Logistic regression | `C` ∈ {0.01, 0.1, 1, 10} | `C=0.1`, SMOTE |
| Random forest | `n_estimators` {200,400} × `max_depth` {None,12} × `min_samples_leaf` {1,5} | 400 trees, depth None, leaf 5, SMOTE |
| XGBoost | `max_depth` {4,6} × `learning_rate` {0.05,0.15} × `n_estimators` {200,400} | depth 4, lr 0.15, 200 rounds, SMOTE |

Baselines: `DummyClassifier(strategy="most_frequent")` and `strategy="stratified"`.

---

## 4. Results — Run A: natural prevalence

18,251 rows · train 14,600 / test 3,651 · train positive rate 19.0% · **holdout positive rate 10.9%**

> The holdout positive rate is lower than training because hit rate declines over the period, and
> the split is chronological. This is a genuine distribution shift and raises the majority-class
> baseline on the test set.

### 4.1 Imbalance strategy (5-fold CV, top rows)

| Model | Strategy | CV macro F1 | ± | CV ROC-AUC |
| --- | --- | --- | --- | --- |
| XGBoost | **SMOTE** | 0.6705 | 0.0105 | 0.7474 |
| Random forest | SMOTE | 0.6620 | 0.0054 | 0.7474 |
| XGBoost | balanced | 0.6527 | 0.0063 | 0.7567 |
| Logistic regression | SMOTE | 0.6395 | 0.0057 | 0.7496 |

**SMOTE was selected for all three families.**

### 4.2 Holdout performance

| Model | Accuracy | Precision (macro) | Recall (macro) | **F1 (macro)** | ROC-AUC |
| --- | --- | --- | --- | --- | --- |
| Majority-class baseline | **0.8910** | 0.4455 | 0.5000 | 0.4712 | 0.5000 |
| Stratified-random baseline | 0.7406 | 0.4926 | 0.4884 | 0.4851 | 0.4884 |
| Logistic regression | 0.6795 | 0.5714 | 0.6680 | 0.5496 | 0.7429 |
| Random forest | 0.7412 | 0.5863 | 0.6794 | 0.5876 | **0.7467** |
| **XGBoost (selected)** | **0.7732** | 0.5922 | 0.6710 | **0.6024** | 0.7323 |

Cross-validated macro F1: XGBoost 0.6683 ± 0.0097 · RF 0.6628 ± 0.0106 · LR 0.6439 ± 0.0059.

### 4.3 Confusion matrix (XGBoost)

|  | Predicted non-hit | Predicted hit |
| --- | --- | --- |
| **Actual non-hit** | 2,608 | 645 |
| **Actual hit** | 183 | 215 |

Of 398 real hits it finds 215 (recall 54.0%); of 860 predicted hits 215 are real (precision 25.0%).

### 4.4 Calibration (Brier, lower is better)

XGBoost **0.1630** · Random forest 0.1914 · Logistic regression 0.2286

### 4.5 Fairness (per genre, n ≥ 30)

| Measure | Value |
| --- | --- |
| Groups total / kept / excluded | 145 / **19** / 126 |
| Excluded groups scoring a perfect F1 | **102** |
| Best group | baton rouge rap — 1.000 |
| Worst group | **r&b — 0.259** |
| **Disparity (max − min)** | **0.741** |
| Mean ± SD across kept groups | 0.554 ± 0.208 |

The 102 perfect scores among excluded groups are artefacts of tiny n (often 1–2 tracks). Reporting
unfiltered per-genre metrics would be invalid.

---

## 5. Results — Run B: matched case-control (the control experiment)

Each hit matched to one non-hit **from the same release year, and the same genre where available**.

| Measure | Value |
| --- | --- |
| Hits used | 3,178 (all) |
| Matched on year **and** genre | 2,757 (86.8%) |
| Matched on year only | 421 |
| Unmatched | 0 |
| Rows out | 6,356 · positive rate 50.0% |

### 5.1 Holdout performance

| Model | Accuracy | **F1 (macro)** | ROC-AUC |
| --- | --- | --- | --- |
| Majority-class baseline | 0.4992 | 0.3330 | 0.5000 |
| Stratified-random baseline | 0.4969 | 0.4968 | 0.4968 |
| **Logistic regression** | **0.5629** | **0.5566** | **0.6055** |
| Random forest | 0.5566 | 0.5530 | 0.5813 |
| XGBoost (selected by CV) | 0.5385 | 0.5350 | 0.5804 |

Calibration (Brier): RF 0.2530 · XGBoost 0.2569 · LR 0.2579 — all markedly worse than Run A.

Fairness at n ≥ 30: 5 of 58 groups kept · best dance pop 0.597 · worst rap 0.439 · **disparity 0.157**.

### 5.2 The central finding

**ROC-AUC falls from 0.747 to 0.606 between Run A and Run B.**

AUC is prevalence-independent, so balancing alone cannot explain this. The drop is caused by the
**matching**: holding release year and genre constant removes them as predictors. The interpretation
is that most of the model's apparent predictive power in Run A came from *when a track was released
and what genre it was*, not from its acoustic properties. With those confounds controlled, residual
audio signal is weak — AUC ≈ 0.58–0.61, only modestly above chance.

Note also that in Run B the ranking inverts: logistic regression becomes best, and the ensemble
advantage disappears into fold noise.

---

## 6. Hypothesis verdicts

| | Run A (natural) | Run B (matched) |
| --- | --- | --- |
| **H1** — accuracy > 70%, beats random | **Supported** — 77.3% > 70%, beats random 74.1% | **Rejected** — 56.3% |
| **H2** — ensembles > logistic regression | **Supported** — XGBoost 0.6683 vs LR 0.6439 CV macro F1; margin 0.0244 > combined SD 0.0155 | **Not supported** — margin 0.0056 < combined SD 0.0204, i.e. within noise |
| **H3** — genre disparities exist | **Supported** — disparity 0.741 across 19 groups | Weakly supported — 0.157 across 5 groups |

**Mandatory caveat on H1.** The hypothesis specifies a *random* baseline. Against the
**majority-class** baseline (89.1% accuracy) the model **loses on accuracy** — though it wins
decisively on macro F1 (0.602 vs 0.471). On a 10.9% positive rate, accuracy is the wrong headline
metric and "random baseline" is too weak a comparator. Any write-up must report both baselines.

---

## 7. Proposal vs implementation

### 7.1 Commitments not met

| Commitment | Status |
| --- | --- |
| Collect features live via **Spotify Web API** | **Not done.** Spotify restricted `audio-features`, `audio-analysis` and `preview_url` for new applications (Nov 2024). Dataset is pre-collected. |
| **Million Song Dataset** supplement | Not used. |
| Engineered features: genre-normalised scores, rolling popularity, era-adjusted valence | Not implemented. |

### 7.2 Commitments met

Data cleaning · **SMOTE** · three classifier families · **grid search with stratified k-fold CV** ·
temporal holdout · accuracy / macro F1 / ROC-AUC · **calibration plots** · feature importance ·
**per-genre fairness analysis**.

### 7.3 Delivered beyond the proposal

- A deployed **FastAPI + Next.js/TypeScript application** (13 API endpoints, 9 routes, 19 charts),
  not promised anywhere in the proposal.
- **Librosa feature extraction** and a Spotify-free training path from local audio — the adaptive
  response to the API deprecation.
- The **matched case-control control experiment** (§5).
- Discovery of the impossible-date defect (§2.2).

### 7.4 Corrections the proposal document needs

1. **Tools table** — add FastAPI, Next.js/TypeScript, Plotly, librosa, imbalanced-learn, joblib;
   remove Seaborn (unused; Matplotlib is used).
2. **Risk register** — the materialised risk was **API deprecation**, not "rate limits".
3. **Phase 1** — state that features are pre-collected, not gathered live.
4. **H1 wording** — "random baseline" is too weak; report against the majority-class baseline.

---

## 8. Known limitations (state these explicitly)

1. **Audio features are Spotify-derived, not reproducible from a waveform.** A local-audio upload
   supplies only `tempo` plus scale-mismatched proxies; 9 of 13 numeric features arrive zero-filled.
   Measured consequence: across 30 synthetic songs spanning the entire plausible Librosa range,
   predicted scores varied only between **37.7% and 45.0%** — the model is effectively insensitive
   to the audio.
2. **The balanced sample is not calibrated to real prevalence** — report discrimination from Run B
   and calibration from Run A.
3. **38% of the source data was discarded** as unusable, so results describe the surviving subset.
4. **No artist-level features**, which the cited literature identifies as dominant predictors.
5. **Genre is high-cardinality and sparse**, so one-hot genre combinations dominate importance.
6. **`artist_popularity`, if later added, is a present-day measurement** and would leak when
   predicting historical chart success.
7. **Chart labels encode historical industry bias**, so a model trained on them reproduces it —
   this is the substance of RQ3, not an aside.

---

## 9. Reproduction

```bash
# Backend (project root)
venv\Scripts\activate
uvicorn backend.app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev          # http://localhost:3000

# Experiments — regenerates every artefact
python scripts/run_experiments.py              # Run A, ~5 min
python scripts/run_experiments.py --balanced   # Run B, ~4 min
```

Seeded throughout with `random_state=42`.

### Artefacts

| Path | Contents |
| --- | --- |
| `reports/results/*.csv` | Run A results (unsuffixed) and Run B (`*_balanced`) |
| `reports/figures/calibration_curves.png`, `genre_fairness.png` | Thesis figures |
| `notebooks/06_tuning_and_validation.ipynb` | Executed methodology notebook |
| `data/processed/spotify_clean.csv` | Cleaned dataset, 18,251 rows |
| `models/saved_models/hit_app_bundle.joblib` | App model (XGBoost, macro F1 0.6236, 17 features) |

The app bundle is trained separately from the experiment and is **not** the tuned experimental
model; its score is not a thesis result.

### Code map

| Path | Role |
| --- | --- |
| `src/preprocessing.py` | `clean_dataset`, `balanced_case_control_sample`, `canonical_genre`, `make_preprocessor` |
| `src/experiments.py` | Baselines, imbalance strategies, grids, CV, calibration, fairness |
| `src/evaluation.py` | `classification_metrics`, `metrics_by_group` |
| `src/model.py` | Estimator constructors |
| `src/audio_features.py` | 21 Librosa features |
| `scripts/run_experiments.py` | Orchestration and hypothesis verdicts |
| `backend/app/` | FastAPI service |
| `frontend/` | Next.js application |

---

## 10. Recommended narrative

Lead with Run A: H1, H2 and H3 all supported, with the majority-baseline caveat stated openly.
Then present Run B as a controlled follow-up showing AUC collapsing from 0.747 to 0.606 once era
and genre are held constant.

That ordering converts the weakest-looking number into the most defensible claim available:
**acoustic and metadata features alone have limited power to predict chart success; genre and
timing effects dominate.** It answers RQ1 honestly, explains RQ2's model ranking as
metric-dependent, and gives RQ3 an empirical basis rather than a purely theoretical one — while
remaining consistent with Pachet & Roy (2008), who argued hit song science is not yet a science.
