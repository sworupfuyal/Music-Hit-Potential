import type { Metadata } from "next";

import { AudioPredictView } from "@/components/views/AudioPredictView";

export const metadata: Metadata = { title: "Local audio prediction — HitLab" };

export default function Page() {
  return <AudioPredictView />;
}
