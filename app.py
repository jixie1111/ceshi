from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.backend.app.main import app


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "space_static"

if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = STATIC_DIR / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def missing_static():
        return PlainTextResponse("Frontend build is missing. Run npm --prefix src/frontend run build.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or os.environ.get("GRADIO_SERVER_PORT") or "7860")
    uvicorn.run(app, host="0.0.0.0", port=port)
