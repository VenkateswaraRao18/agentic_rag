"""
Run the API with:  uvicorn run_api:app --reload --host 127.0.0.1 --port 8000
(from this directory), or:  python run_api.py

This file lives at the repo root and forces that root onto sys.path *before* importing
`app`, so Python does not pick up some other `app` package from PYTHONPATH or another
folder. A correct GET /health response includes code_revision and app_main_path.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_root_s = str(_REPO_ROOT)
if _root_s in sys.path:
    sys.path.remove(_root_s)
sys.path.insert(0, _root_s)

from app.main import app  # noqa: E402

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001, reload=False)
