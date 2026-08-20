"use client";

/** Dataset Explorer: distributions, correlations, genre and temporal breakdowns. */

import { useEffect, useState } from "react";

import { Chart } from "@/components/Chart";
import { DataTable, Field, FilterRow, Panel, selectClass } from "@/components/Panel";
import { Alert, Card, Metric } from "@/components/ui";
import { api } from "@/lib/api";
import {
  correlationHeatmap,
  featureDistribution,
  genreHitRateBars,
  genreVolumeBars,
  hitRateByYearLine,
  yearVolumeBars,
} from "@/lib/charts-analytics";
import { useApiData } from "@/lib/useApiData";

export default function DatasetPage() {
  const [feature, setFeature] = useState("energy");
  const [bins, setBins] = useState(30);
  const [genreColumn, setGenreColumn] = useState<string | null>(null);
  const [topGenres, setTopGenres] = useState(12);

  const summary = useApiData(() => api.getDatasetSummary(), []);
  const distribution = useApiData(() => api.getDistribution(feature, bins), [feature, bins]);
  const correlations = useApiData(() => api.getCorrelations(), []);
  const genres = useApiData(() => api.getGenres(genreColumn, topGenres), [genreColumn, topGenres]);
  const yearly = useApiData(() => api.getHitRateByYear(20), []);

  // Default the feature selector to a column the dataset actually has.
  const available = summary.data?.numeric_features ?? [];
  useEffect(() => {
    if (available.length && !available.includes(feature)) setFeature(available[0]);
  }, [available, feature]);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Rows"
          value={summary.data ? summary.data.rows.toLocaleString() : "…"}
          hint={summary.data ? `${summary.data.columns} columns` : undefined}
        />
        <Metric
          label="Class balance"
          value={
            summary.data?.hit_rate != null
              ? `${(summary.data.hit_rate * 100).toFixed(1)}% hits`
              : "…"
          }
          hint={
            summary.data
              ? `${summary.data.hits.toLocaleString()} / ${summary.data.flops.toLocaleString()}`
              : undefined
          }
        />
        <Metric
          label="Missing values"
          value={summary.data ? summary.data.missing_total.toLocaleString() : "…"}
          hint={summary.data ? `${summary.data.duplicates} duplicate rows` : undefined}
        />
        <Metric
          label="Date range"
          value={
            summary.data?.date_range
              ? `${summary.data.date_range.min.slice(0, 4)}–${summary.data.date_range.max.slice(0, 4)}`
              : "…"
          }
          hint="From first_week"
        />
      </section>

      <Card>
        <h2 className="text-sm font-semibold">Data quality</h2>
        {summary.error ? (
          <Alert kind="error">{summary.error}</Alert>
        ) : summary.data === null ? (
          <div className="mt-3 h-24 animate-pulse rounded-lg bg-canvas" />
        ) : summary.data.quality.length === 0 ? (
          <Alert kind="success">No data-quality problems detected.</Alert>
        ) : (
          <ul className="mt-3 space-y-2">
            {summary.data.quality.map((flag) => (
              <li
                key={flag.label}
                className={`rounded-lg border px-4 py-3 text-sm ${
                  flag.severity === "serious"
                    ? "border-danger/50 bg-danger/10"
                    : "border-amber/50 bg-amber/10"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={flag.severity === "serious" ? "text-danger" : "text-amber"}
                  >
                    {flag.severity === "serious" ? "▲" : "●"}
                  </span>
                  <span className="font-semibold">{flag.label}</span>
                  <span className="ml-auto text-[11px] uppercase tracking-wide text-muted">
                    {flag.severity}
                  </span>
                </div>
                <p className="mt-1 text-muted">{flag.detail}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <section className="space-y-4">
        <FilterRow>
          <Field label="Feature">
            <select
              className={selectClass}
              value={feature}
              onChange={(event) => setFeature(event.target.value)}
            >
              {available.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Bins">
            <select
              className={selectClass}
              value={bins}
              onChange={(event) => setBins(Number(event.target.value))}
            >
              {[10, 20, 30, 50, 80].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>
          {distribution.data ? (
            <p className="text-xs text-muted">
              mean {distribution.data.stats.mean?.toFixed(3)} · median{" "}
              {distribution.data.stats.median?.toFixed(3)} ·{" "}
              {distribution.data.missing.toLocaleString()} missing
              {distribution.data.hit_mean !== null && distribution.data.flop_mean !== null ? (
                <>
                  {" "}
                  · hit mean {distribution.data.hit_mean.toFixed(3)} vs non-hit{" "}
                  {distribution.data.flop_mean.toFixed(3)}
                </>
              ) : null}
            </p>
          ) : null}
        </FilterRow>

        <Panel
          state={distribution}
          height={400}
          table={(data) => (
            <DataTable
              columns={["Bin centre", "Hits", "Non-hits"]}
              align={{ 0: "right", 1: "right", 2: "right" }}
              rows={data.bin_centers.map((centre, i) => [
                centre === null ? null : centre.toPrecision(4),
                data.hit_counts[i]?.toLocaleString() ?? null,
                data.flop_counts[i]?.toLocaleString() ?? null,
              ])}
            />
          )}
        >
          {(data) => <Chart figure={featureDistribution(data)} />}
        </Panel>
      </section>

      <Panel
        state={correlations}
        height={600}
        table={(data) => (
          <DataTable
            columns={["Feature A", "Feature B", "r"]}
            align={{ 2: "right" }}
            rows={data.top_pairs.map((p) => [p.a, p.b, p.r === null ? null : p.r.toFixed(3)])}
          />
        )}
      >
        {(data) => (
          <>
            <Chart figure={correlationHeatmap(data.labels, data.matrix)} />
            <p className="mt-2 text-xs text-muted">
              {data.note} Strongest pair:{" "}
              {data.top_pairs[0]
                ? `${data.top_pairs[0].a} × ${data.top_pairs[0].b} (r = ${data.top_pairs[0].r?.toFixed(3)})`
                : "—"}
            </p>
          </>
        )}
      </Panel>

      <section className="space-y-4">
        <FilterRow>
          <Field label="Genre column">
            <select
              className={selectClass}
              value={genreColumn ?? genres.data?.column ?? ""}
              onChange={(event) => setGenreColumn(event.target.value)}
            >
              {(genres.data?.available_columns ?? []).map((column) => (
                <option key={column} value={column}>
                  {column}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Top genres">
            <select
              className={selectClass}
              value={topGenres}
              onChange={(event) => setTopGenres(Number(event.target.value))}
            >
              {[8, 12, 20, 30].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>
          {genres.data ? (
            <p className="max-w-lg text-xs text-muted">
              {genres.data.distinct.toLocaleString()} distinct values ·{" "}
              {genres.data.coverage !== null
                ? `${(genres.data.coverage * 100).toFixed(0)}% of rows have one`
                : ""}
              {genres.data.coverage !== null && genres.data.coverage < 0.5
                ? " — the rates below describe only that subset, not the whole dataset."
                : ""}
            </p>
          ) : null}
        </FilterRow>

        <div className="grid gap-4 xl:grid-cols-2">
          <Panel
            state={genres}
            height={430}
            table={(data) => (
              <DataTable
                columns={["Genre", "Tracks"]}
                align={{ 1: "right" }}
                rows={data.labels.map((label, i) => [label, data.volumes[i].toLocaleString()])}
              />
            )}
          >
            {(data) => <Chart figure={genreVolumeBars(data.labels, data.volumes)} />}
          </Panel>

          <Panel
            state={genres}
            height={430}
            table={(data) => (
              <DataTable
                columns={["Genre", "Hit rate"]}
                align={{ 1: "right" }}
                rows={data.labels.map((label, i) => [
                  label,
                  data.hit_rates[i] === null
                    ? null
                    : `${((data.hit_rates[i] as number) * 100).toFixed(1)}%`,
                ])}
              />
            )}
          >
            {(data) => (
              <Chart
                figure={genreHitRateBars(
                  data.labels,
                  data.hit_rates,
                  summary.data?.hit_rate ?? null,
                )}
              />
            )}
          </Panel>
        </div>
      </section>

      <section className="grid gap-4">
        <Panel
          state={yearly}
          height={350}
          table={(data) => (
            <DataTable
              columns={["Year", "Tracks", "Hit rate"]}
              align={{ 1: "right", 2: "right" }}
              rows={data.years.map((year, i) => [
                year,
                data.counts[i].toLocaleString(),
                data.hit_rates[i] === null
                  ? null
                  : `${((data.hit_rates[i] as number) * 100).toFixed(1)}%`,
              ])}
            />
          )}
        >
          {(data) => (
            <>
              <Chart
                figure={hitRateByYearLine(data.years, data.hit_rates, data.current_year)}
              />
              {data.future_years.length > 0 ? (
                <p className="mt-2 text-xs text-danger">
                  {data.future_years.length} year buckets are in the future (
                  {data.future_years[0]}–{data.future_years[data.future_years.length - 1]}).
                  Training sorts on this column, so these rows dominate the holdout split.
                </p>
              ) : null}
            </>
          )}
        </Panel>

        <Panel state={yearly} height={270}>
          {(data) => <Chart figure={yearVolumeBars(data.years, data.counts)} />}
        </Panel>
      </section>
    </div>
  );
}
