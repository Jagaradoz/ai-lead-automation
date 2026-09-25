#!/usr/bin/env python3
"""
serve_api.py
FastAPI app for AI Lead Automation.
Mounts the lead and settings routers and serves the web app from web/ on GET /.
"""

import json
import os
import sys
from pathlib import Path

# Load .env if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from scripts.api.deps import get_settings_store
from scripts.api.leads import router as leads_router
from scripts.api.settings import router as settings_router
from scripts.llm.settings_store import SettingsStore
from scripts.paths import WEB_DIR

APP_VERSION = "2.0.0"
DATASET_PATH = ROOT_DIR / "evaluation" / "datasets" / "sample-leads.json"
MAX_BODY_BYTES = 1_000_000
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

app = FastAPI(
    title="AI Lead Automation",
    description="Lead intake, AI fact extraction with a configurable model, deterministic scoring and a lead inbox.",
    version=APP_VERSION,
)

_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
# Rejects requests whose Host header isn't ours (blocks DNS-rebinding pages from reaching a local server).
_allowed_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


def _is_cross_site_write(request: Request) -> bool:
    """
    Browsers send Sec-Fetch-Site and Origin on writes; other sites' pages must not be able
    to trigger body-less POSTs (which skip CORS preflight). Non-browser clients send neither.
    """
    if request.method in _SAFE_METHODS:
        return False
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        return True
    origin = request.headers.get("origin")
    if origin and origin != "null":
        own = f"{request.url.scheme}://{request.headers.get('host', '')}"
        return origin != own and origin not in _cors_origins
    return origin == "null"


@app.middleware("http")
async def guard_and_secure(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
    if _is_cross_site_write(request):
        return JSONResponse(status_code=403, content={"detail": "Cross-site requests are not allowed."})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if not request.url.path.startswith(_DOCS_PATHS):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


@app.get("/health")
def health(store: SettingsStore = Depends(get_settings_store)):
    settings = store.load()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "engine": settings.describe(),
        "ai_engine_mode": "model" if settings.is_configured else "rules",
        "settings_locked": bool(os.environ.get("ADMIN_TOKEN")),
        "system": "AI Lead Automation",
    }


@app.get("/api/samples")
def get_samples():
    """Sample leads for the 'Try a sample' menu."""
    if not DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found.")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


app.include_router(leads_router)
app.include_router(settings_router)

if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"[*] Starting AI Lead Automation on http://127.0.0.1:{port}")
    uvicorn.run("scripts.serve_api:app", host="127.0.0.1", port=port, reload=True)
