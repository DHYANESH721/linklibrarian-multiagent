"""base_agent.py — the parent class every LinkLibrarian agent inherits from.

Each agent follows the classic agent loop:

    PERCEIVE  → read what it receives in the shared task
    DECIDE    → apply its own rules / reasoning
    ACT       → write its result back into the task (or refuse with an error)

Agents never call each other directly. The Librarian Agent (the manager)
hands the same `task` dictionary from agent to agent — a shared "blackboard".
Every agent records what it did in `task["trace"]`, so you can see exactly
which agent did which job, in which order, and how long it took.
"""

import logging
import time


class AgentError(Exception):
    """An agent decided the job cannot continue (message is shown to the user)."""

    def __init__(self, message: str, agent: str = "Agent"):
        super().__init__(message)
        self.agent = agent


class ScrapeError(AgentError):
    """The page could not be fetched or contains nothing readable."""


class BaseAgent:
    """Common behaviour for all agents: a name, a role, logging and tracing."""

    name = "Base Agent"
    role = "does nothing on its own"

    def __init__(self):
        self.logger = logging.getLogger(f"agents.{self.__class__.__name__}")

    # ------------------------------------------------------------------ #
    # The one method every agent must implement
    # ------------------------------------------------------------------ #
    def run(self, task: dict) -> dict:
        """Perceive the task, decide, act, and return the updated task."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Helpers shared by every agent
    # ------------------------------------------------------------------ #
    def say(self, message: str) -> None:
        """Print what the agent is doing, e.g. '[Scout Agent] page is readable'."""
        self.logger.info("[%s] %s", self.name, message)

    def record(self, task: dict, action: str, started: float) -> None:
        """Add one line to the task's trace (who did what, and how long it took)."""
        task.setdefault("trace", []).append({
            "agent": self.name,
            "action": action,
            "ms": round((time.perf_counter() - started) * 1000),
        })

    def __repr__(self) -> str:
        return f"<{self.name}: {self.role}>"
