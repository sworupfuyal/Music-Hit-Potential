"use client";

/**
 * Shown when no bundle exists yet: trains the app model from the project dataset.
 * Mirrors the old app's "Train App Model" button, XGBoost toggle and progress bar.
 */

import { useState } from "react";

import { api } from "@/lib/api";
import { useTrainingJob } from "@/lib/useTrainingJob";

import { Alert, Button, Card, ProgressBar } from "./ui";

export function DatasetTraining({
  onModelChanged,
  notice,
}: {
  onModelChanged: () => void;
  notice?: string | null;
}) {
  const [includeXgboost, setIncludeXgboost] = useState(false);
  const { job, error, running, fraction, start } = useTrainingJob(onModelChanged);

  return (
    <Card className="space-y-4">
      {notice ? <Alert kind="warning">{notice}</Alert> : null}
      <Alert kind="info">No saved app model found yet. Train one to unlock predictions.</Alert>

      <div className="flex flex-wrap items-center gap-4">
        <Button
          onClick={() => void start(() => api.trainDataset(includeXgboost))}
          disabled={running}
        >
          {running ? "Training…" : "Train App Model"}
        </Button>

        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={includeXgboost}
            onChange={(event) => setIncludeXgboost(event.target.checked)}
            disabled={running}
            className="size-4 accent-[var(--color-brand)]"
          />
          Include XGBoost (slower)
        </label>
      </div>

      {job ? (
        <div className="space-y-2">
          <ProgressBar value={fraction} />
          <p className="text-sm text-muted">{job.message}</p>
        </div>
      ) : null}

      {error ? <Alert kind="error">Could not train app model: {error}</Alert> : null}
    </Card>
  );
}
