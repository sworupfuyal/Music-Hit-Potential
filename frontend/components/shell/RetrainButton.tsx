"use client";

/**
 * Sidebar action that retrains the app model from the project dataset.
 *
 * Training runs as a background job on the API, so this starts the job and polls
 * it, showing progress in place. On success the model context refreshes, which
 * repaints the top bar, the dashboard tiles and the generated prediction form
 * without a page reload.
 *
 * This retrains the *app* bundle. It does not regenerate the thesis artefacts in
 * reports/results — those come from scripts/run_experiments.py.
 */

import { useModel } from "@/app/providers";
import { EqualizerBars } from "@/components/music";
import { ProgressBar } from "@/components/ui";
import { api } from "@/lib/api";
import { useTrainingJob } from "@/lib/useTrainingJob";

export function RetrainButton() {
  const { refresh } = useModel();
  const { job, error, running, fraction, start } = useTrainingJob(refresh);

  const succeeded = job?.status === "succeeded" && job.result;

  return (
    <div className="space-y-2 border-t border-edge pt-3">
      <button
        type="button"
        onClick={() => void start(() => api.trainDataset(true))}
        disabled={running}
        title="Retrain the app model from data/raw/spotify.csv, including XGBoost"
        className="flex w-full items-center gap-3 rounded-full border border-edge px-3 py-2 text-sm font-medium text-muted transition hover:border-brand/50 hover:bg-brand-tint hover:text-brand-strong disabled:cursor-not-allowed disabled:opacity-60"
      >
        {running ? (
          <EqualizerBars className="h-3.5 w-4" />
        ) : (
          <span aria-hidden className="w-4 text-center">
            ⟳
          </span>
        )}
        {running ? "Retraining…" : "Retrain model"}
      </button>

      {running ? (
        <div className="space-y-1 px-1">
          <ProgressBar value={fraction} />
          <p className="truncate text-[11px] text-muted" title={job?.message}>
            {job?.message}
          </p>
        </div>
      ) : null}

      {succeeded && !running ? (
        <p className="px-1 text-[11px] text-brand-strong">
          Trained {job.result?.model_name?.replace(/_/g, " ")} · macro F1{" "}
          {job.result?.f1_macro?.toFixed(3)}
        </p>
      ) : null}

      {error ? <p className="px-1 text-[11px] text-danger">{error}</p> : null}
    </div>
  );
}
