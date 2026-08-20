/**
 * Chart builders for the analytics pages (Dashboard, Model Evaluation, Dataset
 * Explorer, History). The prediction-hero charts stay in `charts.ts`; both share
 * that module's theme tokens and `baseLayout`.
 *
 * Rules applied throughout: one y-axis per plot — never dual-axis, which is why the
 * genre and per-year panels are each a *pair* of charts rather than two scales in
 * one frame; nominal categories take a single hue instead of a value ramp;
 * magnitude uses the one-hue SEQUENTIAL ramp and polarity the DIVERGING ramp with
 * its neutral midpoint; a legend is present whenever there are two or more series;
 * and text wears ink tokens, never a series color.
 */

import type { Data } from "plotly.js";

import {
  AMBER,
  BG,
  DIVERGING,
  FLOP_COLOR,
  HIT_COLOR,
  HOVER,
  INK_COLOR,
  INK_MUTED_COLOR,
  NEUTRAL_MARK,
  RED,
  SEQUENTIAL,
  SERIES,
  axis,
  baseLayout,
  type Figure,
} from "./charts";

// --- Model evaluation -----------------------------------------------------

export interface ComparisonRow {
  model: string;
  metrics: Record<string, number | null>;
  baseline: boolean;
}

/** Grouped bars: one trace per model across every metric. */
export function modelComparisonBars(metrics: string[], rows: ComparisonRow[]): Figure {
  const pretty = metrics.map((m) => m.replace(/_/g, " "));
  let slot = 0;
  let baselineSlot = 0;

  // Baselines are references rather than candidates, so they take neutral greys and
  // never consume a categorical slot. Two distinct greys keep them separable in the
  // legend without implying either is a competing model.
  const BASELINE_GREYS = [NEUTRAL_MARK, "#8b95a3"];

  const data: Data[] = rows.map((row) => {
    const color = row.baseline
      ? BASELINE_GREYS[baselineSlot++ % BASELINE_GREYS.length]
      : SERIES[slot++ % SERIES.length];
    const name = row.model.replace(/_/g, " ");
    return {
      type: "bar",
      name,
      x: pretty,
      y: metrics.map((m) => row.metrics[m] ?? null),
      marker: { color, cornerradius: 4, line: { width: 0 } },
      hovertemplate: `${name}<br>%{x}: %{y:.4f}<extra></extra>`,
    } as unknown as Data;
  });

  return {
    data,
    layout: {
      ...baseLayout(400, "Model Comparison"),
      barmode: "group",
      bargap: 0.28,
      bargroupgap: 0.06,
      xaxis: axis(),
      yaxis: axis("Score", { range: [0, 1] }),
      hoverlabel: HOVER,
      legend: { orientation: "h", y: -0.18, bgcolor: "rgba(0,0,0,0)" },
      margin: { l: 55, r: 30, t: 50, b: 80 },
    },
  };
}

/** Confusion matrix: sequential single-hue magnitude with counts written on. */
export function confusionHeatmap(
  matrix: number[][],
  labels: { actual: string[]; predicted: string[] },
): Figure {
  const rowTotals = matrix.map((row) => row.reduce((a, b) => a + b, 0));

  // The sequential ramp darkens with magnitude, so the busiest cell ends up nearly
  // black. Flip the label to white there rather than printing dark-on-dark.
  const peak = Math.max(...matrix.flat(), 1);

  const annotations = matrix.flatMap((row, r) =>
    row.map((value, c) => ({
      x: labels.predicted[c],
      y: labels.actual[r],
      text: `<b>${value.toLocaleString()}</b><br>${
        rowTotals[r] ? ((value / rowTotals[r]) * 100).toFixed(1) : "0"
      }% of row`,
      showarrow: false,
      font: { color: value / peak > 0.55 ? "#FFFFFF" : INK_COLOR, size: 13 },
    })),
  );

  return {
    data: [
      {
        type: "heatmap",
        z: matrix,
        x: labels.predicted,
        y: labels.actual,
        colorscale: SEQUENTIAL,
        showscale: false,
        xgap: 2,
        ygap: 2,
        hovertemplate: "actual %{y} / predicted %{x}: %{z:,}<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(330, "Confusion Matrix (holdout)"),
      annotations,
      xaxis: axis("Predicted"),
      yaxis: axis("Actual", { autorange: "reversed" }),
      hoverlabel: HOVER,
      margin: { l: 95, r: 30, t: 50, b: 60 },
    },
  };
}

export function rocCurve(fpr: number[], tpr: number[], auc: number | null): Figure {
  return {
    data: [
      {
        type: "scatter",
        mode: "lines",
        name: `ROC${auc !== null ? ` (AUC ${auc.toFixed(3)})` : ""}`,
        x: fpr,
        y: tpr,
        line: { color: SERIES[1], width: 2 },
        fill: "tozeroy",
        fillcolor: "rgba(0,144,167,0.12)",
        hovertemplate: "FPR %{x:.3f}<br>TPR %{y:.3f}<extra></extra>",
      } as unknown as Data,
      {
        type: "scatter",
        mode: "lines",
        name: "Chance (AUC 0.5)",
        x: [0, 1],
        y: [0, 1],
        line: { color: NEUTRAL_MARK, width: 2, dash: "dash" },
        hoverinfo: "skip",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(400, "ROC Curve"),
      xaxis: axis("False positive rate", { range: [0, 1] }),
      yaxis: axis("True positive rate", { range: [0, 1] }),
      hovermode: "closest",
      hoverlabel: HOVER,
      legend: { orientation: "h", y: -0.2, bgcolor: "rgba(0,0,0,0)" },
      margin: { l: 60, r: 30, t: 50, b: 80 },
    },
  };
}

export function prCurve(
  recall: number[],
  precision: number[],
  averagePrecision: number | null,
  positiveRate: number | null,
): Figure {
  const data: Data[] = [
    {
      type: "scatter",
      mode: "lines",
      name: `Precision-recall${
        averagePrecision !== null ? ` (AP ${averagePrecision.toFixed(3)})` : ""
      }`,
      x: recall,
      y: precision,
      line: { color: SERIES[3], width: 2 },
      hovertemplate: "recall %{x:.3f}<br>precision %{y:.3f}<extra></extra>",
    } as unknown as Data,
  ];

  if (positiveRate !== null) {
    data.push({
      type: "scatter",
      mode: "lines",
      name: `No-skill (${(positiveRate * 100).toFixed(1)}% positives)`,
      x: [0, 1],
      y: [positiveRate, positiveRate],
      line: { color: NEUTRAL_MARK, width: 2, dash: "dash" },
      hoverinfo: "skip",
    } as unknown as Data);
  }

  return {
    data,
    layout: {
      ...baseLayout(400, "Precision-Recall Curve"),
      xaxis: axis("Recall", { range: [0, 1] }),
      yaxis: axis("Precision", { range: [0, 1] }),
      hovermode: "closest",
      hoverlabel: HOVER,
      legend: { orientation: "h", y: -0.2, bgcolor: "rgba(0,0,0,0)" },
      margin: { l: 60, r: 30, t: 50, b: 80 },
    },
  };
}

export interface FairnessGroup {
  n_samples: number;
  f1_macro: number | null;
  group?: string;
}

/**
 * Sample size (log) against macro F1. One series, so no legend — the title names
 * it. The threshold rule shows why small groups must be excluded: nearly
 * everything left of it scores exactly 0 or 1 because n is tiny.
 */
export function fairnessScatter(groups: FairnessGroup[], minN: number): Figure {
  const cutoff = Math.log10(Math.max(minN, 1));
  return {
    data: [
      {
        type: "scatter",
        mode: "markers",
        x: groups.map((g) => g.n_samples),
        y: groups.map((g) => g.f1_macro),
        text: groups.map((g) => g.group ?? ""),
        marker: {
          size: 9,
          color: SERIES[1],
          opacity: 0.75,
          line: { width: 2, color: BG },
        },
        hovertemplate: "%{text}<br>n = %{x:,}<br>macro F1 %{y:.3f}<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(400, "Per-genre F1 vs group size"),
      xaxis: axis("Samples in group (log scale)", { type: "log" }),
      yaxis: axis("Macro F1", { range: [-0.05, 1.05] }),
      shapes: [
        {
          type: "line",
          x0: cutoff,
          x1: cutoff,
          yref: "paper",
          y0: 0,
          y1: 1,
          line: { color: AMBER, width: 2 },
        },
      ],
      annotations: [
        {
          x: cutoff,
          yref: "paper",
          y: 1,
          text: `n = ${minN} cutoff`,
          showarrow: false,
          xanchor: "left",
          yanchor: "bottom",
          font: { color: INK_MUTED_COLOR, size: 11 },
        },
      ],
      hoverlabel: HOVER,
      margin: { l: 60, r: 30, t: 50, b: 65 },
    },
  };
}

// --- Dataset explorer -----------------------------------------------------

export interface DistributionPayload {
  feature: string;
  bin_centers: (number | null)[];
  hit_counts: number[];
  flop_counts: number[];
}

/**
 * Hit vs non-hit distribution of one feature, as share *within each class* rather
 * than raw counts: non-hits outnumber hits ~5:1, so raw counts would flatten the
 * hit series against the axis and hide the comparison the chart exists to make.
 */
export function featureDistribution(dist: DistributionPayload): Figure {
  const share = (counts: number[]) => {
    const total = counts.reduce((a, b) => a + b, 0);
    return total ? counts.map((c) => (c / total) * 100) : counts;
  };

  return {
    data: [
      {
        type: "bar",
        name: "Non-hits",
        x: dist.bin_centers,
        y: share(dist.flop_counts),
        marker: { color: FLOP_COLOR, line: { width: 0 } },
        opacity: 0.55,
        hovertemplate: "non-hits &middot; %{x:.4g}<br>%{y:.2f}% of non-hits<extra></extra>",
      } as unknown as Data,
      {
        type: "scatter",
        mode: "lines",
        name: "Hits",
        x: dist.bin_centers,
        y: share(dist.hit_counts),
        line: { color: HIT_COLOR, width: 3, shape: "spline", smoothing: 0.6 },
        hovertemplate: "hits &middot; %{x:.4g}<br>%{y:.2f}% of hits<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(400, `${dist.feature} - hits vs non-hits`),
      barmode: "overlay",
      bargap: 0.04,
      xaxis: axis(dist.feature),
      yaxis: axis("Share within class (%)"),
      hovermode: "closest",
      hoverlabel: HOVER,
      legend: { orientation: "h", y: -0.2, bgcolor: "rgba(0,0,0,0)" },
      margin: { l: 65, r: 30, t: 50, b: 80 },
    },
  };
}

/** Correlation matrix: diverging scale anchored at zero over a fixed -1..1 domain. */
export function correlationHeatmap(labels: string[], matrix: (number | null)[][]): Figure {
  return {
    data: [
      {
        type: "heatmap",
        z: matrix,
        x: labels,
        y: labels,
        colorscale: DIVERGING,
        zmid: 0,
        zmin: -1,
        zmax: 1,
        xgap: 2,
        ygap: 2,
        colorbar: { thickness: 12, len: 0.85, title: { text: "r" }, tickfont: { size: 11 } },
        hovertemplate: "%{y} &times; %{x}<br>r = %{z:.3f}<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(600, "Feature correlations (Pearson r)"),
      xaxis: axis(undefined, { tickangle: -45, automargin: true }),
      yaxis: axis(undefined, { automargin: true, autorange: "reversed" }),
      hoverlabel: HOVER,
      margin: { l: 30, r: 30, t: 50, b: 30 },
    },
  };
}

/** Volume per genre. Nominal categories, so every bar takes the same hue. */
export function genreVolumeBars(labels: string[], volumes: number[]): Figure {
  const order = [...labels.keys()].reverse();
  return {
    data: [
      {
        type: "bar",
        orientation: "h",
        y: order.map((i) => labels[i]),
        x: order.map((i) => volumes[i]),
        marker: { color: SERIES[0], cornerradius: 4, line: { width: 0 } },
        hovertemplate: "%{y}<br>%{x:,} tracks<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(430, "Tracks per genre"),
      bargap: 0.3,
      xaxis: axis("Tracks"),
      yaxis: axis(undefined, { type: "category", automargin: true }),
      hoverlabel: HOVER,
      margin: { l: 30, r: 30, t: 50, b: 60 },
    },
  };
}

/**
 * Hit rate per genre — a companion chart to genreVolumeBars rather than a second
 * axis on it, so the two scales are never visually equated.
 */
export function genreHitRateBars(
  labels: string[],
  rates: (number | null)[],
  overallRate: number | null,
): Figure {
  const order = [...labels.keys()].reverse();
  const marker =
    overallRate !== null
      ? [
          {
            type: "line" as const,
            x0: overallRate * 100,
            x1: overallRate * 100,
            yref: "paper" as const,
            y0: 0,
            y1: 1,
            line: { color: AMBER, width: 2 },
          },
        ]
      : [];

  return {
    data: [
      {
        type: "bar",
        orientation: "h",
        y: order.map((i) => labels[i]),
        x: order.map((i) => (rates[i] ?? 0) * 100),
        marker: { color: SERIES[3], cornerradius: 4, line: { width: 0 } },
        hovertemplate: "%{y}<br>hit rate %{x:.1f}%<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(430, "Hit rate per genre"),
      bargap: 0.3,
      xaxis: axis("Hit rate (%)"),
      yaxis: axis(undefined, { type: "category", automargin: true }),
      shapes: marker,
      annotations:
        overallRate !== null
          ? [
              {
                x: overallRate * 100,
                yref: "paper",
                y: 1,
                text: `dataset average ${(overallRate * 100).toFixed(1)}%`,
                showarrow: false,
                xanchor: "left",
                yanchor: "bottom",
                font: { color: INK_MUTED_COLOR, size: 11 },
              },
            ]
          : [],
      hoverlabel: HOVER,
      margin: { l: 30, r: 30, t: 50, b: 60 },
    },
  };
}

/** Hit rate over time. Single series, crosshair hover. */
export function hitRateByYearLine(
  years: number[],
  rates: (number | null)[],
  currentYear: number,
): Figure {
  const futureStart = years.find((y) => y > currentYear);
  return {
    data: [
      {
        type: "scatter",
        mode: "lines+markers",
        x: years,
        y: rates.map((r) => (r === null ? null : r * 100)),
        line: { color: SERIES[0], width: 2 },
        marker: { size: 5 },
        hovertemplate: "hit rate %{y:.1f}%<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(350, "Hit rate by release year"),
      xaxis: axis("Release year"),
      yaxis: axis("Hit rate (%)"),
      hovermode: "x unified",
      hoverlabel: HOVER,
      // Shade the impossible-date region instead of silently plotting it as data.
      shapes: futureStart
        ? [
            {
              type: "rect",
              x0: futureStart,
              x1: Math.max(...years),
              yref: "paper",
              y0: 0,
              y1: 1,
              fillcolor: "rgba(255,59,59,0.10)",
              line: { width: 0 },
            },
          ]
        : [],
      annotations: futureStart
        ? [
            {
              x: futureStart,
              yref: "paper",
              y: 1,
              text: "impossible future dates",
              showarrow: false,
              xanchor: "left",
              yanchor: "bottom",
              font: { color: RED, size: 11 },
            },
          ]
        : [],
      margin: { l: 60, r: 30, t: 50, b: 60 },
    },
  };
}

/** Release volume over time — companion to hitRateByYearLine on a shared x. */
export function yearVolumeBars(years: number[], counts: number[]): Figure {
  return {
    data: [
      {
        type: "bar",
        x: years,
        y: counts,
        marker: { color: SERIES[1], cornerradius: 3, line: { width: 0 } },
        hovertemplate: "%{y:,} tracks<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(270, "Tracks per release year"),
      bargap: 0.15,
      xaxis: axis("Release year"),
      yaxis: axis("Tracks"),
      hovermode: "x unified",
      hoverlabel: HOVER,
      margin: { l: 60, r: 30, t: 50, b: 60 },
    },
  };
}

// --- History --------------------------------------------------------------

export interface HistoryPoint {
  timestamp: number;
  score: number;
  mode: string;
}

/** Session prediction scores in order, with the 50% decision threshold marked. */
export function historyTrend(points: HistoryPoint[]): Figure {
  const ordered = [...points].sort((a, b) => a.timestamp - b.timestamp);
  return {
    data: [
      {
        type: "scatter",
        mode: "lines+markers",
        x: ordered.map((p) => new Date(p.timestamp).toISOString()),
        y: ordered.map((p) => p.score * 100),
        text: ordered.map((p) => p.mode),
        line: { color: SERIES[1], width: 2 },
        marker: { size: 9, line: { width: 2, color: BG } },
        hovertemplate: "%{text}<br>%{y:.1f}%<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(330, "Prediction scores this session"),
      xaxis: axis("Time"),
      yaxis: axis("Hit potential (%)", { range: [0, 100] }),
      shapes: [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          y0: 50,
          y1: 50,
          line: { color: AMBER, width: 2 },
        },
      ],
      annotations: [
        {
          xref: "paper",
          x: 0,
          y: 50,
          text: "hit threshold",
          showarrow: false,
          xanchor: "left",
          yanchor: "bottom",
          font: { color: INK_MUTED_COLOR, size: 11 },
        },
      ],
      hovermode: "closest",
      hoverlabel: HOVER,
      margin: { l: 60, r: 30, t: 50, b: 60 },
    },
  };
}
