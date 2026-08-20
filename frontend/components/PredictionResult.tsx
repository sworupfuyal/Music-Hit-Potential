"use client";

import confetti from "canvas-confetti";
import { useEffect, useRef } from "react";

import {
  NEON_GREEN,
  featureRadar,
  hasMfcc,
  hitGauge,
  mfccHeatmap,
  verdictLabel,
} from "@/lib/charts";
import { addHistoryEntry, type HistoryEntry } from "@/lib/history";
import type { ModelMetadata, NumberMap } from "@/lib/types";

import { Chart } from "./Chart";

/**
 * The dramatic single-prediction output: verdict headline, gauge, acoustic radar
 * and MFCC barcode. Scores at or above 70% fire confetti, standing in for the old
 * `st.balloons()`. Each distinct result is also appended to the session history.
 */
export function PredictionResult({
  model,
  probability,
  features,
  mode,
  detail = "",
}: {
  model: ModelMetadata;
  probability: number;
  features: NumberMap | null;
  mode: HistoryEntry["mode"];
  detail?: string;
}) {
  const pct = probability * 100;
  const { label, color } = verdictLabel(pct);

  useEffect(() => {
    if (pct < 70) return;
    void confetti({
      particleCount: 140,
      spread: 80,
      origin: { y: 0.3 },
      colors: [NEON_GREEN, "#19d3f3", "#ffb000", "#ffffff"],
    });
  }, [pct, probability]);

  // Signature-based guard: dedupes React's double-invoked effects in development
  // while still logging genuinely new results on this same mounted component.
  const lastLogged = useRef<string | null>(null);
  useEffect(() => {
    const signature = `${mode}|${probability}|${detail}`;
    if (lastLogged.current === signature) return;
    lastLogged.current = signature;
    addHistoryEntry({ mode, score: probability, verdict: label, detail });
  }, [mode, probability, detail, label]);

  const radar = features
    ? featureRadar(features, model.hit_profile, model.flop_profile, model.feature_ranges)
    : null;
  const showMfcc = features !== null && hasMfcc(features);

  return (
    <div className="animate-rise space-y-4">
      <h2 className="text-center text-3xl font-bold" style={{ color }}>
        {label}
      </h2>

      <div className="grid gap-4 lg:grid-cols-2">
        <Chart figure={hitGauge(probability)} />
        {radar ? <Chart figure={radar} /> : null}
      </div>

      {showMfcc && features ? <Chart figure={mfccHeatmap(features)} /> : null}
    </div>
  );
}
