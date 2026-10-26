"""NumberShield FastAPI Main Application Entrypoint."""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.core.redactor import setup_secure_logging
from backend.app.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize secure logging and database tables on startup
    setup_secure_logging(settings.log_level)
    init_db(settings.db_path)
    yield


app = FastAPI(
    title="NumberShield API",
    version=settings.version,
    description="A Free, Open-Source Phone-Number Privacy & Spam Reduction Platform",
    lifespan=lifespan,
)

# Configure CORS strictly for local development and execution
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": settings.version,
        "app_name": settings.app_name,
        "database": str(settings.db_path),
        "zero_cost_mode": True,
    }


# Mount built frontend files if distribution directory exists
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
