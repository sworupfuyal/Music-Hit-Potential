"use client";

/**
 * Spotify client-credentials form, rendered on the Settings page. Values are held
 * by the settings context (session storage) and posted to the backend per request —
 * nothing is written to disk server-side.
 */

import type { SpotifyCreds } from "@/lib/types";

export function SpotifyCredentialsPanel({
  creds,
  onChange,
}: {
  creds: SpotifyCreds;
  onChange: (next: SpotifyCreds) => void;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
        Spotify API
      </h3>
      <label className="block space-y-1">
        <span className="text-xs text-muted">Client ID</span>
        <input
          type="text"
          value={creds.clientId}
          onChange={(event) => onChange({ ...creds, clientId: event.target.value })}
          className="w-full rounded-lg border border-edge bg-canvas px-3 py-2 text-sm outline-none focus:border-brand"
          autoComplete="off"
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs text-muted">Client Secret</span>
        <input
          type="password"
          value={creds.clientSecret}
          onChange={(event) => onChange({ ...creds, clientSecret: event.target.value })}
          className="w-full rounded-lg border border-edge bg-canvas px-3 py-2 text-sm outline-none focus:border-brand"
          autoComplete="off"
        />
      </label>
      <p className="text-xs text-muted">
        Kept in this browser session only. Needed for the Spotify tab.
      </p>
    </div>
  );
}
