"""Loads prompts from versioned files (CLAUDE.md hard rule 2 — never inline in Python)
and logs which version was used, per the GenAI Playbook's Reasoning Control checklist.
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
