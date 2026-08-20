"use client";

/** Batch Prediction — upload a CSV, get KPIs, charts, a preview table and a download. */

import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import { batchHistogram, batchRankedBars, batchScatter } from "@/lib/charts";
import { addHistoryEntry } from "@/lib/history";
import type { BatchResponse } from "@/lib/types";

import { Chart } from "../Chart";
import { Alert, Button, Card, Metric } from "../ui";

function cell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  return String(value);
}

export function BatchTab() {
  const [result, setResult] = useState<BatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    setResult(null);
    setFileName(file.name);
    try {
      const response = await api.predictBatch(file);
      setResult(response);
      // One summary entry per batch rather than one per row.
      addHistoryEntry({
        mode: "Batch",
        score: response.avg_score / 100,
        verdict: `${response.predicted_hits}/${response.total} predicted hits`,
        detail: file.name,
      });
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card>
        <p className="text-sm">
          Upload a CSV with the same feature columns used during training.
        </p>
        <label className="mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-edge bg-canvas px-6 py-8 text-center transition hover:border-brand/50 hover:bg-brand-tint/40">
          <span className="text-sm font-semibold">
            {fileName ?? "Choose a CSV file"}
          </span>
          <span className="text-xs text-muted">Batch CSV · .csv</span>
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
            }}
          />
        </label>
        {busy ? <p className="mt-3 text-sm text-muted">Scoring rows…</p> : null}
      </Card>

      {error ? <Alert kind="error">{error}</Alert> : null}

      {result ? (
        <div className="animate-rise space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Songs" value={result.total.toLocaleString()} />
            <Metric
              label="🔥 Predicted Hits"
              value={result.predicted_hits.toLocaleString()}
            />
            <Metric label="Avg Score" value={`${result.avg_score.toFixed(1)}%`} />
            <Metric label="Top Score" value={`${result.top_score.toFixed(1)}%`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <Chart figure={batchHistogram(result.scores)} />
            </Card>
            <Card>
              <Chart
                figure={batchRankedBars(
                  result.ranked.labels,
                  result.ranked.scores,
                  result.ranked.labels.length,
                )}
              />
            </Card>
          </div>

          {result.scatter ? (
            <Card>
              <Chart figure={batchScatter(result.scatter)} />
            </Card>
          ) : null}

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">
                First {result.preview_rows.length} scored rows
              </h3>
              <a
                href={api.batchCsvUrl(result.download_id)}
                download
                className="rounded-full bg-brand px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-strong"
              >
                Download predictions CSV
              </a>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="text-muted">
                  <tr>
                    {result.preview_columns.map((col) => (
                      <th key={col} className="whitespace-nowrap px-3 py-2 font-medium">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.preview_rows.map((row, index) => (
                    <tr key={index} className="border-t border-edge/60">
                      {result.preview_columns.map((col) => (
                        <td key={col} className="whitespace-nowrap px-3 py-2 tabular-nums">
                          {cell(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
