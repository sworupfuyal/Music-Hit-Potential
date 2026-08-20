"use client";

import { useModel, useSettings } from "@/app/providers";
import { SpotifyTab } from "@/components/tabs/SpotifyTab";
import { Alert } from "@/components/ui";

export function SpotifyPredictView() {
  const { model } = useModel();
  const { settings } = useSettings();

  if (!model?.exists) return <Alert kind="info">Loading model…</Alert>;

  return (
    <SpotifyTab
      model={model}
      creds={{ clientId: settings.clientId, clientSecret: settings.clientSecret }}
    />
  );
}
