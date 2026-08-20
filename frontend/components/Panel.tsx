"use client";

/**
 * Chart panel wrapper: card chrome, loading/error states, and an optional table
 * view. Every continuous-scale chart ships a table twin so no value is reachable
 * only through color or a tooltip.
 */

import { useState, type ReactNode } from "react";

import type { AsyncData } from "@/lib/useApiData";

import { Alert, Card } from "./ui";

export function Panel<T>({
  state,
  children,
  table,
  height = 380,
  className = "",
}: {
  state: AsyncData<T>;
  children: (data: T) => ReactNode;
  table?: (data: T) => ReactNode;
  height?: number;
  className?: string;
}) {
  const [showTable, setShowTable] = useState(false);

  return (
    <Card className={className}>
      {state.error ? (
        <Alert kind="error">{state.error}</Alert>
      ) : state.data === null ? (
        <div className="animate-pulse rounded-lg bg-canvas" style={{ height }} />
      ) : (
        <>
          {table ? (
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={() => setShowTable((v) => !v)}
                className="rounded-full border border-edge px-3 py-1 text-xs font-medium text-muted transition hover:border-brand/50 hover:bg-brand-tint hover:text-brand-strong"
                aria-pressed={showTable}
              >
                {showTable ? "Show chart" : "Show table"}
              </button>
            </div>
          ) : null}

          {/* Hold the previous render at reduced opacity during a refetch. */}
          <div className={state.loading ? "opacity-60 transition-opacity" : ""}>
            {showTable && table ? (
              <div className="max-h-[420px] overflow-auto">{table(state.data)}</div>
            ) : (
              children(state.data)
            )}
          </div>
        </>
      )}
    </Card>
  );
}

/** Compact table used by the panel table views. */
export function DataTable({
  columns,
  rows,
  align = {},
}: {
  columns: string[];
  rows: (string | number | null)[][];
  align?: Record<number, "left" | "right">;
}) {
  return (
    <table className="min-w-full text-left text-xs">
      <thead className="sticky top-0 bg-elevated text-muted">
        <tr>
          {columns.map((col, i) => (
            <th
              key={col}
              className={`whitespace-nowrap px-3 py-2 font-medium ${
                align[i] === "right" ? "text-right" : ""
              }`}
            >
              {col}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, r) => (
          <tr key={r} className="border-t border-edge/60">
            {row.map((cell, c) => (
              <td
                key={c}
                className={`whitespace-nowrap px-3 py-1.5 tabular-nums ${
                  align[c] === "right" ? "text-right" : ""
                }`}
              >
                {cell === null ? "—" : cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** One-line control row that scopes every chart below it. */
export function FilterRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-edge bg-surface px-4 py-3 shadow-sm shadow-black/[0.03]">
      {children}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      {children}
    </label>
  );
}

export const selectClass =
  "rounded-lg border border-edge bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-brand";
