import type { Metadata } from "next";

import { SinglePredictView } from "@/components/views/SinglePredictView";

export const metadata: Metadata = { title: "Single song prediction — HitLab" };

export default function Page() {
  return <SinglePredictView />;
}
