"""`reflect` command-line entry point."""
from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date, datetime, timedelta

from . import __version__
from . import config as config_mod
from . import dashboard
from . import paths
from .git_reader import GitReadError, read_all_commits
from .log_reader import read_log
from .metrics import compute_day, compute_period


def _parse_day(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _iso_week_bounds(year: int, week: int) -> tuple[date, date]:
    monday = date.fromisocalendar(year, week, 1)
    return monday, monday + timedelta(days=6)


def _load_or_fail() -> tuple[config_mod.Config, list, list]:
    try:
        cfg = config_mod.load()
    except config_mod.ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        commits = read_all_commits(cfg.repos)
    except GitReadError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    entries = read_log()
    return cfg, commits, entries


def cmd_day(target: date) -> int:
    cfg, commits, entries = _load_or_fail()
    metrics = compute_day(target, commits, entries, cfg.settings)
    dashboard.render_day(metrics)
    return 0


def cmd_week(arg: str | None) -> int:
    today = date.today()
    if arg is None:
        year, week, _ = today.isocalendar()
    else:
        try:
            y_str, w_str = arg.split("-")
            year, week = int(y_str), int(w_str)
        except ValueError:
            print("error: week must be in YYYY-WW format (ISO week)", file=sys.stderr)
            return 2
    start, end = _iso_week_bounds(year, week)
    if end > today:
        end = today
    cfg, commits, entries = _load_or_fail()
    label = f"Week {year}-W{week:02d}  ({start} → {end})"
    summary = compute_period(label, start, end, commits, entries, cfg.settings)
    dashboard.render_period(summary)
    return 0


def cmd_month(arg: str | None) -> int:
    today = date.today()
    if arg is None:
        year, month = today.year, today.month
    else:
        try:
            y_str, m_str = arg.split("-")
            year, month = int(y_str), int(m_str)
        except ValueError:
            print("error: month must be in YYYY-MM format", file=sys.stderr)
            return 2
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    if end > today:
        end = today
    cfg, commits, entries = _load_or_fail()
    label = f"{calendar.month_name[month]} {year}  ({start} → {end})"
    summary = compute_period(label, start, end, commits, entries, cfg.settings)
    dashboard.render_period(summary)
    return 0


def cmd_config() -> int:
    created = config_mod.bootstrap_if_missing()
    cfg_path = paths.config_path()
    log_path = paths.log_path()
    if created:
        print(f"Bootstrapped {paths.data_dir()}")
        print(f"  config: {cfg_path}")
        print(f"  log:    {log_path}")
        print()
        print("Edit config.toml to add your repos, then run `reflect today`.")
        return 0

    try:
        cfg = config_mod.load()
    except config_mod.ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"config: {cfg_path}")
    print(f"log:    {log_path}")
    print()
    print("repos:")
    for r in cfg.repos:
        marker = "✓" if r.path.exists() else "⚠"
        print(f"  {marker} {r.key:<20} [{r.stack:<10}] project={r.project}  email={r.git_email}")
        print(f"      path: {r.path}")
    print()
    print("settings:")
    s = cfg.settings
    for name in (
        "deep_work_min_block_minutes",
        "deep_work_max_interruptions",
        "rework_lookback_days",
        "session_gap_minutes",
        "first_commit_credit_minutes",
    ):
        print(f"  {name} = {getattr(s, name)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="reflect",
        description="Personal reflection dashboard from local git history and a manual time log.",
    )
    p.add_argument("--version", action="version", version=f"reflect {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("today", help="today's dashboard")
    sub.add_parser("yesterday", help="yesterday's dashboard")
    day_p = sub.add_parser("day", help="specific day (YYYY-MM-DD)")
    day_p.add_argument("date")
    week_p = sub.add_parser("week", help="current week, or specific (YYYY-WW)")
    week_p.add_argument("week", nargs="?")
    month_p = sub.add_parser("month", help="current month, or specific (YYYY-MM)")
    month_p.add_argument("month", nargs="?")
    sub.add_parser("config", help="bootstrap data dir or print resolved config")

    args = p.parse_args(argv)

    if args.cmd is None:
        p.print_help()
        return 0

    # Bootstrap for any command that reads config/log (not strictly needed for
    # `config` since that command bootstraps itself).
    if args.cmd != "config":
        config_mod.bootstrap_if_missing()

    if args.cmd == "today":
        return cmd_day(date.today())
    if args.cmd == "yesterday":
        return cmd_day(date.today() - timedelta(days=1))
    if args.cmd == "day":
        try:
            return cmd_day(_parse_day(args.date))
        except ValueError:
            print("error: date must be in YYYY-MM-DD format", file=sys.stderr)
            return 2
    if args.cmd == "week":
        return cmd_week(args.week)
    if args.cmd == "month":
        return cmd_month(args.month)
    if args.cmd == "config":
        return cmd_config()

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
