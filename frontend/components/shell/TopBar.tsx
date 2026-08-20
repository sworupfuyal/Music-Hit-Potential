"use client";

import { usePathname } from "next/navigation";

import { useModel } from "@/app/providers";

import { EqualizerBars } from "@/components/music";

import { NAV } from "./nav";

function titleFor(pathname: string): string {
  for (const section of NAV) {
    for (const item of section.items) {
      const match = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
      if (match) return item.label;
    }
  }
  return "Music Hit Potential";
}

export function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const pathname = usePathname();
  const { model, loading, error } = useModel();

  const trained = model?.exists === true;
  // The level meter doubles as the status light: it only "plays" when a model is
  // loaded and the API is answering.
  const meterClass = error ? "bg-danger" : trained ? "bg-brand" : "bg-amber";
  const statusText = error
    ? "API unreachable"
    : loading
      ? "Checking API"
      : trained
        ? "Model ready"
        : "No model trained";

  return (
    <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-edge bg-surface/90 px-4 py-3 backdrop-blur lg:px-8">
      <button
        type="button"
        onClick={onOpenNav}
        aria-label="Open navigation"
        className="rounded-full border border-edge px-3 py-1.5 text-sm lg:hidden"
      >
        ☰
      </button>

      <h1 className="text-base font-semibold">{titleFor(pathname)}</h1>

      <div className="ml-auto flex items-center gap-4 text-xs">
        {model?.exists ? (
          <div className="hidden items-center gap-3 sm:flex">
            <span className="rounded-full bg-brand-tint px-3 py-1 font-semibold text-brand-strong">
              {model.model_name}
            </span>
            <span className="text-muted">
              macro F1{" "}
              <span className="font-semibold tabular-nums text-ink">
                {model.f1_macro !== null ? model.f1_macro.toFixed(4) : "—"}
              </span>
            </span>
          </div>
        ) : null}
        <span className="flex items-center gap-2 text-muted">
          <EqualizerBars
            playing={trained && !loading && !error}
            barClassName={meterClass}
            className="h-3.5"
          />
          {statusText}
        </span>
      </div>
    </header>
  );
}
