"""Rich-based terminal renderer.

Display rules from CLAUDE.md §7:
  - Numbers carry units (e.g. "4h 35m", not "4.58").
  - Percentages are whole numbers.
  - Estimated values are prefixed with "~".
  - Neutral markers only: ✓, ⚠, —. No judgment emoji.
  - The daily view ends with ONE reflection prompt chosen from whatever stood out.
"""
from __future__ import annotations

from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .metrics import DayMetrics, PeriodSummary


def _fmt_minutes(m: int) -> str:
    if m < 60:
        return f"{m}m"
    h, rem = divmod(m, 60)
    return f"{h}h {rem}m" if rem else f"{h}h"


def _fmt_opt_minutes(m: int | None) -> str:
    return "—" if m is None else _fmt_minutes(m)


def _fmt_pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _fmt_hm(ts: datetime) -> str:
    return ts.strftime("%H:%M")


def _kv_table() -> Table:
    t = Table.grid(padding=(0, 2))
    t.add_column(justify="left", style="dim", no_wrap=True)
    t.add_column(justify="left")
    return t


def _choose_prompt(m: DayMetrics) -> str:
    """Pick ONE reflection prompt based on what stood out in the day's numbers.

    Order of preference tries to surface the most actionable signal first.
    Framing stays neutral — questions, not verdicts.
    """
    if m.stale_tasks:
        t = m.stale_tasks[0]
        return (
            f'"{t}" was mentioned recently but not in the last 5 days and '
            f"hasn't been merged. Kill it, resume it, or park it?"
        )

    if (
        m.bugfix_ratio_rolling_median is not None
        and m.bugfix_ratio >= m.bugfix_ratio_rolling_median + 0.15
        and m.commit_count >= 3
    ):
        return (
            f"Bugfixes were {_fmt_pct(m.bugfix_ratio)} of today's commits vs. "
            f"your 4-week median of {_fmt_pct(m.bugfix_ratio_rolling_median)}. "
            f"Is something unstable, or is this triage week?"
        )

    if m.rework_ratio >= 0.4 and m.commit_count >= 3:
        return (
            f"{_fmt_pct(m.rework_ratio)} of today's commits touched files you "
            f"edited in the last few days. Is this iteration or re-iteration?"
        )

    if m.project_switches >= 3:
        return (
            f"You switched projects {m.project_switches} times today. "
            f"Did the switching cost anything, or did it feel fine?"
        )

    if m.interruption_count >= 3:
        return (
            f"{m.interruption_count} interruptions logged "
            f"({_fmt_minutes(m.interruption_minutes)} total). "
            f"Anything worth protecting against tomorrow?"
        )

    if m.first_commit_latency_minutes is not None and m.first_commit_latency_minutes >= 180:
        return (
            f"~{_fmt_minutes(m.first_commit_latency_minutes)} passed between "
            f"your first log entry and your first commit. What filled that window?"
        )

    if m.deep_work_day and m.longest_session is not None:
        return (
            f"You got a {_fmt_minutes(m.longest_session.span_minutes)} continuous "
            f"block ({_fmt_hm(m.longest_session.start)}–{_fmt_hm(m.longest_session.end)}). "
            f"What made that possible — and can you repeat it?"
        )

    if m.commit_count == 0 and m.non_committed_focus_minutes < 30 and m.meeting_minutes >= 60:
        return (
            f"No commits and little logged deep-think today — "
            f"{_fmt_minutes(m.meeting_minutes)} in meetings. "
            f"Was that the right shape for the day?"
        )

    if m.unattributed_commits > 0 and m.commit_count > 0:
        return (
            f"{m.unattributed_commits} of {m.commit_count} commits didn't match "
            f"any task in your end-of-day list. Missing a task, or off-plan work?"
        )

    return "What felt different about today compared to yesterday?"


def _time_block(m: DayMetrics) -> Table:
    t = _kv_table()
    t.add_row("Focused coding", f"~{_fmt_minutes(m.focused_coding_minutes)}")
    t.add_row("Deep think (logged)", _fmt_minutes(m.non_committed_focus_minutes))
    t.add_row("Meetings", _fmt_minutes(m.meeting_minutes))
    t.add_row("Pre-merge testing", _fmt_minutes(m.testing_minutes))
    t.add_row(
        "Interruptions",
        f"{_fmt_minutes(m.interruption_minutes)}"
        + (f" ({m.interruption_count})" if m.interruption_count else ""),
    )
    return t


def _session_block(m: DayMetrics) -> Table:
    t = _kv_table()
    if m.longest_session is None:
        t.add_row("Longest session", "—")
    else:
        ls = m.longest_session
        t.add_row(
            "Longest session",
            f"{_fmt_minutes(ls.span_minutes)} "
            f"({_fmt_hm(ls.start)}–{_fmt_hm(ls.end)})",
        )
    t.add_row("Deep-work day", "✓" if m.deep_work_day else "—")
    t.add_row("First-commit lag", f"~{_fmt_opt_minutes(m.first_commit_latency_minutes)}")
    return t


def _shape_block(m: DayMetrics) -> Table:
    t = _kv_table()
    t.add_row("Commits", str(m.commit_count))

    stack_str = " · ".join(
        f"{k} {v}" for k, v in sorted(m.stack_split.items(), key=lambda x: -x[1])
    ) or "—"
    t.add_row("Stack split", stack_str)

    cat_str = " · ".join(
        f"{k} {v}" for k, v in sorted(m.category_split.items(), key=lambda x: -x[1])
    ) or "—"
    t.add_row("Categories", cat_str)

    bug_row = _fmt_pct(m.bugfix_ratio)
    if m.bugfix_ratio_rolling_median is not None:
        bug_row += f"   (4w median {_fmt_pct(m.bugfix_ratio_rolling_median)})"
    t.add_row("Bugfix ratio", bug_row)

    t.add_row("Rework ratio", _fmt_pct(m.rework_ratio))
    t.add_row("Project switches", str(m.project_switches))
    return t


def _task_block(m: DayMetrics) -> Table | Text:
    if not m.commits_per_task and m.unattributed_commits == 0:
        return Text("— no task list logged for today —", style="dim")
    t = _kv_table()
    for task, count in sorted(m.commits_per_task.items(), key=lambda x: -x[1]):
        t.add_row(task, f"{count} commit" + ("s" if count != 1 else ""))
    if m.unattributed_commits:
        t.add_row("unattributed", f"{m.unattributed_commits} commits")
    if m.ambiguous_commits:
        t.add_row("⚠ ambiguous", f"{m.ambiguous_commits} commits (pick one)")
    return t


def render_day(m: DayMetrics, console: Console | None = None) -> None:
    console = console or Console()
    date_str = m.target_date.strftime("%A, %Y-%m-%d")
    console.print(Rule(Text.assemble(("reflect ", "bold"), ("· ", "dim"), (date_str, "cyan"))))
    console.print()

    sections: list = [
        Panel(_time_block(m), title="time", title_align="left", border_style="dim"),
        Panel(_session_block(m), title="sessions", title_align="left", border_style="dim"),
        Panel(_shape_block(m), title="work shape", title_align="left", border_style="dim"),
        Panel(_task_block(m), title="tasks", title_align="left", border_style="dim"),
    ]
    if m.stale_tasks:
        stale_text = Text()
        for t in m.stale_tasks:
            stale_text.append(f"· {t}\n")
        sections.append(Panel(stale_text, title="stale (>5d, no merge)", title_align="left", border_style="yellow"))

    if m.reflect_note:
        sections.append(Panel(Text(m.reflect_note, style="italic"), title="your note", title_align="left", border_style="dim"))

    console.print(Group(*sections))
    console.print()

    prompt = Text.assemble(("▸ ", "bold cyan"), (_choose_prompt(m), "italic"))
    console.print(Panel(prompt, title="reflection", title_align="left", border_style="cyan"))


def render_period(s: PeriodSummary, console: Console | None = None) -> None:
    console = console or Console()
    title = Text.assemble(("reflect ", "bold"), ("· ", "dim"), (s.label, "cyan"))
    console.print(Rule(title))
    console.print()

    totals = _kv_table()
    totals.add_row("Days", str(s.day_count))
    totals.add_row("Commits", str(s.commit_count))
    totals.add_row("Focused coding", f"~{_fmt_minutes(s.focused_coding_minutes)}")
    totals.add_row("Meetings", _fmt_minutes(s.meeting_minutes))
    totals.add_row("Pre-merge testing", _fmt_minutes(s.testing_minutes))
    totals.add_row(
        "Interruptions",
        f"{_fmt_minutes(s.interruption_minutes)}"
        + (f" ({s.interruption_count})" if s.interruption_count else ""),
    )
    totals.add_row("Deep-work days", f"{s.deep_work_days} of {s.day_count}")
    totals.add_row("Bugfix ratio", _fmt_pct(s.bugfix_ratio))
    totals.add_row("Rework ratio", _fmt_pct(s.rework_ratio))
    stack_str = " · ".join(f"{k} {v}" for k, v in sorted(s.stack_split.items(), key=lambda x: -x[1])) or "—"
    totals.add_row("Stack split", stack_str)
    cat_str = " · ".join(f"{k} {v}" for k, v in sorted(s.category_split.items(), key=lambda x: -x[1])) or "—"
    totals.add_row("Categories", cat_str)

    bars = Table.grid(padding=(0, 1))
    bars.add_column(style="dim", justify="right")
    bars.add_column()
    max_count = max((c for _, c in s.per_day_commits), default=0)
    for d, c in s.per_day_commits:
        bar = "█" * c if max_count <= 20 else "█" * int(round(c / max_count * 20))
        bars.add_row(d.strftime("%a %m-%d"), f"{bar}  {c}" if c else "—")

    console.print(Group(
        Panel(totals, title="totals", title_align="left", border_style="dim"),
        Panel(bars, title="commits per day", title_align="left", border_style="dim"),
    ))
