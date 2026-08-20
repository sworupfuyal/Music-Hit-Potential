"use client";

/**
 * Cross-route state. Model metadata is fetched once here rather than per page —
 * every route needs it, and it is what the input forms and chart ranges are built
 * from. Settings live alongside it so the Spotify tab and Settings page share one
 * source of truth.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api } from "@/lib/api";
import type { ModelResponse } from "@/lib/types";

// --- Model ----------------------------------------------------------------

interface ModelState {
  model: ModelResponse | null;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const ModelContext = createContext<ModelState | null>(null);

export function useModel(): ModelState {
  const context = useContext(ModelContext);
  if (!context) throw new Error("useModel must be used inside <Providers>");
  return context;
}

// --- Settings -------------------------------------------------------------

export interface Settings {
  clientId: string;
  clientSecret: string;
  threshold: number;
}

interface SettingsState {
  settings: Settings;
  update: (patch: Partial<Settings>) => void;
}

const DEFAULT_SETTINGS: Settings = { clientId: "", clientSecret: "", threshold: 0.5 };
// Credentials stay in sessionStorage (cleared when the browser closes); the rest is
// a durable preference.
const CREDS_KEY = "music-hit-spotify-credentials";
const PREFS_KEY = "music-hit-preferences";

const SettingsContext = createContext<SettingsState | null>(null);

export function useSettings(): SettingsState {
  const context = useContext(SettingsContext);
  if (!context) throw new Error("useSettings must be used inside <Providers>");
  return context;
}

export function Providers({ children }: { children: ReactNode }) {
  const [model, setModel] = useState<ModelResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      setModel(await api.getModel());
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    try {
      const creds = sessionStorage.getItem(CREDS_KEY);
      const prefs = localStorage.getItem(PREFS_KEY);
      setSettings((prev) => ({
        ...prev,
        ...(creds ? (JSON.parse(creds) as Partial<Settings>) : {}),
        ...(prefs ? (JSON.parse(prefs) as Partial<Settings>) : {}),
      }));
    } catch {
      /* ignore malformed storage */
    }
  }, []);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      try {
        sessionStorage.setItem(
          CREDS_KEY,
          JSON.stringify({ clientId: next.clientId, clientSecret: next.clientSecret }),
        );
        localStorage.setItem(PREFS_KEY, JSON.stringify({ threshold: next.threshold }));
      } catch {
        /* storage unavailable - keep in-memory only */
      }
      return next;
    });
  }, []);

  const modelValue = useMemo(
    () => ({ model, error, loading, refresh }),
    [model, error, loading, refresh],
  );
  const settingsValue = useMemo(() => ({ settings, update }), [settings, update]);

  return (
    <ModelContext.Provider value={modelValue}>
      <SettingsContext.Provider value={settingsValue}>{children}</SettingsContext.Provider>
    </ModelContext.Provider>
  );
}
