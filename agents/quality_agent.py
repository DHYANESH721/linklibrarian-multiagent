"""quality_agent.py — QUALITY CHECKER AGENT

Job: inspect the finished card BEFORE it is saved and decide:

    ✓ APPROVED  → good enough, the Librarian may save it
    ✗ REJECTED  → explain what is wrong, so the Librarian can send the work
                  back to the Summariser Agent and/or the Tagger Agent to redo

Rules it checks
---------------
Summary : at least 2 sentences, 15–120 words, not just the page title,
          no "as an AI" / refusal phrases, not cut off mid-sentence
Tags    : 2–6 tags
Category: a built-in category, an existing one, or a clean new name
"""

import re
import time

from agents.base_agent import BaseAgent
from agents.tagger_agent import TaggerAgent

MIN_WORDS, MAX_WORDS = 15, 120
MIN_SENTENCES = 2
MIN_TAGS, MAX_TAGS = 2, 6
BAD_PHRASES = ("as an ai", "i cannot", "i can't", "i'm sorry", "language model",
               "no content", "unable to access")


class QualityCheckerAgent(BaseAgent):
    name = "Quality Checker Agent"
    role = "checks the result and sends poor work back to be redone"

    def run(self, task: dict) -> dict:
        started = time.perf_counter()
        summary_problems = self.check_summary(task)
        tag_problems = self.check_tags(task)

        task["quality_feedback"] = {}
        if summary_problems:
            task["quality_feedback"]["summary"] = "; ".join(summary_problems)
        if tag_problems:
            task["quality_feedback"]["tags"] = "; ".join(tag_problems)
        task["approved"] = not (summary_problems or tag_problems)

        if task["approved"]:
            self.say("APPROVED — summary and tags meet the quality rules")
            self.record(task, "approved", started)
        else:
            problems = summary_problems + tag_problems
            self.say(f"REJECTED — {'; '.join(problems)}")
            self.record(task, f"rejected: {'; '.join(problems)}", started)
        return task

    # ------------------------------------------------------------------ #
    @staticmethod
    def check_summary(task: dict) -> list[str]:
        summary = (task.get("summary") or "").strip()
        problems = []
        words = summary.split()
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", summary) if len(s.split()) >= 3]

        if len(words) < MIN_WORDS:
            problems.append(f"summary too short ({len(words)} words, need {MIN_WORDS}+)")
        elif len(words) > MAX_WORDS:
            problems.append(f"summary too long ({len(words)} words, max {MAX_WORDS})")
        if words and len(sentences) < MIN_SENTENCES:
            problems.append(f"summary has {len(sentences)} sentence(s), need {MIN_SENTENCES}-3")
        if summary and summary[-1] not in ".!?\"')":
            problems.append("summary ends mid-sentence")
        title = (task.get("title") or "").strip().lower()
        if title and summary.lower().rstrip(".") == title.rstrip("."):
            problems.append("summary only repeats the title")
        if any(p in summary.lower() for p in BAD_PHRASES):
            problems.append("summary contains a refusal or 'as an AI' phrase")
        return problems

    @staticmethod
    def check_tags(task: dict) -> list[str]:
        problems = []
        tags = task.get("tags") or []
        if not MIN_TAGS <= len(tags) <= MAX_TAGS:
            problems.append(f"{len(tags)} tags (need {MIN_TAGS}-{MAX_TAGS})")
        category = task.get("category") or ""
        accepted, _ = TaggerAgent.choose_category(category, task.get("existing_categories"))
        if not category or accepted != category:
            problems.append(f"invalid category '{category}'")
        return problems
