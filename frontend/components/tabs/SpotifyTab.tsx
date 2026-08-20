"use client";

/** Spotify URL/ID — fetch track + artist metadata and preview audio, then predict. */

import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import type {
  ModelMetadata,
  SpotifyCreds,
  SpotifyPredictionResponse,
} from "@/lib/types";

import { PredictionResult } from "../PredictionResult";
import { Alert, Button, Card } from "../ui";

export function SpotifyTab({
  model,
  creds,
}: {
  model: ModelMetadata;
  creds: SpotifyCreds;
}) {
  const [track, setTrack] = useState("");
  const [result, setResult] = useState<SpotifyPredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const predict = async () => {
    if (!creds.clientId || !creds.clientSecret) {
      setError("Please provide Spotify Client ID and Client Secret in the sidebar.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.predictSpotify(track, creds.clientId, creds.clientSecret));
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const display = result?.display;

  return (
    <div className="space-y-5">
      <Card>
        <p className="text-sm">Predict from a Spotify track URL, URI, or track ID.</p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={track}
            onChange={(event) => setTrack(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !busy) void predict();
            }}
            placeholder="https://open.spotify.com/track/<id> or spotify:track:<id>"
            className="flex-1 rounded-lg border border-edge bg-canvas px-3 py-2 text-sm outline-none focus:border-brand"
          />
          <Button onClick={predict} disabled={busy}>
            {busy ? "Fetching…" : "Fetch From Spotify And Predict"}
          </Button>
        </div>
      </Card>

      {error ? <Alert kind="error">{error}</Alert> : null}

      {display?.audio_warning ? (
        <Alert kind="warning">
          Audio features unavailable — {display.audio_warning} Some features are zeroed;
          prediction accuracy may be reduced.
        </Alert>
      ) : null}

      {result && display ? (
        <Card>
          <div className="flex flex-wrap items-center gap-4">
            {display.album_image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={display.album_image}
                alt={display.album_name}
                className="h-20 w-20 rounded-lg object-cover"
              />
            ) : null}
            <div className="text-sm">
              <div className="text-base font-semibold">{display.track_name}</div>
              <div className="text-muted">
                {[display.artist_name, display.album_name, display.primary_genre]
                  .filter(Boolean)
                  .join("  ·  ")}
              </div>
            </div>
          </div>

          {display.preview_url ? (
            <audio controls src={display.preview_url} className="mt-4 w-full">
              <track kind="captions" />
            </audio>
          ) : null}

          <div className="mt-5">
            <PredictionResult
              model={model}
              probability={result.probability}
              features={result.features}
              mode="Spotify"
              detail={[display.track_name, display.artist_name].filter(Boolean).join(" - ")}
            />
          </div>
        </Card>
      ) : null}
    </div>
  );
}
