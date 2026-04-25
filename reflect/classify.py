"""Commit subject → category classifier (CLAUDE.md §5).

The first whitespace-separated token of the subject line drives the category,
case-insensitive. Trailing punctuation (":", "!", etc.) is stripped before matching,
so "Add: ..." and "Fix!" still classify correctly.
"""
from __future__ import annotations

import re

CATEGORIES: tuple[str, ...] = (
    "feature", "bugfix", "removal", "update",
    "refactor", "test", "chore", "docs", "other",
)

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(add|implement|create|introduce|feat|feature)$", re.I), "feature"),
    (re.compile(r"^(fix|bugfix|correct|resolve|patch)$", re.I), "bugfix"),
    (re.compile(r"^(remove|delete|drop)$", re.I), "removal"),
    (re.compile(r"^(update|change|modify|adjust|tweak)$", re.I), "update"),
    (re.compile(r"^(refactor|cleanup|rename|restructure)$", re.I), "refactor"),
    (re.compile(r"^(test|spec)$", re.I), "test"),
    (re.compile(r"^(chore|bump|dep|deps|lint|format|config)$", re.I), "chore"),
    (re.compile(r"^(doc|docs|readme)$", re.I), "docs"),
]

_PUNCT_TRAIL = ":,.!?;"


def classify_subject(subject: str) -> str:
    stripped = subject.strip()
    if not stripped:
        return "other"
    token = stripped.split(maxsplit=1)[0].rstrip(_PUNCT_TRAIL)
    for pattern, category in _RULES:
        if pattern.match(token):
            return category
    return "other"
