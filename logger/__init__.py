"""
Logger – Goal & Habit Tracker Blueprint
========================================

Drop-in Flask Blueprint for tracking goals/habits with visual progress rings.

Usage (standalone):
    python run.py

Usage (integrate into your portfolio):
    from logger import init_app as init_logger, create_blueprint

    # after configuring your Flask app and db URI:
    init_logger(app)
    app.register_blueprint(create_blueprint(), url_prefix="/logger")
"""

import os

from flask import Blueprint, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

_LOGGER_DIR = os.path.abspath(os.path.dirname(__file__))


def init_app(app):
    """Initialise Logger on a Flask app.  Call this BEFORE register_blueprint."""
    # Provide a default DB URI if the host app hasn't set one
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"sqlite:///{os.path.join(_LOGGER_DIR, 'logger.db')}"
        )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = "dev-key-change-in-production"

    db.init_app(app)

    # Only set up LoginManager if the host app doesn't already have one
    if not hasattr(app, "login_manager"):
        login_manager.init_app(app)

    _lm = app.login_manager
    # Disable the default login_view ("login") so Flask-Login never
    # auto-redirects non-logger routes to a login page.
    _lm.login_view = None

    from .models import User

    @_lm.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @_lm.unauthorized_handler
    def handle_unauthorized():
        """Only redirect to logger login for logger-blueprint requests."""
        if request.blueprint == "logger":
            return redirect(url_for("logger.login", next=request.url))
        # Non-logger routes: just go home, never show a login page.
        return redirect(url_for("home"))

    with app.app_context():
        from . import models  # noqa – ensure tables are registered
        db.create_all()


def create_blueprint():
    """Return a configured Blueprint ready to be registered on an app."""
    bp = Blueprint(
        "logger",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/logger/static",
    )

    from .routes import register_routes
    register_routes(bp)

    return bp
