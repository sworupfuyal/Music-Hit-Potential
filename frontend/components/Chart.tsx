"use client";

import dynamic from "next/dynamic";

import type { Figure } from "@/lib/charts";

const Plot = dynamic(() => import("./PlotlyBase"), {
  ssr: false,
  loading: () => <div className="h-[320px] animate-pulse rounded-lg bg-surface" />,
});

/** Renders a figure produced by lib/charts.ts, responsive to its container. */
export function Chart({ figure, className = "" }: { figure: Figure; className?: string }) {
  return (
    <div className={`w-full ${className}`}>
      <Plot
        data={figure.data}
        layout={{ ...figure.layout, autosize: true }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%", height: `${figure.layout.height ?? 360}px` }}
        useResizeHandler
      />
    </div>
  );
}
