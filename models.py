"""ORM models for LinkLibrarian."""

from datetime import datetime, timezone

from database import db


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp (naive-stored for SQLite friendliness)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Link(db.Model):
    """A single saved bookmark plus its AI-generated metadata."""

    __tablename__ = "links"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(2048), nullable=False, unique=True, index=True)
    title = db.Column(db.String(512), nullable=False, default="Untitled")
    summary = db.Column(db.Text, nullable=False, default="")
    # Tags are stored as a lowercase comma-separated string: "python,flask,api".
    tags = db.Column(db.String(512), nullable=False, default="")
    category = db.Column(db.String(120), nullable=False, default="Uncategorized", index=True)
    favicon = db.Column(db.String(2048), nullable=True)
    date_added = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # ------------------------------------------------------------------ #
    # Tag helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_tags(tags) -> str:
        """Turn a list or comma string into a clean, de-duplicated CSV string."""
        if not tags:
            return ""
        if isinstance(tags, str):
            raw = tags.split(",")
        else:
            raw = list(tags)

        seen, cleaned = set(), []
        for tag in raw:
            slug = str(tag).strip().lower().replace(" ", "-")
            slug = "".join(ch for ch in slug if ch.isalnum() or ch in "-_+.")
            if slug and slug not in seen:
                seen.add(slug)
                cleaned.append(slug)
        return ",".join(cleaned[:10])

    @property
    def tag_list(self) -> list[str]:
        """Tags as a Python list."""
        return [t for t in self.tags.split(",") if t]

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        """JSON-safe representation used by the API and the front end."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "tags": self.tag_list,
            "category": self.category,
            "favicon": self.favicon,
            "date_added": self.date_added.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Link {self.id} {self.url[:48]}>"
