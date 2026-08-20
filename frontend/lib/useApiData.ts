"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "./api";

export interface AsyncData<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Fetch-on-mount helper for the analytics panels. `deps` should list whatever the
 * fetcher closes over (filter values), mirroring useEffect semantics.
 *
 * Previous data is kept while a refetch is in flight so filter changes do not blank
 * the panel out and shift the layout.
 */
export function useApiData<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  // The fetcher is recreated on every render by design; deps drive re-running.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fetcher, deps);

  useEffect(() => {
    let active = true;
    setLoading(true);
    run()
      .then((result) => {
        if (!active) return;
        setData(result);
        setError(null);
      })
      .catch((exc: unknown) => {
        if (!active) return;
        setError(exc instanceof ApiError ? exc.message : String(exc));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [run, nonce]);

  return { data, error, loading, reload: () => setNonce((n) => n + 1) };
}
