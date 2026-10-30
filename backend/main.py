"""COD Compass - Backend Application Entrypoint.

FastAPI server exposing pre-shipment decision engine, WhatsApp simulator,
financial model reconciliation, and policy management.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.api.endpoints import router as api_router
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes the database and pre-warms models on startup."""
    print("Initializing COD Compass database and models...")
    init_db()
    yield
    print("COD Compass backend shutting down.")


app = FastAPI(
    title="COD Compass API",
    description="Pre-shipment decision engine balancing RTO losses against genuine customer conversion.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mount frontend production build if available
frontend_dist = os.path.abspath(os.path.join(current_dir, "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
