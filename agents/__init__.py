"""The LinkLibrarian multi-agent team.

    Librarian Agent        (manager)  librarian_agent.py
      ├── Scout Agent                 scout_agent.py
      ├── Reader Agent                reader_agent.py
      ├── Summariser Agent            summariser_agent.py
      ├── Tagger Agent                tagger_agent.py
      └── Quality Checker Agent       quality_agent.py

base_agent.py is the parent class they all share.
llm_client.py is the AI tool (Groq) used by the Summariser and Tagger.
"""

from agents.base_agent import AgentError, BaseAgent, ScrapeError
from agents.librarian_agent import DuplicateLinkError, LibrarianAgent

__all__ = ["AgentError", "BaseAgent", "ScrapeError", "DuplicateLinkError", "LibrarianAgent"]
