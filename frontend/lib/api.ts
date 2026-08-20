/** Typed client for the FastAPI backend. */

import type {
  AudioLibrary,
  AudioPredictionResponse,
  BatchResponse,
  ComparisonResponse,
  ConfusionResponse,
  CorrelationsResponse,
  CurvesResponse,
  DatasetSummary,
  DistributionResponse,
  FeatureImportance,
  GenreMetricsResponse,
  GenresResponse,
  ModelResponse,
  PredictionResponse,
  SpotifyPredictionResponse,
  TrainingJob,
  YearlyResponse,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

/** Error carrying the backend's `detail` message, so the UI can show it verbatim. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_BASE_URL}. Is the FastAPI server running?`,
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (body.detail) {
        detail = JSON.stringify(body.detail);
      }
    } catch {
      /* keep the status-based fallback */
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

function jsonBody(payload: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

export const api = {
  getModel: () => request<ModelResponse>("/api/model"),

  getImportance: (topN = 15) =>
    request<FeatureImportance>(`/api/model/importance?top_n=${topN}`),

  getAudioLibrary: () => request<AudioLibrary>("/api/train/audio-library"),

  predictSingle: (features: Record<string, number | string>) =>
    request<PredictionResponse>("/api/predict/single", jsonBody({ features })),

  predictBatch: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<BatchResponse>("/api/predict/batch", { method: "POST", body: form });
  },

  batchCsvUrl: (downloadId: string) =>
    `${API_BASE_URL}/api/predict/batch/${downloadId}/csv`,

  predictSpotify: (track: string, clientId: string, clientSecret: string) =>
    request<SpotifyPredictionResponse>(
      "/api/predict/spotify",
      jsonBody({ track, client_id: clientId, client_secret: clientSecret }),
    ),

  predictAudio: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<AudioPredictionResponse>("/api/predict/audio", {
      method: "POST",
      body: form,
    });
  },

  trainDataset: (includeXgboost: boolean) =>
    request<{ job_id: string }>(
      "/api/train/dataset",
      jsonBody({ include_xgboost: includeXgboost }),
    ),

  trainAudio: () => request<{ job_id: string }>("/api/train/audio", { method: "POST" }),

  getJob: (jobId: string) => request<TrainingJob>(`/api/train/jobs/${jobId}`),

  // --- analytics ---
  getModelComparison: () => request<ComparisonResponse>("/api/reports/model-comparison"),

  getConfusionMatrix: () => request<ConfusionResponse>("/api/reports/confusion-matrix"),

  getGenreMetrics: (minN: number) =>
    request<GenreMetricsResponse>(`/api/reports/genre-metrics?min_n=${minN}`),

  getCurves: () => request<CurvesResponse>("/api/reports/curves"),

  getDatasetSummary: () => request<DatasetSummary>("/api/dataset/summary"),

  getDistribution: (feature: string, bins = 30) =>
    request<DistributionResponse>(
      `/api/dataset/distributions?feature=${encodeURIComponent(feature)}&bins=${bins}`,
    ),

  getCorrelations: () => request<CorrelationsResponse>("/api/dataset/correlations"),

  getGenres: (column: string | null, top = 15) =>
    request<GenresResponse>(
      `/api/dataset/genres?top=${top}` + (column ? `&column=${encodeURIComponent(column)}` : ""),
    ),

  getHitRateByYear: (minCount = 10) =>
    request<YearlyResponse>(`/api/dataset/hit-rate-by-year?min_count=${minCount}`),
};
