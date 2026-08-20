"use client";

/** Small presentational primitives shared across the app. */

import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-edge bg-surface p-5 shadow-sm shadow-black/[0.03] ${className}`}
    >
      {children}
    </div>
  );
}

export function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-edge bg-surface px-4 py-3 shadow-sm shadow-black/[0.03]">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted">{hint}</div> : null}
    </div>
  );
}

type ButtonProps = {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost";
  type?: "button" | "submit";
  className?: string;
};

export function Button({
  children,
  onClick,
  disabled = false,
  variant = "primary",
  type = "button",
  className = "",
}: ButtonProps) {
  // Pill shape throughout — the transport-control look of a player.
  const styles =
    variant === "primary"
      ? "bg-brand text-white shadow-sm hover:bg-brand-strong"
      : "border border-edge bg-surface text-ink hover:border-edge-strong hover:bg-elevated";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-full px-5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export function Alert({
  kind,
  children,
}: {
  kind: "error" | "warning" | "info" | "success";
  children: ReactNode;
}) {
  const palette: Record<string, string> = {
    error: "border-danger/30 bg-danger-tint text-danger",
    warning: "border-amber/30 bg-amber-tint text-amber",
    info: "border-neon/30 bg-neon/5 text-neon",
    success: "border-brand/30 bg-brand-tint text-brand-strong",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${palette[kind]}`}>{children}</div>
  );
}

export function ProgressBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-edge">
      <div
        className="h-full rounded-full bg-brand transition-[width] duration-300"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-lg font-semibold">{children}</h2>;
}

export function Expander({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-2xl border border-edge bg-surface px-5 py-3 shadow-sm shadow-black/[0.03]"
    >
      <summary className="cursor-pointer list-none text-sm font-semibold text-ink marker:content-none">
        <span className="mr-2 inline-block transition group-open:rotate-90">▶</span>
        {title}
      </summary>
      <div className="pt-4">{children}</div>
    </details>
  );
}
