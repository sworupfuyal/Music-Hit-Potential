"use client";

/** Single Song Input — a form generated from the bundle's feature columns. */

import { useMemo, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { ModelMetadata, NumberMap } from "@/lib/types";

import { PredictionResult } from "../PredictionResult";
import { Alert, Button, Card, SectionTitle } from "../ui";

type FormValues = Record<string, string>;

function initialValues(model: ModelMetadata): FormValues {
  const values: FormValues = {};
  for (const col of model.feature_columns) {
    if (model.numeric_columns.includes(col)) {
      const fallback = model.numeric_defaults[col];
      values[col] = String(fallback ?? 0);
    } else {
      values[col] = "";
    }
  }
  return values;
}

export function SingleTab({ model }: { model: ModelMetadata }) {
  const [values, setValues] = useState<FormValues>(() => initialValues(model));
  const [probability, setProbability] = useState<number | null>(null);
  const [features, setFeatures] = useState<NumberMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const numericSet = useMemo(() => new Set(model.numeric_columns), [model.numeric_columns]);

  const setValue = (col: string, value: string) =>
    setValues((prev) => ({ ...prev, [col]: value }));

  const predict = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, number | string> = {};
      for (const col of model.feature_columns) {
        if (numericSet.has(col)) {
          const parsed = Number.parseFloat(values[col]);
          payload[col] = Number.isFinite(parsed)
            ? parsed
            : (model.numeric_defaults[col] ?? 0);
        } else {
          payload[col] = values[col] ?? "";
        }
      }
      const result = await api.predictSingle(payload);
      setProbability(result.probability);
      setFeatures(result.features);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : String(exc));
      setProbability(null);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setValues(initialValues(model));
    setProbability(null);
    setFeatures(null);
    setError(null);
  };

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex items-center justify-between gap-4">
          <SectionTitle>Single Song Input</SectionTitle>
          <Button variant="ghost" onClick={reset}>
            Reset to defaults
          </Button>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {model.feature_columns.map((col) =>
            numericSet.has(col) ? (
              <label key={col} className="space-y-1">
                <span className="block text-xs font-medium text-muted">{col}</span>
                <input
                  type="number"
                  step="any"
                  value={values[col]}
                  onChange={(event) => setValue(col, event.target.value)}
                  className="w-full rounded-lg border border-edge bg-canvas px-3 py-2 text-sm tabular-nums outline-none focus:border-brand"
                />
              </label>
            ) : (
              <label key={col} className="space-y-1">
                <span className="block text-xs font-medium text-muted">{col}</span>
                <select
                  value={values[col]}
                  onChange={(event) => setValue(col, event.target.value)}
                  className="w-full rounded-lg border border-edge bg-canvas px-3 py-2 text-sm outline-none focus:border-brand"
                >
                  <option value=""></option>
                  {(model.category_options[col] ?? []).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            ),
          )}
        </div>

        <div className="mt-5">
          <Button onClick={predict} disabled={busy}>
            {busy ? "Predicting…" : "Predict Hit Potential"}
          </Button>
        </div>
      </Card>

      {error ? <Alert kind="error">{error}</Alert> : null}

      {probability !== null ? (
        <Card>
          <PredictionResult
            model={model}
            probability={probability}
            features={features}
            mode="Single"
            detail="Manual feature entry"
          />
        </Card>
      ) : null}
    </div>
  );
}
