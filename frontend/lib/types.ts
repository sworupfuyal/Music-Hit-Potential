/** Shapes returned by the FastAPI backend (see backend/app/schemas.py). */

export type NumberMap = Record<string, number | null>;

export interface ModelMetadata {
  exists: true;
  model_name: string | null;
  f1_macro: number | null;
  feature_columns: string[];
  numeric_columns: string[];
  categorical_columns: string[];
  category_options: Record<string, string[]>;
  numeric_defaults: NumberMap;
  feature_ranges: Record<string, [number | null, number | null]>;
  hit_profile: NumberMap;
  flop_profile: NumberMap;
  trained_on: string | null;
  n_train_songs: number | null;
}

export interface MissingModel {
  exists: false;
  error: string | null;
}

export type ModelResponse = ModelMetadata | MissingModel;

export interface FeatureImportance {
  available: boolean;
  names?: string[];
  values?: number[];
  top_n?: number;
}

export interface AudioLibrary {
  hit: number;
  not_hit: number;
  ready: boolean;
  hit_dir: string;
  not_hit_dir: string;
}

export interface PredictionResponse {
  probability: number;
  features: NumberMap;
}

export interface SpotifyDisplay {
  track_name: string;
  artist_name: string;
  album_name: string;
  primary_genre: string;
  track_id: string;
  audio_warning: string | null;
  album_image: string | null;
  preview_url: string | null;
}

export interface SpotifyPredictionResponse extends PredictionResponse {
  display: SpotifyDisplay;
}

export interface AudioPredictionResponse extends PredictionResponse {
  audio_features: NumberMap;
}

export interface BatchScatter {
  x_label: string;
  y_label: string;
  x: (number | null)[];
  y: (number | null)[];
  score: number[];
}

export interface BatchResponse {
  download_id: string;
  filename: string | null;
  total: number;
  predicted_hits: number;
  avg_score: number;
  top_score: number;
  label_column: string | null;
  scores: number[];
  ranked: { labels: string[]; scores: number[] };
  scatter: BatchScatter | null;
  preview_columns: string[];
  preview_rows: Record<string, unknown>[];
}

export type JobStatus = "running" | "succeeded" | "failed";

export interface TrainingJob {
  id: string;
  kind: "dataset" | "audio";
  status: JobStatus;
  done: number;
  total: number;
  current: string;
  message: string;
  error: string | null;
  result: {
    model_name: string | null;
    f1_macro: number | null;
    trained_on: string | null;
    n_train_songs: number | null;
  } | null;
}

/** Spotify client credentials, held in the browser and posted per request. */
export interface SpotifyCreds {
  clientId: string;
  clientSecret: string;
}

// --- Analytics payloads ---------------------------------------------------

export interface ComparisonResponse {
  metrics: string[];
  rows: { model: string; metrics: Record<string, number | null>; baseline: boolean }[];
}

export interface ConfusionResponse {
  matrix: number[][];
  labels: { actual: string[]; predicted: string[] };
  counts: { tn: number; fp: number; fn: number; tp: number; total: number };
  rates: Record<string, number | null>;
}

export interface GenreMetricsResponse {
  min_n: number;
  total_groups: number;
  kept_groups: number;
  excluded_groups: number;
  excluded_perfect_scores: number;
  groups: { group: string; n_samples: number; accuracy: number | null; f1_macro: number | null }[];
  all_groups: { n_samples: number; f1_macro: number | null }[];
}

export interface CurvesResponse {
  n_test: number;
  positive_rate: number | null;
  roc: { fpr: number[]; tpr: number[]; auc: number | null };
  pr: { recall: number[]; precision: number[]; average_precision: number | null };
  model_name: string | null;
}

export interface QualityFlag {
  severity: "serious" | "warning";
  label: string;
  detail: string;
}

export interface DatasetSummary {
  rows: number;
  columns: number;
  hits: number;
  flops: number;
  hit_rate: number | null;
  numeric_features: string[];
  date_range: { min: string; max: string } | null;
  missing_top: Record<string, number>;
  missing_total: number;
  duplicates: number;
  quality: QualityFlag[];
}

export interface DistributionResponse {
  feature: string;
  bin_centers: (number | null)[];
  bin_width: number | null;
  hit_counts: number[];
  flop_counts: number[];
  missing: number;
  stats: Record<string, number | null>;
  hit_mean: number | null;
  flop_mean: number | null;
}

export interface CorrelationsResponse {
  labels: string[];
  matrix: (number | null)[][];
  top_pairs: { a: string; b: string; r: number | null }[];
  note: string;
}

export interface GenresResponse {
  column: string;
  available_columns: string[];
  labels: string[];
  volumes: number[];
  hit_rates: (number | null)[];
  distinct: number;
  coverage: number | null;
}

export interface YearlyResponse {
  years: number[];
  counts: number[];
  hit_rates: (number | null)[];
  min_count: number;
  current_year: number;
  future_years: number[];
}
