"""UnityCommunityNftBot — FastAPI backend entry point."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.models import Base
from backend.db.session import engine

load_dotenv()

app = FastAPI(
    title="UnityCommunityNftBot API",
    version="0.1.0",
)

# CORS — allow Mini App and Admin frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("MINI_APP_URL", "http://localhost:5173"),
        os.getenv("ADMIN_WEB_URL", "http://localhost:5174"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create tables on startup (no-op if they already exist)."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready.")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "UnityCommunityNftBot API"}
