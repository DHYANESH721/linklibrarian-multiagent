"""HTTP layer: page routes and the JSON API. Thin by design."""

import logging

from flask import Blueprint, render_template, request

from config import Config
from agents import AgentError
from services import link_service
from services.link_service import DuplicateLinkError
from utils.helpers import fail, ok
from utils.validators import ValidationError

logger = logging.getLogger(__name__)

pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__, url_prefix="/api")


# ====================================================================== #
# Pages
# ====================================================================== #
@pages.route("/")
def home():
    """Library view with search, category, and tag filters applied server-side."""
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    tag = request.args.get("tag", "").strip()
    sort = request.args.get("sort", "newest").strip()

    links = link_service.list_links(search=search, category=category, tag=tag, sort=sort)

    return render_template(
        "index.html",
        links=links,
        categories=link_service.all_categories(),
        tags=link_service.all_tags(),
        stats=link_service.library_stats(),
        filters={"q": search, "category": category, "tag": tag, "sort": sort},
        ai_enabled=Config.ai_enabled(),
    )


@pages.route("/link/<int:link_id>")
def detail(link_id: int):
    """Full card view for one link."""
    try:
        link = link_service.get_link(link_id)
    except ValidationError:
        return render_template("404.html"), 404
    return render_template("detail.html", link=link)


# ====================================================================== #
# JSON API
# ====================================================================== #
@api.post("/links")
def create_link():
    """Save a URL. The Librarian Agent runs Scout → Reader → Summariser →
    Tagger → Quality Checker, then stores the card."""
    payload = request.get_json(silent=True) or request.form
    try:
        link, ai_generated, trace = link_service.create_link(payload.get("url", ""))
    except DuplicateLinkError as exc:
        return fail(str(exc), 409, link=exc.link.to_dict())
    except ValidationError as exc:
        return fail(str(exc), 400)
    except AgentError as exc:
        return fail(str(exc), 422, agent=exc.agent)
    except Exception:  # pragma: no cover - unexpected
        logger.exception("Unhandled error while saving link")
        return fail("Something went wrong while saving that link.", 500)

    return ok({"link": link.to_dict(), "ai_generated": ai_generated, "agents": trace}, 201)


@api.get("/links")
def list_links():
    """List links with optional q / category / tag / sort parameters."""
    links = link_service.list_links(
        search=request.args.get("q", ""),
        category=request.args.get("category", ""),
        tag=request.args.get("tag", ""),
        sort=request.args.get("sort", "newest"),
    )
    return ok({"links": [link.to_dict() for link in links], "count": len(links)})


@api.get("/links/<int:link_id>")
def get_link(link_id: int):
    """Fetch a single link."""
    try:
        return ok({"link": link_service.get_link(link_id).to_dict()})
    except ValidationError as exc:
        return fail(str(exc), 404)


@api.put("/links/<int:link_id>")
def update_link(link_id: int):
    """Edit title, summary, tags, category, or URL."""
    payload = request.get_json(silent=True) or request.form
    try:
        link = link_service.update_link(link_id, dict(payload))
    except DuplicateLinkError as exc:
        return fail(str(exc), 409)
    except ValidationError as exc:
        return fail(str(exc), 400)
    return ok({"link": link.to_dict()})


@api.delete("/links/<int:link_id>")
def delete_link(link_id: int):
    """Remove a link."""
    try:
        link_service.delete_link(link_id)
    except ValidationError as exc:
        return fail(str(exc), 404)
    return ok({"deleted": link_id})


@api.post("/links/<int:link_id>/refresh")
def refresh_link(link_id: int):
    """Ask the agent team to re-read an existing link."""
    try:
        link, trace = link_service.refresh_link(link_id)
    except ValidationError as exc:
        return fail(str(exc), 404)
    except AgentError as exc:
        return fail(str(exc), 422, agent=exc.agent)
    return ok({"link": link.to_dict(), "agents": trace})


@api.get("/categories")
def categories():
    """All categories in use."""
    return ok({"categories": link_service.all_categories()})


@api.get("/tags")
def tags():
    """All tags with usage counts."""
    return ok({"tags": link_service.all_tags()})


@api.get("/health")
def health():
    """Liveness probe; also reports whether the AI key is configured."""
    return ok({
        "status": "ok",
        "ai_enabled": Config.ai_enabled(),
        "model": Config.AI_MODEL,
        "agents": [{"name": a.name, "job": a.role} for a in link_service.librarian.team],
    })
