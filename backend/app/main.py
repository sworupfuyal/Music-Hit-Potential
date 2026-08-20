"""FastAPI application entrypoint.

Run from the project root:
    uvicorn backend.app.main:app --reload --port 8000
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bundle import bundle_exists
from .paths import DATA_PATH
from .routers import dataset, model, predict, reports, train

# Comma-separated list; defaults cover the Next.js dev server.
_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app = FastAPI(
    title="Music Hit Potential API",
    description="Hit-potential predictions from song features, Spotify tracks and raw audio.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(model.router)
app.include_router(predict.router)
app.include_router(train.router)
app.include_router(reports.router)
app.include_router(dataset.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {
        "status": "ok",
        "model_trained": bundle_exists(),
        "dataset_available": DATA_PATH.exists(),
    }
