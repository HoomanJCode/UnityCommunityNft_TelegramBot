"""Database engine + session factory.

The whole backend shares one SQLAlchemy `engine` (SQLite by default) and one
`SessionLocal` factory. Every request handler / worker task opens its own
short-lived session and closes it when done — sessions are never shared.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load .env so DATABASE_URL (and DEBUG) are available at import time.
load_dotenv()

# Default to a local SQLite file; swap in a Postgres URL later if needed.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

engine = create_engine(
    DATABASE_URL,
    # Echo SQL to the console when DEBUG=true — handy in dev, noisy in prod.
    echo=os.getenv("DEBUG", "false").lower() == "true",
    # SQLite is strict about thread access. Flask (web thread) and the mint
    # worker (asyncio task) touch the DB from different threads, so allow it.
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Each call to SessionLocal() returns a fresh session with autocommit off;
# callers must explicitly commit (or roll back) and close.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield a session for one request, guaranteeing it is closed after.

    Implemented as a generator so it can be wired in as a FastAPI dependency
    if the backend ever migrates away from Flask.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
