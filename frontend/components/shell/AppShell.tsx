"use client";

/**
 * Persistent chrome: a fixed sidebar on large screens, a slide-over on small ones.
 * The no-model training gate lives here so it blocks every route rather than only
 * the dashboard.
 */

import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { useModel } from "@/app/providers";
import { DatasetTraining } from "@/components/DatasetTraining";
import { Alert } from "@/components/ui";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  const { model, loading, error, refresh } = useModel();
  const [navOpen, setNavOpen] = useState(false);
  const pathname = usePathname();

  // Close the slide-over whenever the route changes.
  useEffect(() => setNavOpen(false), [pathname]);

  const gated = !loading && !error && model?.exists === false;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-r border-edge bg-surface lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar />
        </div>
      </aside>

      {navOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-ink/40"
            onClick={() => setNavOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-64 border-r border-edge bg-surface">
            <Sidebar onNavigate={() => setNavOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenNav={() => setNavOpen(true)} />
        <main className="min-w-0 flex-1 px-4 py-6 lg:px-8">
          {error ? (
            <Alert kind="error">{error}</Alert>
          ) : gated ? (
            <div className="mx-auto max-w-2xl">
              <DatasetTraining
                onModelChanged={refresh}
                notice={model && !model.exists ? model.error : null}
              />
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
}
