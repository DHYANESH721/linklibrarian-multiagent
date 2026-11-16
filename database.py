"""Database bootstrap: a single SQLAlchemy instance shared app-wide."""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app: Flask) -> None:
    """Bind SQLAlchemy to the app and create tables if they do not exist."""
    db.init_app(app)

    # Imported for side effects: registers models on the metadata.
    from models import Link  # noqa: F401

    with app.app_context():
        db.create_all()
