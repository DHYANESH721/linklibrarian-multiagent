"""summariser_agent.py — SUMMARISER AGENT

Job: read the clean text from the Reader Agent and write a 2–3 sentence
summary of what the page is about and who it is useful for.

  • Thinks with the Groq AI model (through llm_client).
  • If the Quality Checker Agent rejects a summary, the Librarian sends the
    task back here WITH the Quality Checker's feedback, and this agent
    rewrites the summary taking that feedback into account.
  • If the AI is unavailable (no key, no internet, rate limit), it falls back
    to the page's own description so the link can still be saved.
"""

import time

from agents import llm_client
from agents.base_agent import BaseAgent
from utils.helpers import truncate

SYSTEM_PROMPT = (
    "You are a librarian who writes catalogue summaries of web pages. "
    "Reply with a single JSON object and nothing else: {\"summary\": string}. "
    "The summary must be 2-3 complete, plain sentences (about 30-70 words) describing "
    "what the page contains and who it is useful for. Do not repeat the title, "
    "do not use bullet points, and do not mention that you are an AI."
)


class SummariserAgent(BaseAgent):
    name = "Summariser Agent"
    role = "asks the AI for a 2–3 line summary"

    def run(self, task: dict) -> dict:
        started = time.perf_counter()
        feedback = task.get("quality_feedback", {}).get("summary")
        attempt = task.get("summary_attempts", 0) + 1
        task["summary_attempts"] = attempt

        try:
            reply = llm_client.ask_json(SYSTEM_PROMPT, self._prompt(task, feedback), max_tokens=300)
            summary = str(reply.get("summary", "")).strip()
            if not summary:
                raise llm_client.LLMError("empty summary")
            task["summary"] = summary
            task["ai_summary"] = True
            how = "rewrote summary using Quality Checker feedback" if feedback else "wrote summary with AI"
        except llm_client.LLMError as exc:
            self.say(f"AI unavailable ({exc}) — using offline fallback")
            task["summary"] = self._fallback(task)
            task["ai_summary"] = False
            how = "offline fallback summary"

        self.say(f"{how} (attempt {attempt}): \"{truncate(task['summary'], 90)}\"")
        self.record(task, f"{how} (attempt {attempt})", started)
        return task

    @staticmethod
    def _prompt(task: dict, feedback: str | None) -> str:
        body = truncate(task.get("text") or task.get("description", ""), 8000)
        prompt = (
            f"URL: {task['url']}\nTitle: {task.get('title', '')}\n"
            f"Meta description: {task.get('description') or '(none)'}\n\n"
            f"Page content:\n{body}"
        )
        if feedback:
            prompt += (
                f"\n\nYour previous summary was rejected by the quality checker: {feedback}\n"
                f"Previous summary: {task.get('summary', '')}\nWrite a better one."
            )
        return prompt

    @staticmethod
    def _fallback(task: dict) -> str:
        source = task.get("description") or " ".join((task.get("text") or "").split())
        return truncate(source, 320) or f"Saved page: {task.get('title', 'Untitled page')}"
