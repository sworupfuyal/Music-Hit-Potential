"use client";

import { useModel } from "@/app/providers";
import { AudioTab } from "@/components/tabs/AudioTab";
import { Alert } from "@/components/ui";

export function AudioPredictView() {
  const { model, refresh } = useModel();
  if (!model?.exists) return <Alert kind="info">Loading model…</Alert>;
  return <AudioTab model={model} onModelChanged={refresh} />;
}
