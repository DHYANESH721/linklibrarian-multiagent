"""reader_agent.py — READER AGENT

Job: take the raw HTML the Scout Agent brought back and turn it into clean,
readable information:

    title        → from og:title, <title>, or the first <h1>
    description  → from the meta description tags
    favicon      → the site's little icon
    text         → the main article text, with menus, ads and scripts removed
"""

import json
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from agents.base_agent import BaseAgent, ScrapeError
from config import Config
from utils.validators import clean_text

# Tags that never contain readable article text.
NOISE_TAGS = (
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "form", "iframe", "svg", "button", "figure",
)

# Where the main content usually lives, best guess first.
CONTENT_SELECTORS = (
    "article", "main", "[role=main]", "#content", ".post-content",
    ".entry-content", ".article-body", ".markdown-body",
)


class ReaderAgent(BaseAgent):
    name = "Reader Agent"
    role = "pulls out the title and main text and cleans it"

    def run(self, task: dict) -> dict:
        started = time.perf_counter()
        soup = BeautifulSoup(task["html"], "html.parser")
        page_url = task.get("final_url") or task["url"]

        hidden = self.extract_hidden_metadata(soup)     # research papers, articles
        task["title"] = hidden.get("title") or self.extract_title(soup)
        task["description"] = hidden.get("abstract") or self.extract_description(soup)
        if hidden:
            self.say(f"found hidden page metadata ({', '.join(sorted(hidden))})")
        task["favicon"] = self.extract_favicon(soup, page_url)
        task["text"] = self.extract_main_text(soup)
        task.pop("html", None)                      # raw HTML no longer needed

        if not task["text"] and not task["description"]:
            self.say("nothing readable — page is probably built entirely with JavaScript")
            self.record(task, "no readable text", started)
            raise ScrapeError(
                "No readable text found on that page. It may be rendered entirely by JavaScript.",
                self.name,
            )

        self.say(f'read "{task["title"][:60]}" — {len(task["text"]):,} characters of clean text')
        self.record(task, "title + main text extracted", started)
        return task

    # ------------------------------------------------------------------ #
    # Extraction skills
    # ------------------------------------------------------------------ #
    @staticmethod
    def extract_hidden_metadata(soup: BeautifulSoup) -> dict:
        """Find the real title / abstract that many sites hide in metadata.

        Research sites (IEEE Xplore, Springer, ScienceDirect, arXiv…) often load the
        visible page with JavaScript but still ship the paper's details as:
          • scholarly meta tags   citation_title / citation_abstract / dc.description
          • JSON-LD blocks        <script type="application/ld+json">
          • IEEE Xplore's         xplGlobal.document.metadata = {...}
        """
        found = {}

        def meta(*names):
            for name in names:
                tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", property=name)
                if tag and tag.get("content", "").strip():
                    return clean_text(tag["content"], 1500)
            return ""

        found["title"] = meta("citation_title", "dc.title", "DC.title", "parsely-title")
        found["abstract"] = meta("citation_abstract", "dc.description", "DC.description")

        for block in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(block.string or "")
            except (ValueError, TypeError):
                continue
            for item in data if isinstance(data, list) else [data]:
                if not isinstance(item, dict):
                    continue
                found["title"] = found["title"] or clean_text(item.get("headline") or item.get("name") or "", 300)
                found["abstract"] = found["abstract"] or clean_text(
                    item.get("abstract") or item.get("description") or "", 1500)

        for block in soup.find_all("script"):
            code = block.string or ""
            if "xplGlobal.document.metadata" not in code:
                continue
            for key in ("title", "abstract"):
                if not found[key]:
                    m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', code)
                    if m:
                        value = json.loads(f'"{m.group(1)}"')
                        found[key] = clean_text(re.sub(r"<[^>]+>", " ", value), 1500)

        return {k: v for k, v in found.items() if v}

    @staticmethod
    def extract_title(soup: BeautifulSoup) -> str:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return clean_text(og["content"], 300)
        if soup.title and soup.title.string:
            return clean_text(soup.title.string, 300)
        h1 = soup.find("h1")
        if h1:
            return clean_text(h1.get_text(), 300)
        return "Untitled page"

    @staticmethod
    def extract_description(soup: BeautifulSoup) -> str:
        for finder in (
            lambda: soup.find("meta", attrs={"name": "description"}),
            lambda: soup.find("meta", property="og:description"),
            lambda: soup.find("meta", attrs={"name": "twitter:description"}),
        ):
            tag = finder()
            if tag and tag.get("content"):
                return clean_text(tag["content"], 500)
        return ""

    @staticmethod
    def extract_favicon(soup: BeautifulSoup, url: str) -> str:
        for wanted in ("icon", "shortcut", "apple-touch-icon"):
            for tag in soup.find_all("link", href=True):
                rel = tag.get("rel") or []
                rel_text = " ".join(rel).lower() if isinstance(rel, list) else str(rel).lower()
                if wanted in rel_text:
                    return urljoin(url, tag["href"])
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"

    @staticmethod
    def extract_main_text(soup: BeautifulSoup) -> str:
        for tag in soup(NOISE_TAGS):
            tag.decompose()

        container = None
        for selector in CONTENT_SELECTORS:
            found = soup.select_one(selector)
            if found and len(found.get_text(strip=True)) > 200:
                container = found
                break
        container = container or soup.body or soup

        lines = [
            line.strip()
            for line in container.get_text(separator="\n").splitlines()
            if len(line.strip()) > 2
        ]
        return "\n".join(lines)[:Config.SCRAPER_MAX_CHARS]
