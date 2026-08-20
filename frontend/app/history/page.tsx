"use client";

/** Session prediction log with a score trend and CSV export. */

import { useEffect, useMemo, useState } from "react";

import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/Panel";
import { Alert, Button, Card, Metric } from "@/components/ui";
import { historyTrend } from "@/lib/charts-analytics";
import {
  clearHistory,
  historyToCsv,
  onHistoryChange,
  readHistory,
  type HistoryEntry,
} from "@/lib/history";

export default function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);

  useEffect(() => {
    const load = () => setEntries(readHistory());
    load();
    return onHistoryChange(load);
  }, []);

  const stats = useMemo(() => {
    if (!entries || entries.length === 0) return null;
    const scores = entries.map((e) => e.score);
    return {
      count: entries.length,
      average: scores.reduce((a, b) => a + b, 0) / scores.length,
      best: Math.max(...scores),
      predictedHits: scores.filter((s) => s >= 0.5).length,
    };
  }, [entries]);

  const download = () => {
    if (!entries) return;
    const blob = new Blob([historyToCsv(entries)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "prediction_history.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  if (entries === null) {
    return <div className="h-40 animate-pulse rounded-xl bg-surface" />;
  }

  if (entries.length === 0) {
    return (
      <Alert kind="info">
        No predictions yet. Score a song from any of the Predict pages and it will be logged
        here.
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Predictions" value={stats!.count} />
        <Metric label="Average score" value={`${(stats!.average * 100).toFixed(1)}%`} />
        <Metric label="Best score" value={`${(stats!.best * 100).toFixed(1)}%`} />
        <Metric label="Above threshold" value={stats!.predictedHits} hint="Score ≥ 50%" />
      </section>

      <Card>
        <Chart
          figure={historyTrend(
            entries.map((e) => ({ timestamp: e.timestamp, score: e.score, mode: e.mode })),
          )}
        />
      </Card>

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">All predictions</h2>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={download}>
              Export CSV
            </Button>
            <Button variant="ghost" onClick={clearHistory}>
              Clear history
            </Button>
          </div>
        </div>
        <div className="max-h-[460px] overflow-auto">
          <DataTable
            columns={["When", "Mode", "Score", "Verdict", "Detail"]}
            align={{ 2: "right" }}
            rows={[...entries]
              .reverse()
              .map((entry) => [
                new Date(entry.timestamp).toLocaleString(),
                entry.mode,
                `${(entry.score * 100).toFixed(1)}%`,
                entry.verdict,
                entry.detail,
              ])}
          />
        </div>
      </Card>
    </div>
  );
}
