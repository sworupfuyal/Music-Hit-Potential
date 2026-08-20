"use client";

/** Dashboard: model + dataset headline numbers, then the two summary charts. */

import Link from "next/link";

import { useModel } from "@/app/providers";
import { Chart } from "@/components/Chart";
import { DataTable, Panel } from "@/components/Panel";
import { WaveformDivider } from "@/components/music";
import { Alert, Card, Metric } from "@/components/ui";
import { api } from "@/lib/api";
import { modelComparisonBars, confusionHeatmap } from "@/lib/charts-analytics";
import { useApiData } from "@/lib/useApiData";

const QUICK_LINKS = [
  { href: "/predict/single", label: "Score a single song", hint: "Enter feature values by hand" },
  { href: "/predict/spotify", label: "Score a Spotify track", hint: "Paste a URL or track ID" },
  { href: "/insights", label: "Model evaluation", hint: "ROC, confusion matrix, fairness" },
  { href: "/dataset", label: "Dataset explorer", hint: "Distributions and data quality" },
];

export default function DashboardPage() {
  const { model } = useModel();
  const summary = useApiData(() => api.getDatasetSummary(), []);
  const comparison = useApiData(() => api.getModelComparison(), []);
  const confusion = useApiData(() => api.getConfusionMatrix(), []);

  const serious = (summary.data?.quality ?? []).filter((q) => q.severity === "serious");

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Active model"
          value={model?.exists ? (model.model_name ?? "—") : "—"}
          hint={
            model?.exists && model.trained_on === "local_audio"
              ? `${model.n_train_songs ?? "?"} local songs`
              : "Project dataset"
          }
        />
        <Metric
          label="Validation macro F1"
          value={
            model?.exists && model.f1_macro !== null ? model.f1_macro.toFixed(4) : "—"
          }
          hint={`${model?.exists ? model.feature_columns.length : 0} features`}
        />
        <Metric
          label="Dataset rows"
          value={summary.data ? summary.data.rows.toLocaleString() : "…"}
          hint={summary.data ? `${summary.data.columns} columns` : undefined}
        />
        <Metric
          label="Hit rate"
          value={
            summary.data?.hit_rate !== null && summary.data
              ? `${(summary.data.hit_rate! * 100).toFixed(1)}%`
              : "…"
          }
          hint={
            summary.data
              ? `${summary.data.hits.toLocaleString()} hits · ${summary.data.flops.toLocaleString()} non-hits`
              : undefined
          }
        />
      </section>

      <WaveformDivider className="opacity-70" />

      {serious.length > 0 ? (
        <Alert kind="warning">
          <span className="font-semibold">
            {serious.length} serious data-quality issue{serious.length > 1 ? "s" : ""} detected.
          </span>{" "}
          {serious[0].label} — {serious[0].detail}{" "}
          <Link href="/dataset" className="underline">
            See all in the dataset explorer
          </Link>
          .
        </Alert>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel
          state={comparison}
          height={400}
          table={(data) => (
            <DataTable
              columns={["Model", ...data.metrics.map((m) => m.replace(/_/g, " "))]}
              align={Object.fromEntries(data.metrics.map((_, i) => [i + 1, "right"]))}
              rows={data.rows.map((row) => [
                row.model.replace(/_/g, " ") + (row.baseline ? " (baseline)" : ""),
                ...data.metrics.map((m) => {
                  const value = row.metrics[m];
                  return value === null || value === undefined ? null : value.toFixed(4);
                }),
              ])}
            />
          )}
        >
          {(data) => <Chart figure={modelComparisonBars(data.metrics, data.rows)} />}
        </Panel>

        <Panel
          state={confusion}
          height={330}
          table={(data) => (
            <DataTable
              columns={["", "Predicted non-hit", "Predicted hit"]}
              align={{ 1: "right", 2: "right" }}
              rows={[
                ["Actual non-hit", data.matrix[0][0].toLocaleString(), data.matrix[0][1].toLocaleString()],
                ["Actual hit", data.matrix[1][0].toLocaleString(), data.matrix[1][1].toLocaleString()],
              ]}
            />
          )}
        >
          {(data) => <Chart figure={confusionHeatmap(data.matrix, data.labels)} />}
        </Panel>
      </section>

      <Card>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Jump to
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {QUICK_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-xl border border-edge bg-canvas px-4 py-3 transition hover:border-brand/50 hover:bg-brand-tint/50"
            >
              <div className="text-sm font-semibold">{link.label}</div>
              <div className="mt-1 text-xs text-muted">{link.hint}</div>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
