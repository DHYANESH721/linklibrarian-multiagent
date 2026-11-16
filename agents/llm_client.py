"""llm_client.py — the AI TOOL the agents use (this file is NOT an agent).

The Summariser Agent and the Tagger Agent both need to "think" with a large
language model. Instead of each one talking to Groq on its own, they share
this small client.

Provider: Groq (https://console.groq.com) — free tier, OpenAI-compatible.
Model:    llama-3.3-70b-versatile (set AI_MODEL in .env to change it).
"""

import json
import re

import requests

from config import Config


class LLMError(Exception):
    """The AI provider could not be reached or replied with something unusable."""


def ask_json(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> dict:
    """Send a prompt to Groq and return the reply as a Python dict.

    Raises LLMError on any problem, so the calling agent can fall back.
    """
    if not Config.ai_enabled():
        raise LLMError("GROQ_API_KEY is not set")

    payload = {
        "model": Config.AI_MODEL,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(Config.AI_BASE_URL, json=payload, headers=headers,
                                 timeout=Config.AI_TIMEOUT)
    except requests.exceptions.Timeout:
        raise LLMError("AI provider timed out") from None
    except requests.exceptions.RequestException as exc:
        raise LLMError(f"network error: {exc}") from None

    if response.status_code == 401:
        raise LLMError("invalid API key")
    if response.status_code == 429:
        raise LLMError("rate limit reached")
    if response.status_code >= 400:
        raise LLMError(f"HTTP {response.status_code}: {response.text[:200]}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"unexpected response shape: {exc}") from None
    return parse_json(content)


def parse_json(content: str) -> dict:
    """Parse the model's reply, tolerating stray ```json fences."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise LLMError("model did not return JSON") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"malformed JSON: {exc}") from None
    if not isinstance(data, dict):
        raise LLMError("model returned JSON that is not an object")
    return data
