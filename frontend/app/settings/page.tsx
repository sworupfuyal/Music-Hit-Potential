"use client";

/** Credentials, model actions and API details. */

import { useModel, useSettings } from "@/app/providers";
import { SpotifyCredentialsPanel } from "@/components/SpotifyCredentials";
import { Alert, Button, Card, Metric } from "@/components/ui";
import { API_BASE_URL } from "@/lib/api";
import { clearHistory } from "@/lib/history";

export default function SettingsPage() {
  const { settings, update } = useSettings();
  const { model, refresh, loading } = useModel();

  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <SpotifyCredentialsPanel
          creds={{ clientId: settings.clientId, clientSecret: settings.clientSecret }}
          onChange={(next) =>
            update({ clientId: next.clientId, clientSecret: next.clientSecret })
          }
        />
      </Card>

      <Card className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Active model
        </h2>
        {model?.exists ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Metric label="Model" value={model.model_name ?? "—"} />
            <Metric
              label="Macro F1"
              value={model.f1_macro !== null ? model.f1_macro.toFixed(4) : "—"}
            />
            <Metric label="Features" value={model.feature_columns.length} />
            <Metric
              label="Trained on"
              value={model.trained_on === "local_audio" ? "Local audio" : "Project dataset"}
              hint={
                model.trained_on === "local_audio"
                  ? `${model.n_train_songs ?? "?"} songs`
                  : undefined
              }
            />
          </div>
        ) : (
          <Alert kind="info">No model is currently loaded.</Alert>
        )}
        <Button variant="ghost" onClick={() => void refresh()} disabled={loading}>
          {loading ? "Refreshing…" : "Reload model from API"}
        </Button>
      </Card>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          API connection
        </h2>
        <div className="rounded-lg border border-edge bg-canvas px-3 py-2 font-mono text-sm">
          {API_BASE_URL}
        </div>
        <p className="text-xs text-muted">
          Set at build time via <code>NEXT_PUBLIC_API_BASE_URL</code>. Copy{" "}
          <code>frontend/.env.local.example</code> to <code>.env.local</code> to change it,
          then restart the dev server.
        </p>
      </Card>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Stored data
        </h2>
        <p className="text-xs text-muted">
          Prediction history is kept in this browser only. Spotify credentials live in
          session storage and are cleared when the browser closes.
        </p>
        <Button variant="ghost" onClick={clearHistory}>
          Clear prediction history
        </Button>
      </Card>
    </div>
  );
}
