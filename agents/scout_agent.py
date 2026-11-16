"""scout_agent.py — SCOUT AGENT

Job: go to the web address and fetch the page.
Decides one of three things before anyone else does any work:

    ✓ READABLE  → the page came back as HTML, hand it to the Reader Agent
    ⛔ BLOCKED   → the site refuses automated readers, stop and explain why
    ↻ RETRY     → the site was slow or had a temporary error, try once more
"""

import time
from urllib.parse import urlparse

import requests

from agents.base_agent import BaseAgent, ScrapeError
from config import Config

# Sites known to block automated readers.
BLOCKED_DOMAINS = (
    "redbus.in", "amazon.in", "amazon.com", "flipkart.com",
    "swiggy.com", "zomato.com", "instagram.com", "facebook.com",
    "linkedin.com", "netflix.com", "hotstar.com", "myntra.com",
    "snapdeal.com", "meesho.com", "bigbasket.com", "blinkit.com",
)

BLOCKED_MESSAGE = (
    "⛔ This site blocks automated readers and cannot be saved. "
    "Sites like Amazon, Flipkart, RedBus, Swiggy, Zomato, Instagram, "
    "Facebook, LinkedIn, and Netflix intentionally prevent tools like "
    "LinkLibrarian from reading their pages. "
    "Try saving a news article, Wikipedia page, blog post, "
    "GitHub repository, or documentation page instead."
)

MAX_ATTEMPTS = 2          # first try + one retry
RETRY_WAIT_S = 1.0        # pause before retrying
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ScoutAgent(BaseAgent):
    name = "Scout Agent"
    role = "fetches the page and decides: readable, blocked, or retry"

    def run(self, task: dict) -> dict:
        started = time.perf_counter()
        url = task["url"]

        # DECISION 1: is this a site we already know blocks readers?
        if self.is_blocked_domain(url):
            self.say(f"BLOCKED — {urlparse(url).hostname} does not allow automated readers")
            self.record(task, "blocked (known site)", started)
            raise ScrapeError(BLOCKED_MESSAGE, self.name)

        # DECISION 2: fetch, retrying once on temporary problems
        last_problem = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.say(f"fetching {url} (attempt {attempt}/{MAX_ATTEMPTS})")
            try:
                response = requests.get(
                    url, headers=self._headers(), timeout=Config.SCRAPER_TIMEOUT,
                    allow_redirects=True,
                )
            except requests.exceptions.Timeout:
                last_problem = f"The site took longer than {Config.SCRAPER_TIMEOUT}s to respond."
            except requests.exceptions.SSLError:
                self.record(task, "refused: bad certificate", started)
                raise ScrapeError("The site has an invalid security certificate.", self.name) from None
            except requests.exceptions.ConnectionError:
                last_problem = "Could not reach that site. Check the address and try again."
            except requests.exceptions.RequestException as exc:
                last_problem = f"Request failed: {exc}"
            else:
                verdict = self.judge(response)
                if verdict == "readable":
                    task["html"] = response.text
                    task["final_url"] = response.url or url
                    self.say(f"READABLE — HTTP {response.status_code}, "
                             f"{len(response.text):,} characters of HTML")
                    self.record(task, f"page readable (attempt {attempt})", started)
                    return task
                if verdict == "retry":
                    last_problem = f"The site returned a temporary error (HTTP {response.status_code})."
                else:                                   # verdict is an error message
                    self.say(f"REFUSED — {verdict}")
                    self.record(task, "refused", started)
                    raise ScrapeError(verdict, self.name)

            if attempt < MAX_ATTEMPTS:
                self.say(f"RETRY — {last_problem} Waiting {RETRY_WAIT_S:.0f}s…")
                time.sleep(RETRY_WAIT_S)

        self.record(task, "gave up after retry", started)
        raise ScrapeError(last_problem, self.name)

    # ------------------------------------------------------------------ #
    # Decision rules
    # ------------------------------------------------------------------ #
    @staticmethod
    def is_blocked_domain(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)

    @staticmethod
    def judge(response) -> str:
        """Return 'readable', 'retry', or an error message for the user."""
        code = response.status_code
        if code in RETRYABLE_STATUS:
            return "retry"
        if code in (401, 403):
            return BLOCKED_MESSAGE
        if code == 404:
            return "That page does not exist (HTTP 404)."
        if code >= 400:
            return f"The site returned HTTP {code}."
        content_type = response.headers.get("Content-Type", "")
        if content_type and "html" not in content_type.lower():
            return f"That link is not a webpage ({content_type.split(';')[0]})."
        response.encoding = response.encoding or response.apparent_encoding
        return "readable"

    @staticmethod
    def _headers() -> dict:
        return {
            "User-Agent": Config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
