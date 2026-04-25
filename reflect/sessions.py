"""Cluster commits into coding sessions using the git-hours heuristic.

A session is a run of commits where each consecutive pair is <= session_gap_minutes
apart. The credit_minutes for a session is the span between its first and last
commit plus first_commit_credit_minutes (to give the initial commit some weight,
since the setup work before it isn't visible in the git log).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from .git_reader import Commit


@dataclass(frozen=True)
class Session:
    start: datetime
    end: datetime
    commit_count: int
    credit_minutes: int

    @property
    def span_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def cluster(
    commits: Iterable[Commit],
    session_gap_minutes: int,
    first_commit_credit_minutes: int,
) -> list[Session]:
    ordered = sorted(commits, key=lambda c: c.timestamp)
    if not ordered:
        return []

    gap = timedelta(minutes=session_gap_minutes)
    sessions: list[Session] = []
    current: list[Commit] = [ordered[0]]

    for c in ordered[1:]:
        if c.timestamp - current[-1].timestamp <= gap:
            current.append(c)
        else:
            sessions.append(_finalize(current, first_commit_credit_minutes))
            current = [c]
    sessions.append(_finalize(current, first_commit_credit_minutes))
    return sessions


def _finalize(commits: list[Commit], credit: int) -> Session:
    start = commits[0].timestamp
    end = commits[-1].timestamp
    span_min = int((end - start).total_seconds() // 60)
    return Session(
        start=start,
        end=end,
        commit_count=len(commits),
        credit_minutes=span_min + credit,
    )
