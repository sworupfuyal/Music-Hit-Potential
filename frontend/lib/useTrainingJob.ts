"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "./api";
import type { TrainingJob } from "./types";

/**
 * Starts a training run and polls its progress, replacing Streamlit's blocking
 * progress bar. `onFinished` fires once the run succeeds so the caller can
 * refresh the model metadata.
 */
export function useTrainingJob(onFinished: () => void) {
  const [job, setJob] = useState<TrainingJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finishedRef = useRef(onFinished);

  finishedRef.current = onFinished;

  const clearTimer = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };

  useEffect(() => clearTimer, []);

  const poll = useCallback((jobId: string) => {
    const tick = async () => {
      try {
        const next = await api.getJob(jobId);
        setJob(next);
        if (next.status === "running") {
          timer.current = setTimeout(tick, 700);
        } else if (next.status === "succeeded") {
          finishedRef.current();
        } else if (next.error) {
          setError(next.error);
        }
      } catch (exc) {
        setError(exc instanceof ApiError ? exc.message : String(exc));
      }
    };
    void tick();
  }, []);

  const start = useCallback(
    async (starter: () => Promise<{ job_id: string }>) => {
      clearTimer();
      setError(null);
      setJob(null);
      try {
        const { job_id } = await starter();
        poll(job_id);
      } catch (exc) {
        setError(exc instanceof ApiError ? exc.message : String(exc));
      }
    },
    [poll],
  );

  const running = job?.status === "running";
  const fraction = job && job.total > 0 ? job.done / job.total : running ? 0 : 1;

  return { job, error, running, fraction, start, reset: () => setJob(null) };
}
