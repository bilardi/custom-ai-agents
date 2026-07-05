"""Load prompt templates from the prompts/ folder."""

from pathlib import Path


def load_prompt(name: str, base: Path | None = None) -> str:
    """Return the content of prompts/<name>.md, stripped of surrounding whitespace."""
    base = base or Path("prompts")
    return (base / f"{name}.md").read_text(encoding="utf-8").strip()
