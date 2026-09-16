"""Loads prompts from versioned files (CLAUDE.md hard rule 2 — never inline in Python)
and logs which version was used, per the GenAI Playbook's Reasoning Control checklist.

When a prompt needs runtime content substituted in (e.g. a chunk's page text), use
`.replace("{content}", value)` on the loaded string, NOT `str.format()` — a prompt that
includes a JSON example (map_pass, reduce prompts) is full of literal `{braces}` that
`.format()` misinterprets as placeholders and raises KeyError on. Confirmed the hard
way in app/pipeline/map_pass.py (docs/DECISIONS.md #37).
"""

from functools import cache
from pathlib import Path

from app.core.logging import get_logger

PROMPTS_DIR = Path(__file__).parent
logger = get_logger(__name__)


@cache
def load_prompt(category: str, version: str) -> str:
    """category: e.g. "vision", "map_pass", "reduce". version: e.g. "v1_vision_extract"."""
    path = PROMPTS_DIR / category / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {category}/{version} (looked in {path})")
    logger.info("prompt.loaded", category=category, version=version)
    return path.read_text(encoding="utf-8")
