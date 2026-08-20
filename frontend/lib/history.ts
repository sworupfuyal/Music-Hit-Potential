/**
 * Session prediction log, persisted to localStorage.
 *
 * Every prediction the app makes is appended here so the History page can show a
 * trend and export it. A custom event notifies listeners mounted on the same page
 * (localStorage's own `storage` event only fires for *other* tabs).
 */

export interface HistoryEntry {
  id: string;
  timestamp: number;
  mode: "Single" | "Spotify" | "Local audio" | "Batch";
  score: number;
  verdict: string;
  detail: string;
}

const STORAGE_KEY = "music-hit-prediction-history";
const CHANGE_EVENT = "music-hit-history-change";
const MAX_ENTRIES = 200;

export function readHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function addHistoryEntry(entry: Omit<HistoryEntry, "id" | "timestamp">): void {
  if (typeof window === "undefined") return;
  const next: HistoryEntry = {
    ...entry,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: Date.now(),
  };
  const all = [...readHistory(), next].slice(-MAX_ENTRIES);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function clearHistory(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function onHistoryChange(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(CHANGE_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(CHANGE_EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}

export function historyToCsv(entries: HistoryEntry[]): string {
  const header = "timestamp,mode,hit_potential,verdict,detail";
  const rows = entries.map((e) =>
    [
      new Date(e.timestamp).toISOString(),
      e.mode,
      e.score.toFixed(6),
      e.verdict,
      `"${e.detail.replace(/"/g, '""')}"`,
    ].join(","),
  );
  return [header, ...rows].join("\n");
}
