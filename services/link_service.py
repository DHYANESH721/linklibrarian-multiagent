"""Business logic for saving, querying, editing, and deleting links.

Routes stay thin: they parse requests and hand off to these functions.
Saving and refreshing a link is delegated to the multi-agent team, led by
the Librarian Agent (see the agents/ folder).
"""

import logging

from sqlalchemy import or_

from agents import DuplicateLinkError, LibrarianAgent
from database import db
from models import Link
from utils.validators import ValidationError, clean_text, normalize_url

logger = logging.getLogger(__name__)

# One manager agent, shared by every request. It owns the other five agents.
librarian = LibrarianAgent()


# ---------------------------------------------------------------------- #
# Create
# ---------------------------------------------------------------------- #
def create_link(raw_url: str) -> tuple[Link, bool, list]:
    """Hand a new URL to the Librarian Agent, who runs the whole agent team.

    Returns:
        (link, ai_generated, trace) — trace lists which agent did what.

    Raises:
        ValidationError:    bad URL.
        DuplicateLinkError: URL already saved.
        ScrapeError:        the Scout or Reader agent could not read the page.
    """
    return librarian.catalogue(raw_url)


# ---------------------------------------------------------------------- #
# Read
# ---------------------------------------------------------------------- #
def list_links(search: str = "", category: str = "", tag: str = "", sort: str = "newest"):
    """Return links matching the given search / filter / sort options."""
    query = Link.query

    if search:
        needle = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Link.title.ilike(needle),
                Link.summary.ilike(needle),
                Link.url.ilike(needle),
                Link.tags.ilike(needle),
            )
        )
    if category and category.lower() != "all":
        query = query.filter(Link.category == category)
    if tag:
        query = query.filter(Link.tags.ilike(f"%{tag.strip().lower()}%"))

    sorts = {
        "newest": Link.date_added.desc(),
        "oldest": Link.date_added.asc(),
        "title": Link.title.asc(),
        "updated": Link.updated_at.desc(),
    }
    return query.order_by(sorts.get(sort, Link.date_added.desc())).all()


def get_link(link_id: int) -> Link:
    """Fetch one link or raise ValidationError."""
    link = db.session.get(Link, link_id)
    if not link:
        raise ValidationError("That link no longer exists.")
    return link


def all_categories() -> list[str]:
    """Distinct categories currently in use, alphabetically."""
    rows = db.session.query(Link.category).distinct().all()
    return sorted({row[0] for row in rows if row[0]})


def all_tags() -> list[dict]:
    """Every tag with a usage count, most-used first."""
    counts: dict[str, int] = {}
    for (tags,) in db.session.query(Link.tags).all():
        for tag in (t for t in (tags or "").split(",") if t):
            counts[tag] = counts.get(tag, 0) + 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


# ---------------------------------------------------------------------- #
# Update / Delete
# ---------------------------------------------------------------------- #
def update_link(link_id: int, payload: dict) -> Link:
    """Apply user edits to a saved link.

    Raises:
        ValidationError: unknown link, bad URL, or duplicate URL.
    """
    link = get_link(link_id)

    if "url" in payload and payload["url"]:
        new_url = normalize_url(payload["url"])
        clash = Link.query.filter(Link.url == new_url, Link.id != link.id).first()
        if clash:
            raise DuplicateLinkError(clash)
        link.url = new_url

    if "title" in payload:
        link.title = clean_text(payload["title"], 500) or link.title
    if "summary" in payload:
        link.summary = clean_text(payload["summary"], 2000)
    if "category" in payload:
        link.category = clean_text(payload["category"], 120) or "Other"
    if "tags" in payload:
        link.tags = Link.normalize_tags(payload["tags"])

    db.session.commit()
    return link


def delete_link(link_id: int) -> None:
    """Remove a link permanently."""
    link = get_link(link_id)
    db.session.delete(link)
    db.session.commit()
    logger.info("Deleted link %s", link_id)


def refresh_link(link_id: int) -> tuple[Link, list]:
    """Ask the Librarian Agent to re-read an existing link, keeping its id."""
    return librarian.refresh(get_link(link_id))


def library_stats() -> dict:
    """Counts shown in the header."""
    return {
        "links": Link.query.count(),
        "categories": len(all_categories()),
        "tags": len(all_tags()),
    }
