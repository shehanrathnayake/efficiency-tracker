"""Commit → task attribution (CLAUDE.md §8).

Rough-by-design. Two passes:
  1. Score each commit against each task using keyword overlap between the
     commit subject and the task name (bag-of-words, lowercased, stopwords
     removed).
  2. For commits that were unattributed or ambiguous after pass 1, re-score
     using pass-1 file-path overlap — i.e. a commit touching files another
     commit already attributed to the same task gets a bonus.

Ties are flagged (ambiguous=True) rather than silently resolved, so the user
can notice which commits need manual disambiguation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .git_reader import Commit


STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "to", "for",
    "with", "by", "at", "from", "up", "into", "as", "is", "it", "be",
    "this", "that", "these", "those",
    # Verbs that drive §5 classification — noise for task matching.
    "add", "adds", "adding", "fix", "fixes", "fixing",
    "update", "updates", "updating", "remove", "removes", "removing",
    "refactor", "refactors", "implement", "implements",
    "create", "creates", "change", "changes",
    "test", "tests", "chore", "doc", "docs",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Loose by design — one shared keyword is enough to attribute.
MIN_SCORE = 1.0
FILE_OVERLAP_WEIGHT = 0.5


@dataclass(frozen=True)
class TaskAttribution:
    commit_hash: str
    task: str | None
    score: float
    ambiguous: bool


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 1 and t not in STOPWORDS
    }


def _normalize_tasks(tasks_csv: str) -> list[str]:
    return [t.strip() for t in tasks_csv.split(",") if t.strip()]


def _pick_best(scores: dict[str, float]) -> tuple[str | None, float, bool]:
    if not scores:
        return (None, 0.0, False)
    top = max(scores.values())
    if top <= 0:
        return (None, 0.0, False)
    winners = [t for t, s in scores.items() if s == top]
    return (winners[0], top, len(winners) > 1)


def attribute(commits: Iterable[Commit], tasks_csv: str) -> list[TaskAttribution]:
    tasks = _normalize_tasks(tasks_csv)
    commits_list = list(commits)

    if not tasks or not commits_list:
        return [TaskAttribution(c.hash, None, 0.0, False) for c in commits_list]

    task_tokens = {t: _tokens(t) for t in tasks}

    # Pass 1: keyword-only scores per commit.
    pass1: dict[str, tuple[str | None, float, bool]] = {}
    for c in commits_list:
        subj_tokens = _tokens(c.subject)
        scores = {t: float(len(subj_tokens & task_tokens[t])) for t in tasks}
        pass1[c.hash] = _pick_best(scores)

    # Build {task -> set(files)} from unambiguous pass-1 attributions.
    task_files: dict[str, set[str]] = {t: set() for t in tasks}
    for c in commits_list:
        picked, score, ambig = pass1[c.hash]
        if picked is not None and score >= MIN_SCORE and not ambig:
            task_files[picked].update(f.path for f in c.files)

    # Pass 2: finalize each commit, re-scoring pass-1 misses with file overlap.
    out: list[TaskAttribution] = []
    for c in commits_list:
        picked, score, ambig = pass1[c.hash]
        if picked is not None and score >= MIN_SCORE and not ambig:
            out.append(TaskAttribution(c.hash, picked, score, False))
            continue

        subj_tokens = _tokens(c.subject)
        commit_files = {f.path for f in c.files}
        scores = {
            t: float(len(subj_tokens & task_tokens[t]))
              + FILE_OVERLAP_WEIGHT * len(commit_files & task_files[t])
            for t in tasks
        }
        picked2, score2, ambig2 = _pick_best(scores)
        if score2 >= MIN_SCORE and picked2 is not None:
            out.append(TaskAttribution(c.hash, picked2, score2, ambig2))
        else:
            out.append(TaskAttribution(c.hash, None, score2, False))
    return out
