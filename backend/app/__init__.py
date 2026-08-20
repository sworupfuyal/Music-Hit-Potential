"""FastAPI backend for the Music Hit Potential app.

The project root is added to sys.path so the shared `src` package (feature
extraction, preprocessing, models) imports cleanly no matter where uvicorn is
launched from.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
