"""Compute the 14 daily metrics from CLAUDE.md §7, plus weekly/monthly aggregates.

All functions are pure — they take already-loaded commits and log entries and
return dataclasses. Nothing here reads files, invokes git, or mutates state.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median

from .attribution import TaskAttribution, attribute
from .classify import classify_subject
from .config import Settings
from .git_reader import Commit
from .log_reader import LogEntry
from .sessions import Session, cluster


@dataclass(frozen=True)
class DayMetrics:
    target_date: date
    commit_count: int
    focused_coding_minutes: int
    non_committed_focus_minutes: int
    meeting_minutes: int
    testing_minutes: int
    interruption_minutes: int
    interruption_count: int
    longest_session: Session | None
    deep_work_day: bool
    first_commit_latency_minutes: int | None
    commits_per_task: dict[str, int]
    unattributed_commits: int
    ambiguous_commits: int
    stack_split: dict[str, int]
    category_split: dict[str, int]
    bugfix_ratio: float
    bugfix_ratio_rolling_median: float | None
    rework_ratio: float
    project_switches: int
    stale_tasks: list[str]
    sessions: list[Session]
    attributions: list[TaskAttribution]
    reflect_note: str | None


@dataclass(frozen=True)
class PeriodSummary:
    label: str
    start: date
    end: date
    day_count: int
    commit_count: int
    focused_coding_minutes: int
    meeting_minutes: int
    testing_minutes: int
    interruption_minutes: int
    interruption_count: int
    deep_work_days: int
    stack_split: dict[str, int]
    category_split: dict[str, int]
    bugfix_ratio: float
    rework_ratio: float
    per_day_commits: list[tuple[date, int]]


def _on_date(ts: datetime, d: date) -> bool:
    return ts.date() == d


def _sum_minutes(entries: list[LogEntry], category: str) -> int:
    return sum(e.duration_min for e in entries if e.category == category)


def _count_by(entries: list[LogEntry], category: str) -> int:
    return sum(1 for e in entries if e.category == category)


def _latest_tasks_entry(entries: list[LogEntry], d: date) -> str:
    rows = [e for e in entries if _on_date(e.timestamp, d) and e.category == "tasks"]
    return rows[-1].note if rows else ""


def _latest_reflect_entry(entries: list[LogEntry], d: date) -> str | None:
    rows = [e for e in entries if _on_date(e.timestamp, d) and e.category == "reflect"]
    return rows[-1].note if rows else None


def _rolling_bugfix_median(
    all_commits: list[Commit], target: date, window_days: int = 28, min_days: int = 5
) -> float | None:
    start = target - timedelta(days=window_days)
    by_day: dict[date, list[int]] = {}
    for c in all_commits:
        d = c.timestamp.date()
        if start <= d < target:
            is_bug = 1 if classify_subject(c.subject) == "bugfix" else 0
            by_day.setdefault(d, []).append(is_bug)
    ratios = [sum(v) / len(v) for v in by_day.values() if v]
    if len(ratios) < min_days:
        return None
    return median(ratios)


def _rework_ratio(
    day_commits: list[Commit],
    all_commits: list[Commit],
    target: date,
    lookback_days: int,
) -> float:
    if not day_commits:
        return 0.0
    start = target - timedelta(days=lookback_days)
    files_by_project: dict[str, set[str]] = {}
    for c in all_commits:
        d = c.timestamp.date()
        if start <= d < target:
            files_by_project.setdefault(c.project, set()).update(f.path for f in c.files)

    rework = 0
    for c in day_commits:
        recent = files_by_project.get(c.project, set())
        if recent and any(f.path in recent for f in c.files):
            rework += 1
    return rework / len(day_commits)


def _project_switches(day_commits: list[Commit]) -> int:
    ordered = sorted(day_commits, key=lambda c: c.timestamp)
    switches = 0
    prev: str | None = None
    for c in ordered:
        if prev is not None and c.project != prev:
            switches += 1
        prev = c.project
    return switches


def _stale_tasks(all_entries: list[LogEntry], target: date) -> list[str]:
    win_14_start = target - timedelta(days=14)
    win_5_start = target - timedelta(days=5)

    def tasks_between(start: date, end: date) -> set[str]:
        out: set[str] = set()
        for e in all_entries:
            if e.category != "tasks":
                continue
            if not (start <= e.timestamp.date() <= end):
                continue
            for t in e.note.split(","):
                t = t.strip().lower()
                if t:
                    out.add(t)
        return out

    tasks_14 = tasks_between(win_14_start, target)
    tasks_5 = tasks_between(win_5_start, target)

    merge_notes = " | ".join(
        e.note.lower() for e in all_entries
        if e.category == "merge_event"
        and win_14_start <= e.timestamp.date() <= target
    )

    candidates: list[str] = []
    for t in tasks_14 - tasks_5:
        keywords = [w for w in t.split() if len(w) > 3]
        if keywords and any(w in merge_notes for w in keywords):
            continue
        candidates.append(t)
    candidates.sort()
    return candidates


def compute_day(
    target: date,
    all_commits: list[Commit],
    all_entries: list[LogEntry],
    settings: Settings,
) -> DayMetrics:
    day_commits = [c for c in all_commits if _on_date(c.timestamp, target)]
    day_entries = [e for e in all_entries if _on_date(e.timestamp, target)]

    # §7.1, §7.6, §7.7
    sessions = cluster(
        day_commits,
        settings.session_gap_minutes,
        settings.first_commit_credit_minutes,
    )
    focused = sum(s.credit_minutes for s in sessions)
    longest = max(sessions, key=lambda s: s.span_minutes, default=None)
    deep_work = (
        any(s.span_minutes >= settings.deep_work_min_block_minutes for s in sessions)
        and _count_by(day_entries, "interrupt") < settings.deep_work_max_interruptions
    )

    # §7.2–7.5
    deepthink_min = _sum_minutes(day_entries, "deepthink")
    meeting_min = _sum_minutes(day_entries, "meeting")
    testing_min = _sum_minutes(day_entries, "testing")
    interrupt_min = _sum_minutes(day_entries, "interrupt")
    interrupt_count = _count_by(day_entries, "interrupt")

    # §7.8
    first_lat: int | None = None
    if day_commits and day_entries:
        first_entry_ts = min(e.timestamp for e in day_entries)
        first_commit_ts = min(c.timestamp for c in day_commits)
        delta = (first_commit_ts - first_entry_ts).total_seconds() / 60
        if delta >= 0:
            first_lat = int(delta)

    # §7.9
    tasks_csv = _latest_tasks_entry(all_entries, target)
    attributions = attribute(day_commits, tasks_csv)
    per_task: Counter[str] = Counter()
    unattributed = 0
    ambiguous = 0
    for a in attributions:
        if a.task is None:
            unattributed += 1
        else:
            per_task[a.task] += 1
            if a.ambiguous:
                ambiguous += 1

    # §7.10
    stack_split = Counter(c.stack for c in day_commits)
    category_split = Counter(classify_subject(c.subject) for c in day_commits)

    # §7.11
    bug_today = category_split.get("bugfix", 0)
    bugfix_ratio = (bug_today / len(day_commits)) if day_commits else 0.0
    rolling = _rolling_bugfix_median(all_commits, target)

    # §7.12
    rework = _rework_ratio(day_commits, all_commits, target, settings.rework_lookback_days)

    # §7.13
    switches = _project_switches(day_commits)

    # §7.14
    stale = _stale_tasks(all_entries, target)

    return DayMetrics(
        target_date=target,
        commit_count=len(day_commits),
        focused_coding_minutes=focused,
        non_committed_focus_minutes=deepthink_min,
        meeting_minutes=meeting_min,
        testing_minutes=testing_min,
        interruption_minutes=interrupt_min,
        interruption_count=interrupt_count,
        longest_session=longest,
        deep_work_day=deep_work,
        first_commit_latency_minutes=first_lat,
        commits_per_task=dict(per_task),
        unattributed_commits=unattributed,
        ambiguous_commits=ambiguous,
        stack_split=dict(stack_split),
        category_split=dict(category_split),
        bugfix_ratio=bugfix_ratio,
        bugfix_ratio_rolling_median=rolling,
        rework_ratio=rework,
        project_switches=switches,
        stale_tasks=stale,
        sessions=sessions,
        attributions=attributions,
        reflect_note=_latest_reflect_entry(all_entries, target),
    )


def compute_period(
    label: str,
    start: date,
    end: date,
    all_commits: list[Commit],
    all_entries: list[LogEntry],
    settings: Settings,
) -> PeriodSummary:
    """Aggregate per-day metrics across [start, end] (inclusive)."""
    days: list[DayMetrics] = []
    d = start
    while d <= end:
        days.append(compute_day(d, all_commits, all_entries, settings))
        d += timedelta(days=1)

    stack_split: Counter[str] = Counter()
    category_split: Counter[str] = Counter()
    total_commits = 0
    bug_commits = 0
    rework_commits = 0
    for m in days:
        stack_split.update(m.stack_split)
        category_split.update(m.category_split)
        total_commits += m.commit_count
        bug_commits += m.category_split.get("bugfix", 0)
        rework_commits += int(round(m.rework_ratio * m.commit_count))

    bugfix_ratio = bug_commits / total_commits if total_commits else 0.0
    rework_ratio = rework_commits / total_commits if total_commits else 0.0

    return PeriodSummary(
        label=label,
        start=start,
        end=end,
        day_count=len(days),
        commit_count=total_commits,
        focused_coding_minutes=sum(m.focused_coding_minutes for m in days),
        meeting_minutes=sum(m.meeting_minutes for m in days),
        testing_minutes=sum(m.testing_minutes for m in days),
        interruption_minutes=sum(m.interruption_minutes for m in days),
        interruption_count=sum(m.interruption_count for m in days),
        deep_work_days=sum(1 for m in days if m.deep_work_day),
        stack_split=dict(stack_split),
        category_split=dict(category_split),
        bugfix_ratio=bugfix_ratio,
        rework_ratio=rework_ratio,
        per_day_commits=[(m.target_date, m.commit_count) for m in days],
    )
