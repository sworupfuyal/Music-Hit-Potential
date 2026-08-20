"use client";

/**
 * Local Audio File — train a Spotify-free model from data/audio/{hit,not_hit},
 * and score an uploaded audio file on the same Librosa features.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { AudioLibrary, AudioPredictionResponse, ModelMetadata } from "@/lib/types";
import { useTrainingJob } from "@/lib/useTrainingJob";

import { PredictionResult } from "../PredictionResult";
import { Alert, Button, Card, Expander, Metric, ProgressBar } from "../ui";

function AudioTrainingPanel({
  model,
  onModelChanged,
}: {
  model: ModelMetadata;
  onModelChanged: () => void;
}) {
  const [library, setLibrary] = useState<AudioLibrary | null>(null);
  const [libraryError, setLibraryError] = useState<string | null>(null);

  const refreshLibrary = useCallback(() => {
    api
      .getAudioLibrary()
      .then(setLibrary)
      .catch((exc: unknown) =>
        setLibraryError(exc instanceof ApiError ? exc.message : String(exc)),
      );
  }, []);

  useEffect(refreshLibrary, [refreshLibrary]);

  const finished = useCallback(() => {
    onModelChanged();
    refreshLibrary();
  }, [onModelChanged, refreshLibrary]);

  const { job, error, running, fraction, start } = useTrainingJob(finished);

  const disabled = !library?.ready || running;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Drop songs into <code className="text-ink">data/audio/hit/</code> and{" "}
        <code className="text-ink">data/audio/not_hit/</code>, then train. This builds a
        model on the same Librosa features uploads use, so scores become meaningful.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <Metric label="🔥 hit/ folder" value={library?.hit ?? "…"} />
        <Metric label="💀 not_hit/ folder" value={library?.not_hit ?? "…"} />
      </div>

      {libraryError ? <Alert kind="error">{libraryError}</Alert> : null}

      {model.trained_on === "local_audio" ? (
        <Alert kind="success">
          Active model was trained on {model.n_train_songs ?? "?"} local songs.
        </Alert>
      ) : null}

      {library && !library.ready ? (
        <Alert kind="info">Add at least one song to BOTH folders to enable training.</Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void start(api.trainAudio)} disabled={disabled}>
          {running ? "Training…" : "Train From Audio Folders"}
        </Button>
        <Button variant="ghost" onClick={refreshLibrary} disabled={running}>
          Refresh folder counts
        </Button>
      </div>

      {job ? (
        <div className="space-y-2">
          <ProgressBar value={fraction} />
          <p className="text-sm text-muted">{job.message}</p>
        </div>
      ) : null}

      {job?.status === "succeeded" && job.result ? (
        <Alert kind="success">
          Trained &apos;{job.result.model_name}&apos; on {job.result.n_train_songs} songs
          (macro F1 {job.result.f1_macro?.toFixed(3)}).
        </Alert>
      ) : null}

      {error ? <Alert kind="error">{error}</Alert> : null}
    </div>
  );
}

export function AudioTab({
  model,
  onModelChanged,
}: {
  model: ModelMetadata;
  onModelChanged: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AudioPredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const objectUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => {
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [objectUrl]);

  const predict = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.predictAudio(file));
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <Expander title="🎓 Train a model from your own audio (Spotify-free)">
        <AudioTrainingPanel model={model} onModelChanged={onModelChanged} />
      </Expander>

      <Card>
        <p className="text-sm">
          Upload an audio file (MP3, WAV, OGG, FLAC) and predict hit potential from its
          acoustic features.
        </p>
        <p className="mt-1 text-xs text-muted">
          Requires ffmpeg on PATH for MP3/OGG/FLAC decoding. WAV works without ffmpeg.
        </p>

        <label className="mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-edge bg-canvas px-6 py-8 text-center transition hover:border-brand/50 hover:bg-brand-tint/40">
          <span className="text-sm font-semibold">{file?.name ?? "Choose an audio file"}</span>
          <span className="text-xs text-muted">.mp3 .wav .ogg .flac .m4a</span>
          <input
            type="file"
            accept=".mp3,.wav,.ogg,.flac,.m4a,audio/*"
            className="hidden"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setResult(null);
              setError(null);
            }}
          />
        </label>

        {objectUrl ? (
          <audio controls src={objectUrl} className="mt-4 w-full">
            <track kind="captions" />
          </audio>
        ) : null}

        <div className="mt-4">
          <Button onClick={predict} disabled={!file || busy}>
            {busy ? "Extracting features…" : "Extract Features & Predict"}
          </Button>
        </div>
      </Card>

      {error ? <Alert kind="error">{error}</Alert> : null}

      {result ? (
        <Card>
          <PredictionResult
            model={model}
            probability={result.probability}
            features={result.features}
            mode="Local audio"
            detail={file?.name ?? "Uploaded audio"}
          />
          <div className="mt-5">
            <Expander title="Extracted audio features">
              <pre className="max-h-72 overflow-auto rounded-lg bg-canvas p-4 text-xs text-muted">
                {JSON.stringify(result.audio_features, null, 2)}
              </pre>
            </Expander>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
