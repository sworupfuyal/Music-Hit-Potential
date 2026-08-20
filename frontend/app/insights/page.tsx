"use client";

/** Model Evaluation: comparison, curves, confusion matrix, per-genre fairness. */

import { useState } from "react";

import { useModel } from "@/app/providers";
import { Chart } from "@/components/Chart";
import { DataTable, Field, FilterRow, Panel, selectClass } from "@/components/Panel";
import { Alert, Card, Metric } from "@/components/ui";
import { api } from "@/lib/api";
import { featureImportanceChart } from "@/lib/charts";
import {
  confusionHeatmap,
  fairnessScatter,
  modelComparisonBars,
  prCurve,
  rocCurve,
} from "@/lib/charts-analytics";
import { useApiData } from "@/lib/useApiData";

const MIN_N_OPTIONS = [1, 5, 10, 30, 50, 100];

export default function InsightsPage() {
  const { model } = useModel();
  const [minN, setMinN] = useState(30);

  const comparison = useApiData(() => api.getModelComparison(), []);
  const confusion = useApiData(() => api.getConfusionMatrix(), []);
  const curves = useApiData(() => api.getCurves(), []);
  const fairness = useApiData(() => api.getGenreMetrics(minN), [minN]);
  const importance = useApiData(() => api.getImportance(20), []);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Selected model"
          value={model?.exists ? (model.model_name ?? "—") : "—"}
        />
        <Metric
          label="ROC AUC (holdout)"
          value={curves.data?.roc.auc !== undefined && curves.data?.roc.auc !== null
            ? curves.data.roc.auc.toFixed(4)
            : "…"}
          hint="Recomputed live from the saved pipeline"
        />
        <Metric
          label="Average precision"
          value={
            curves.data?.pr.average_precision !== undefined &&
            curves.data?.pr.average_precision !== null
              ? curves.data.pr.average_precision.toFixed(4)
              : "…"
          }
          hint={
            curves.data?.positive_rate
              ? `No-skill baseline ${(curves.data.positive_rate * 100).toFixed(1)}%`
              : undefined
          }
        />
        <Metric
          label="Holdout rows"
          value={curves.data ? curves.data.n_test.toLocaleString() : "…"}
          hint="Last 20% of the chronological sort"
        />
      </section>

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
        {(data) => (
          <>
            <Chart figure={modelComparisonBars(data.metrics, data.rows)} />
            <p className="mt-2 text-xs text-muted">
              The grey bar is the majority-class baseline: always predicting
              &ldquo;not a hit&rdquo;. It beats every trained model on accuracy, which is why
              macro F1 is the selection metric here.
            </p>
          </>
        )}
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel
          state={curves}
          height={400}
          table={(data) => (
            <DataTable
              columns={["FPR", "TPR"]}
              align={{ 0: "right", 1: "right" }}
              rows={data.roc.fpr.map((f, i) => [
                f.toFixed(4),
                data.roc.tpr[i]?.toFixed(4) ?? null,
              ])}
            />
          )}
        >
          {(data) => <Chart figure={rocCurve(data.roc.fpr, data.roc.tpr, data.roc.auc)} />}
        </Panel>

        <Panel
          state={curves}
          height={400}
          table={(data) => (
            <DataTable
              columns={["Recall", "Precision"]}
              align={{ 0: "right", 1: "right" }}
              rows={data.pr.recall.map((r, i) => [
                r.toFixed(4),
                data.pr.precision[i]?.toFixed(4) ?? null,
              ])}
            />
          )}
        >
          {(data) => (
            <Chart
              figure={prCurve(
                data.pr.recall,
                data.pr.precision,
                data.pr.average_precision,
                data.positive_rate,
              )}
            />
          )}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel
          state={confusion}
          height={330}
          table={(data) => (
            <DataTable
              columns={["Metric", "Value"]}
              align={{ 1: "right" }}
              rows={Object.entries(data.rates).map(([key, value]) => [
                key.replace(/_/g, " "),
                value === null ? null : value.toFixed(4),
              ])}
            />
          )}
        >
          {(data) => (
            <>
              <Chart figure={confusionHeatmap(data.matrix, data.labels)} />
              <p className="mt-2 text-xs text-muted">
                Of {data.counts.total.toLocaleString()} holdout tracks, the model finds{" "}
                {data.counts.tp.toLocaleString()} of{" "}
                {(data.counts.tp + data.counts.fn).toLocaleString()} real hits (recall{" "}
                {data.rates.recall !== null ? (data.rates.recall * 100).toFixed(1) : "—"}%)
                at a precision of{" "}
                {data.rates.precision !== null
                  ? (data.rates.precision * 100).toFixed(1)
                  : "—"}
                %.
              </p>
            </>
          )}
        </Panel>

        <div className="space-y-4">
          <FilterRow>
            <Field label="Minimum samples per genre">
              <select
                className={selectClass}
                value={minN}
                onChange={(event) => setMinN(Number(event.target.value))}
              >
                {MIN_N_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    n ≥ {option}
                  </option>
                ))}
              </select>
            </Field>
            {fairness.data ? (
              <p className="max-w-md text-xs text-muted">
                {fairness.data.kept_groups} of {fairness.data.total_groups} genres kept.{" "}
                {fairness.data.excluded_perfect_scores} of the{" "}
                {fairness.data.excluded_groups} excluded groups scored a perfect F1 purely
                because their sample size is tiny.
              </p>
            ) : null}
          </FilterRow>

          <Panel
            state={fairness}
            height={400}
            table={(data) => (
              <DataTable
                columns={["Genre", "n", "Accuracy", "Macro F1"]}
                align={{ 1: "right", 2: "right", 3: "right" }}
                rows={data.groups.map((g) => [
                  g.group,
                  g.n_samples.toLocaleString(),
                  g.accuracy === null ? null : g.accuracy.toFixed(3),
                  g.f1_macro === null ? null : g.f1_macro.toFixed(3),
                ])}
              />
            )}
          >
            {(data) => (
              <Chart figure={fairnessScatter(data.all_groups, data.min_n)} />
            )}
          </Panel>
        </div>
      </section>

      <Card>
        <h2 className="mb-3 text-sm font-semibold">What drives a hit?</h2>
        {importance.error ? (
          <Alert kind="error">{importance.error}</Alert>
        ) : importance.data === null ? (
          <div className="h-64 animate-pulse rounded-lg bg-canvas" />
        ) : importance.data.available && importance.data.names && importance.data.values ? (
          <Chart
            figure={featureImportanceChart(
              importance.data.names,
              importance.data.values,
              importance.data.top_n ?? 20,
            )}
          />
        ) : (
          <Alert kind="info">Feature importance is unavailable for this model.</Alert>
        )}
      </Card>
    </div>
  );
}
