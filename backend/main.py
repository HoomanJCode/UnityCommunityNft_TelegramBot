"""UnityCommunityNftBot — Flask backend entry point.

Brings up the HTTP API (admin + mini app blueprints) and ensures the database
schema exists before serving traffic.
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

# Blueprints hold the routes; registering them keeps this file small.
from backend.api.admin import admin_bp
from backend.api.mini_app import mini_app_bp
# Models only need importing so Base.metadata knows about all tables.
from backend.db.models import Base
from backend.db.session import engine

load_dotenv()

app = Flask(__name__)

# The Mini App and admin dashboard run on separate origins (Vite dev servers).
# CORS must allow them to call the API from the browser.
CORS(
    app,
    origins=[
        os.getenv("MINI_APP_URL", "http://localhost:5173"),
        os.getenv("ADMIN_WEB_URL", "http://localhost:5174"),
    ],
)

app.register_blueprint(admin_bp)
app.register_blueprint(mini_app_bp)


@app.route("/health")
def health_check():
    """Health check endpoint — used by deployments to probe liveness."""
    return jsonify({"status": "ok", "service": "UnityCommunityNftBot API"})


def init_db() -> None:
    """Create all database tables (SQLite dev schema bootstrap).

    Using create_all is enough for the demo; a real deployment would switch
    to Alembic migrations (alembic is already in requirements.txt).
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready.")


def main() -> None:
    """Run the Flask development server."""
    init_db()
    # DEBUG flips the auto-reloader and verbose SQL output (see db/session.py).
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug)


if __name__ == "__main__":
    main()
