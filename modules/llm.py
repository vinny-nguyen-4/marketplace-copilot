"""Thin wrapper around the Claude API.

Every AI module calls `ask_json()`. If no ANTHROPIC_API_KEY is set, modules
fall back to a simple offline heuristic so the app still runs for demos.
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")

_client = None


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported lazily so demo mode works without the SDK configured

        _client = anthropic.Anthropic()
    return _client


def load_prompt(name: str, **kwargs) -> str:
    """Load prompts/<name>.txt and fill in {placeholders}."""
    template = (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return template.format(**kwargs)


def _extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in ``` fences or added a sentence."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output:\n{text[:500]}")
    return json.loads(text[start : end + 1])


def ask_json(prompt: str, max_tokens: int = 2000, retries: int = 1) -> dict:
    """Send a prompt to Claude and return the parsed JSON response."""
    client = _get_client()
    last_error = None
    for _ in range(retries + 1):
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return _extract_json(text)
        except (ValueError, json.JSONDecodeError) as err:
            last_error = err
            prompt += "\n\nYour previous reply was not valid JSON. Reply with the JSON object only."
    raise RuntimeError(f"Claude did not return valid JSON: {last_error}")
