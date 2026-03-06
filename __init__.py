import os
from datetime import datetime

from flask import Flask

from .config import SECRET_KEY, DATA_DIR, SCREENSHOTS_DIR
from .models import get_db, init_db


def create_app():
    app = Flask(__name__,
                template_folder="templates",
                static_folder="static")
    app.secret_key = SECRET_KEY

    # Ensure dirs exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    # Initialize database
    init_db()

    # Jinja filters
    @app.template_filter("format_date")
    def format_date(value):
        """'2026-03-07' → 'Sat, Mar 7'; legacy day names pass through capitalized."""
        if isinstance(value, str) and len(value) == 10:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.strftime("%a, %b ") + str(dt.day)
            except ValueError:
                pass
        return value.capitalize() if isinstance(value, str) else value

    # Per-request DB connection
    @app.before_request
    def _open_db():
        from flask import g
        g.db = get_db()

    @app.teardown_appcontext
    def _close_db(exc):
        from flask import g
        db = g.pop("db", None)
        if db:
            db.close()

    # Serve screenshot images
    @app.route("/screenshots/<path:filename>")
    def serve_screenshot(filename):
        from flask import send_from_directory
        return send_from_directory(SCREENSHOTS_DIR, filename)

    # Register blueprints
    from .routes import register_blueprints
    register_blueprints(app)

    return app
