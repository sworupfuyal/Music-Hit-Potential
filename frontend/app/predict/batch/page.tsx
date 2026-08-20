import type { Metadata } from "next";

import { BatchTab } from "@/components/tabs/BatchTab";

export const metadata: Metadata = { title: "Batch prediction — HitLab" };

export default function Page() {
  return <BatchTab />;
}
