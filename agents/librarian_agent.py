"""librarian_agent.py — LIBRARIAN AGENT (the manager)

Job: run the whole team. The Librarian does not scrape or summarise anything
itself — it hands work to the right agent, collects the results, decides
what happens next, and finally saves the finished card in the database.

    1. checks the URL is valid and not already in the library
    2. Scout Agent        → fetch the page (readable / blocked / retry)
    3. Reader Agent       → extract title + clean text
    4. Summariser Agent   → write the summary
    5. Tagger Agent       → choose tags + category
    6. Quality Checker    → approve, or reject with feedback
         ↳ rejected? send the work BACK to the Summariser / Tagger to redo
           (at most MAX_REDOS times), then check again
    7. save the card in the database

Every step is written to task["trace"], so the terminal (and the API
response) shows exactly which agent did what.
"""

import time

from agents.base_agent import BaseAgent
from agents.quality_agent import QualityCheckerAgent
from agents.reader_agent import ReaderAgent
from agents.scout_agent import ScoutAgent
from agents.summariser_agent import SummariserAgent
from agents.tagger_agent import TaggerAgent
from database import db
from models import Link
from utils.validators import ValidationError, clean_text, normalize_url

MAX_REDOS = 2      # how many times the Quality Checker may send work back


class DuplicateLinkError(ValidationError):
    """The URL is already in the library."""

    def __init__(self, link: Link):
        super().__init__("That link is already in your library.")
        self.link = link


class LibrarianAgent(BaseAgent):
    name = "Librarian Agent"
    role = "manager: gives work to the other agents, collects results, saves the card"

    def __init__(self):
        super().__init__()
        # The team this manager coordinates
        self.scout = ScoutAgent()
        self.reader = ReaderAgent()
        self.summariser = SummariserAgent()
        self.tagger = TaggerAgent()
        self.quality = QualityCheckerAgent()

    @property
    def team(self) -> list[BaseAgent]:
        return [self, self.scout, self.reader, self.summariser, self.tagger, self.quality]

    # ================================================================== #
    # Public jobs (called by services/link_service.py)
    # ================================================================== #
    def catalogue(self, raw_url: str) -> tuple[Link, bool, list]:
        """Save a NEW link. Returns (link, ai_generated, trace)."""
        started = time.perf_counter()
        url = normalize_url(raw_url)

        existing = Link.query.filter_by(url=url).first()
        if existing:
            self.say(f"already in the library: {url}")
            raise DuplicateLinkError(existing)

        self.say(f"new job received: {url}")
        task = self.process(url)

        link = Link(
            url=url,
            title=clean_text(task["title"], 500) or "Untitled page",
            summary=clean_text(task["summary"], 2000),
            tags=Link.normalize_tags(task["tags"]),
            category=clean_text(task["category"], 120) or "Other",
            favicon=task.get("favicon"),
        )
        db.session.add(link)
        db.session.commit()

        self.say(f"card #{link.id} saved ✓ — filed under {link.category}")
        self.record(task, f"saved card #{link.id}", started)
        return link, self._ai_used(task), task["trace"]

    def refresh(self, link: Link) -> tuple[Link, list]:
        """Re-read an EXISTING link with the full team and update its card."""
        started = time.perf_counter()
        self.say(f"refresh job received for card #{link.id}: {link.url}")
        task = self.process(link.url)

        link.title = clean_text(task["title"], 500) or link.title
        link.summary = clean_text(task["summary"], 2000)
        link.tags = Link.normalize_tags(task["tags"])
        link.category = clean_text(task["category"], 120) or link.category
        link.favicon = task.get("favicon") or link.favicon
        db.session.commit()

        self.say(f"card #{link.id} updated ✓")
        self.record(task, f"updated card #{link.id}", started)
        return link, task["trace"]

    # ================================================================== #
    # The coordination logic
    # ================================================================== #
    def process(self, url: str) -> dict:
        """Pass one shared task through the team and return the finished task."""
        task = {"url": url, "trace": [], "redos": 0,
                "existing_categories": self.existing_categories()}

        self.scout.run(task)          # may raise ScrapeError (blocked / unreachable)
        self.reader.run(task)         # may raise ScrapeError (nothing readable)
        self.summariser.run(task)
        self.tagger.run(task)

        for round_no in range(MAX_REDOS + 1):
            self.quality.run(task)
            if task["approved"]:
                break

            feedback = task["quality_feedback"]
            if round_no == MAX_REDOS:
                self.say(f"redo limit ({MAX_REDOS}) reached — keeping the best version")
                break
            if not self._ai_used(task):
                self.say("AI is offline, a redo would give the same result — keeping it")
                break

            task["redos"] += 1
            if "summary" in feedback:
                self.say(f"sending summary BACK to {self.summariser.name} (redo {task['redos']})")
                self.summariser.run(task)
            if "tags" in feedback:
                self.say(f"sending tags BACK to {self.tagger.name} (redo {task['redos']})")
                self.tagger.run(task)

        return task

    @staticmethod
    def existing_categories() -> list[str]:
        """Categories already in the library, so the Tagger can reuse them."""
        rows = db.session.query(Link.category).distinct().all()
        return sorted({r[0] for r in rows if r[0]})

    @staticmethod
    def _ai_used(task: dict) -> bool:
        return bool(task.get("ai_summary") and task.get("ai_tags"))
