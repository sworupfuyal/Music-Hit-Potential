"use client";

import { useModel } from "@/app/providers";
import { SingleTab } from "@/components/tabs/SingleTab";
import { Alert } from "@/components/ui";

export function SinglePredictView() {
  const { model } = useModel();
  if (!model?.exists) return <Alert kind="info">Loading model…</Alert>;
  // Keyed on the feature set so retraining rebuilds the generated input form.
  return <SingleTab key={model.feature_columns.join("|")} model={model} />;
}
