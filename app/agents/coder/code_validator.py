"""Lightweight checks on the snippets the coder produces before they reach the user.

The snippets are illustrative: they reference names defined elsewhere, so the only
hard requirement is that they parse. Ruff runs as an advisory pass with the rules
that legitimately fire on out-of-context examples switched off.
"""

import ast
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

_FENCE = re.compile(r"```(?:python|py)?\n(.*?)```", re.DOTALL)
_RUFF_BIN = shutil.which("ruff")
_ADVISORY_RULES = "F"  # pyflakes only; style rules are irrelevant for a snippet
_EXAMPLE_NOISE = "F821,F401,F841"  # undefined names / unused imports and vars are expected


@dataclass
class SnippetReport:
    """Outcome of checking one snippet: whether it is usable and what to fix."""

    valid: bool
    kind: str | None = None
    issues: list[str] = field(default_factory=list[str])


def extract_code_blocks(text: str) -> list[str]:
    """Pull the fenced code blocks out of a Markdown answer."""
    return [match.strip() for match in _FENCE.findall(text)]


def _advisory_lint(code: str) -> list[str]:
    """Return ruff findings as advisory notes; empty when clean or ruff is missing."""
    if _RUFF_BIN is None:
        return []
    completed = subprocess.run(  # noqa: S603
        [
            _RUFF_BIN,
            "check",
            "--isolated",
            "--no-fix",
            "--select",
            _ADVISORY_RULES,
            "--ignore",
            _EXAMPLE_NOISE,
            "--output-format",
            "json",
            "--stdin-filename",
            "snippet.py",
            "-",
        ],
        input=code,
        capture_output=True,
        text=True,
        check=False,
    )
    found: list[dict[str, Any]] = json.loads(completed.stdout or "[]")
    return [
        f"{item['code']} at line {item['location']['row']}: {item['message']}" for item in found
    ]


def check_code(code: str) -> SnippetReport:
    """Check a snippet: parsing is mandatory, ruff findings are advisory."""
    try:
        ast.parse(code)
    except SyntaxError as error:
        return SnippetReport(
            valid=False, kind="syntax", issues=[f"line {error.lineno}: {error.msg}"]
        )
    advisory = _advisory_lint(code)
    if advisory:
        return SnippetReport(valid=False, kind="lint", issues=advisory)
    return SnippetReport(valid=True)
