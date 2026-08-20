import type { Metadata } from "next";

import { SpotifyPredictView } from "@/components/views/SpotifyPredictView";

export const metadata: Metadata = { title: "Spotify track prediction — HitLab" };

export default function Page() {
  return <SpotifyPredictView />;
}
