import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import artists, auth, discovery, research, venues

# Without a handler, app loggers below WARNING are silently dropped —
# uvicorn only configures its own loggers, not ours.
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="Gig Pipeline")

app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(artists.router)
app.include_router(discovery.router)
app.include_router(research.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Serve the built frontend (single-service deployment). In development the
# Vite dev server proxies /api instead, and dist/ may not exist.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and candidate.is_relative_to(FRONTEND_DIST)
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
