"""UnityCommunityNftBot — Flask backend entry point."""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from backend.api.admin import admin_bp
from backend.api.mini_app import mini_app_bp
from backend.db.models import Base
from backend.db.session import engine

load_dotenv()

app = Flask(__name__)

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
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "UnityCommunityNftBot API"})


def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready.")


def main() -> None:
    """Run the Flask development server."""
    init_db()
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=8000, debug=debug)


if __name__ == "__main__":
    main()
