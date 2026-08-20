"""In-memory job registry for long-running training runs.

Training used to block the Streamlit script while a progress bar ticked. Here it
runs on a background thread and the frontend polls GET /api/train/jobs/{id} for
the same (done, total, current) progress the callback reports.
"""

import threading
import uuid
from typing import Any, Callable

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()

# Finished jobs are kept so the UI can read the final state, but the registry is
# trimmed to avoid unbounded growth over a long-running server.
_MAX_JOBS = 20


def _trim_locked() -> None:
    if len(_jobs) <= _MAX_JOBS:
        return
    finished = [
        job_id for job_id, job in _jobs.items() if job["status"] in ("succeeded", "failed")
    ]
    for job_id in finished[: len(_jobs) - _MAX_JOBS]:
        _jobs.pop(job_id, None)


def create_job(kind: str) -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "kind": kind,
            "status": "running",
            "done": 0,
            "total": 0,
            "current": "",
            "message": "Starting…",
            "error": None,
            "result": None,
        }
        _trim_locked()
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.update(fields)


def run_in_background(
    job_id: str,
    work: Callable[[Callable[[int, int, str], None]], dict],
    describe: Callable[[int, int, str], str],
    summarize: Callable[[dict], dict],
) -> None:
    """Run `work` on a thread, forwarding its progress callback into the job state.

    `describe` turns (done, total, current) into the status line shown in the UI;
    `summarize` turns the resulting bundle into a JSON-safe result payload.
    """

    def progress(done: int, total: int, current: str) -> None:
        _update(
            job_id,
            done=done,
            total=total,
            current=current,
            message=describe(done, total, current),
        )

    def target() -> None:
        try:
            bundle = work(progress)
        except Exception as exc:  # surfaced to the UI verbatim, as Streamlit did
            _update(job_id, status="failed", error=str(exc), message="Training failed.")
            return
        _update(
            job_id,
            status="succeeded",
            message="Training complete.",
            result=summarize(bundle),
        )

    threading.Thread(target=target, name=f"train-{job_id}", daemon=True).start()
