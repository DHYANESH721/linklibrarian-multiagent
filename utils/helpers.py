"""Small shared helpers used across the app."""

import logging
from typing import Any

from flask import jsonify


def configure_logging(level: int = logging.INFO) -> None:
    """Set up a single readable log format for the whole process."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def ok(payload: Any = None, status: int = 200):
    """Success envelope for the JSON API."""
    return jsonify({"success": True, "data": payload}), status


def fail(message: str, status: int = 400, **extra):
    """Error envelope for the JSON API."""
    body = {"success": False, "error": message}
    body.update(extra)
    return jsonify(body), status


def truncate(text: str, limit: int) -> str:
    """Hard-truncate text on a word boundary where possible."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip() + "…"
