from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.config import PROJECT_ROOT, get_settings


settings = get_settings()
settings.ensure_directories()

app = FastAPI(
    title="PayTracker API",
    version="1.0.0",
    description=(
        "Private local API for reviewing payslips, shifts, reconciliation and exports. "
        "PayTracker is a record-keeping tool, not legal, tax, payroll or financial advice."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def privacy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    return response


app.include_router(router)

frontend_dist = PROJECT_ROOT / "frontend" / "dist"
assets_dir = frontend_dist / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    index = frontend_dist / "index.html"
    if index.is_file():
        return FileResponse(
            index,
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
    return JSONResponse(
        {
            "message": "PayTracker API is running. Build the frontend with setup-paytracker.ps1.",
            "docs": "/api/docs",
        }
    )
