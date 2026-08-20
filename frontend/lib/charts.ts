/**
 * Plotly chart builders — a direct TypeScript port of the former src/visuals.py.
 *
 * Every builder returns { data, layout } styled with the same dark neon theme the
 * Streamlit app used, so the migrated UI renders identical charts client-side.
 */

import type { Data, Layout } from "plotly.js";

import type { BatchScatter, NumberMap } from "./types";

// --- Theme ----------------------------------------------------------------
// Chart surface is the white card the plot sits on, not the ivory page canvas.
export const BG = "#FFFFFF";
const GRID = "rgba(20,22,26,0.10)";
const INK = "#14161A";
const INK_MUTED = "#5F6673";

/**
 * Chart-mark palette, validated for the LIGHT surface with the dataviz checker
 * against #FFFFFF:
 *   SERIES (4 slots)     lightness PASS · chroma PASS · CVD ΔE 13.1 · normal ΔE 17.1 · contrast ≥3:1
 *   HIT/FLOP pair        CVD ΔE 8.7 · normal ΔE 40.8 · contrast 3.68 / 3.84
 *   SEQUENTIAL (5 steps) monotone light→dark · ΔL ≥ 0.06 · light end 2.31:1
 * Assign SERIES in fixed order and never cycle past slot 4.
 */
export const SERIES = ["#00a848", "#0090a7", "#ba7f00", "#e50083"] as const;
export const HIT_COLOR = "#039a41";
export const FLOP_COLOR = "#f51f8f";
export const NEUTRAL_MARK = "#6b7280";

/**
 * Brand hues for the hero charts. These are the darker steps rather than the raw
 * neon values, which sit too light to read as marks on white.
 */
export const NEON_GREEN = "#00a848";
export const NEON_PINK = "#e50083";
export const NEON_BLUE = "#0090a7";
export const AMBER = "#ba7f00";
export const RED = "#c2261b";

/** Verdict text colours — these carry words, so they clear text contrast (4.5:1). */
export const VERDICT_GREEN = "#0b7a3b";
export const VERDICT_AMBER = "#8a5a00";
export const VERDICT_RED = "#b3261e";

/** Sequential, one hue, low→high. On a light surface magnitude reads as darker. */
export const SEQUENTIAL: [number, string][] = [
  [0, "#2fc35e"],
  [0.25, "#05a547"],
  [0.5, "#008637"],
  [0.75, "#016729"],
  [1, "#014b1c"],
];

/**
 * Diverging, cool ↔ warm. The midpoint is near-surface grey so zero correlation
 * reads as blank rather than as a colour of its own.
 */
export const DIVERGING: [number, string][] = [
  [0, "#006070"],
  [0.25, "#03899f"],
  [0.5, "#eceef1"],
  [0.75, "#e31021"],
  [1, "#a30012"],
];

export const GRID_COLOR = GRID;
export const INK_COLOR = INK;
export const INK_MUTED_COLOR = INK_MUTED;

/** Tooltip styling shared by every analytics chart. */
export const HOVER = {
  bgcolor: "#FFFFFF",
  bordercolor: "rgba(20,22,26,0.18)",
  font: { color: INK, size: 12 },
};

/** Axis defaults: solid hairline grid, one shade off the surface. */
export function axis(title?: string, extra: Record<string, unknown> = {}) {
  return {
    ...(title ? { title: { text: title, font: { size: 12, color: INK_MUTED } } } : {}),
    gridcolor: GRID,
    zerolinecolor: GRID,
    ...extra,
  };
}

export const MFCC_NAMES = Array.from({ length: 13 }, (_, i) => `mfcc_${i + 1}`);

export const RADAR_FEATURES = [
  "tempo",
  "energy",
  "loudness_db",
  "zcr",
  "spectral_centroid",
  "spectral_rolloff",
  "spectral_bandwidth",
  "chroma",
];

export interface Figure {
  data: Data[];
  layout: Partial<Layout>;
}

export function baseLayout(height = 360, title?: string): Partial<Layout> {
  return {
    paper_bgcolor: BG,
    plot_bgcolor: BG,
    font: { color: INK, size: 13 },
    margin: { l: 30, r: 30, t: title ? 50 : 20, b: 30 },
    height,
    ...(title ? { title: { text: title, x: 0.5, font: { size: 16 } } } : {}),
    legend: { bgcolor: "rgba(0,0,0,0)", orientation: "h", y: -0.15 },
  };
}

function num(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

// --- 1. Hero gauge --------------------------------------------------------

export function hitGauge(proba: number): Figure {
  const pct = proba * 100;
  const barColor = pct >= 70 ? NEON_GREEN : pct >= 40 ? AMBER : RED;

  return {
    data: [
      {
        type: "indicator",
        mode: "gauge+number+delta",
        value: pct,
        number: { suffix: "%", font: { size: 46, color: barColor } },
        delta: {
          reference: 50,
          increasing: { color: NEON_GREEN },
          decreasing: { color: RED },
          suffix: " vs threshold",
        },
        gauge: {
          axis: { range: [0, 100], tickwidth: 1, tickcolor: INK_MUTED },
          bar: { color: barColor, thickness: 0.3 },
          bgcolor: BG,
          borderwidth: 0,
          steps: [
            { range: [0, 40], color: "rgba(194,38,27,0.10)" },
            { range: [40, 70], color: "rgba(186,127,0,0.12)" },
            { range: [70, 100], color: "rgba(0,168,72,0.14)" },
          ],
          threshold: {
            line: { color: INK, width: 3 },
            thickness: 0.78,
            value: 50,
          },
        },
      } as unknown as Data,
    ],
    layout: baseLayout(320),
  };
}

export function verdictLabel(pct: number): { label: string; color: string } {
  if (pct >= 70) return { label: "🔥 BANGER", color: VERDICT_GREEN };
  if (pct >= 40) return { label: "😴 SLEEPER", color: VERDICT_AMBER };
  return { label: "💀 FLOP", color: VERDICT_RED };
}

// --- 2. Radar fingerprint -------------------------------------------------

function normalize(value: number, lo: number, hi: number): number {
  if (hi <= lo) return 0;
  return Math.min(Math.max((value - lo) / (hi - lo), 0), 1);
}

export function featureRadar(
  songFeats: NumberMap,
  hitProfile: NumberMap | null,
  flopProfile: NumberMap | null,
  featureRanges: Record<string, [number | null, number | null]> | null,
): Figure | null {
  const feats = RADAR_FEATURES.filter((f) => f in songFeats);
  if (feats.length === 0) return null;

  const ranges = featureRanges ?? {};

  const row = (profile: NumberMap | null): number[] =>
    feats.map((f) => {
      const [lo, hi] = ranges[f] ?? [0, 1];
      const source = profile ?? songFeats;
      return normalize(num(source[f]), num(lo), hi === null ? 1 : hi);
    });

  const closed = [...feats, feats[0]];
  const songVals = row(songFeats);

  const data: Data[] = [
    {
      type: "scatterpolar",
      r: [...songVals, songVals[0]],
      theta: closed,
      fill: "toself",
      name: "This song",
      line: { color: NEON_BLUE, width: 3 },
      fillcolor: "rgba(0,144,167,0.18)",
    } as unknown as Data,
  ];

  if (hitProfile && Object.keys(hitProfile).length > 0) {
    const hv = row(hitProfile);
    data.push({
      type: "scatterpolar",
      r: [...hv, hv[0]],
      theta: closed,
      fill: "toself",
      name: "Avg hit",
      line: { color: NEON_GREEN, width: 2, dash: "dot" },
      fillcolor: "rgba(0,168,72,0.12)",
    } as unknown as Data);
  }

  if (flopProfile && Object.keys(flopProfile).length > 0) {
    const fv = row(flopProfile);
    data.push({
      type: "scatterpolar",
      r: [...fv, fv[0]],
      theta: closed,
      fill: "toself",
      name: "Avg flop",
      line: { color: NEON_PINK, width: 2, dash: "dot" },
      fillcolor: "rgba(229,0,131,0.10)",
    } as unknown as Data);
  }

  return {
    data,
    layout: {
      ...baseLayout(420, "Acoustic Fingerprint"),
      polar: {
        bgcolor: BG,
        radialaxis: { visible: true, range: [0, 1], gridcolor: GRID, showticklabels: false },
        angularaxis: { gridcolor: GRID },
      },
    },
  };
}

// --- 3. MFCC heatmap strip ------------------------------------------------

export function hasMfcc(feats: NumberMap): boolean {
  return MFCC_NAMES.some((name) => num(feats[name]) !== 0);
}

export function mfccHeatmap(audioFeats: NumberMap): Figure {
  const values = MFCC_NAMES.map((name) => num(audioFeats[name]));
  return {
    data: [
      {
        type: "heatmap",
        z: [values],
        x: Array.from({ length: 13 }, (_, i) => `M${i + 1}`),
        y: ["MFCC"],
        colorscale: DIVERGING,
        zmid: 0,
        showscale: true,
        colorbar: { thickness: 12, len: 0.9 },
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(160, "Audio DNA (MFCC barcode)"),
      yaxis: { showticklabels: false },
    },
  };
}

// --- 4. Batch charts ------------------------------------------------------

export function batchHistogram(scores: number[]): Figure {
  return {
    data: [
      {
        type: "histogram",
        x: scores.map((s) => s * 100),
        nbinsx: 25,
        marker: { color: NEON_GREEN, line: { color: BG, width: 1 } },
        opacity: 0.85,
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(340, "Score Distribution"),
      xaxis: { title: { text: "Hit potential (%)" }, gridcolor: GRID, range: [0, 100] },
      yaxis: { title: { text: "Songs" }, gridcolor: GRID },
      shapes: [
        {
          type: "line",
          x0: 50,
          x1: 50,
          yref: "paper",
          y0: 0,
          y1: 1,
          line: { color: INK, width: 2, dash: "dash" },
        },
      ],
      annotations: [
        {
          x: 50,
          yref: "paper",
          y: 1,
          text: "Hit threshold",
          showarrow: false,
          yanchor: "bottom",
        },
      ],
    },
  };
}

export function batchRankedBars(labels: string[], scores: number[], topN = 10): Figure {
  // Reversed so the strongest bar sits at the top of a horizontal chart.
  const order = [...labels.keys()].reverse();
  const y = order.map((i) => labels[i]);
  const x = order.map((i) => scores[i] * 100);

  return {
    data: [
      {
        type: "bar",
        x,
        y,
        orientation: "h",
        marker: { color: SERIES[0], cornerradius: 4, line: { width: 0 } },
        text: x.map((v) => `${v.toFixed(1)}%`),
        textposition: "outside",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(380, `Top ${topN} Predicted Hits`),
      xaxis: { title: { text: "Hit potential (%)" }, gridcolor: GRID, range: [0, 105] },
      yaxis: { gridcolor: GRID, type: "category" },
    },
  };
}

export function batchScatter(scatter: BatchScatter): Figure {
  return {
    data: [
      {
        type: "scatter",
        x: scatter.x,
        y: scatter.y,
        mode: "markers",
        marker: {
          size: 10,
          color: scatter.score.map((s) => s * 100),
          colorscale: SEQUENTIAL,
          cmin: 0,
          cmax: 100,
          showscale: true,
          opacity: 0.8,
          colorbar: { title: { text: "Hit %" }, thickness: 12 },
          line: { width: 0.5, color: "rgba(255,255,255,0.3)" },
        },
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(380, `${scatter.y_label} vs ${scatter.x_label}`),
      xaxis: { title: { text: scatter.x_label }, gridcolor: GRID },
      yaxis: { title: { text: scatter.y_label }, gridcolor: GRID },
    },
  };
}

// --- 5. Feature importance ------------------------------------------------

export function featureImportanceChart(
  names: string[],
  values: number[],
  topN = 15,
): Figure {
  // One-hot genre columns produce very long names. The categories stay full (they
  // must remain unique, or Plotly merges rows) and only the tick text is clipped;
  // hover shows the whole name.
  const ticktext = names.map((name) =>
    name.length > 34 ? `${name.slice(0, 33)}…` : name,
  );

  return {
    data: [
      {
        type: "bar",
        x: values,
        y: names,
        orientation: "h",
        marker: { color: SERIES[0], cornerradius: 4, line: { width: 0 } },
        hovertemplate: "%{y}<br>Importance: %{x:.4f}<extra></extra>",
      } as unknown as Data,
    ],
    layout: {
      ...baseLayout(460, `Top ${topN} Hit Drivers`),
      xaxis: { title: { text: "Importance" }, gridcolor: GRID },
      yaxis: {
        gridcolor: GRID,
        type: "category",
        automargin: true,
        tickmode: "array",
        tickvals: names,
        ticktext,
      },
    },
  };
}
