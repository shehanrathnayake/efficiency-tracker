"""Read and parse the manual time log CSV.

Format (header row optional):
    date,time,duration_min,category,note

Tolerant of:
  - a present-or-absent header row
  - extra commas in the note field when the user forgot to quote
  - a leading UTF-8 BOM (Windows PowerShell sometimes writes one)
  - blank lines
Malformed rows (bad date, bad time, non-integer duration) are silently skipped.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import paths


KNOWN_CATEGORIES: frozenset[str] = frozenset({
    "meeting", "testing", "deepthink", "interrupt", "review",
    "admin", "merge_event", "reflect", "tasks",
})


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    duration_min: int
    category: str
    note: str

    @property
    def date(self) -> date:
        return self.timestamp.date()


def read_log(path: Path | None = None) -> list[LogEntry]:
    p = path if path is not None else paths.log_path()
    if not p.exists():
        return []

    entries: list[LogEntry] = []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if not row or all(not c.strip() for c in row):
                continue
            if i == 0 and row[0].strip().lower() == "date":
                continue
            if len(row) < 5:
                row = row + [""] * (5 - len(row))
            date_s = row[0].strip()
            time_s = row[1].strip()
            dur_s = row[2].strip()
            cat = row[3].strip().lower()
            note = ",".join(row[4:]).strip()

            try:
                d = datetime.strptime(date_s, "%Y-%m-%d").date()
                t = datetime.strptime(time_s, "%H:%M").time()
                dur = int(dur_s)
            except ValueError:
                continue

            entries.append(LogEntry(
                timestamp=datetime.combine(d, t),
                duration_min=dur,
                category=cat,
                note=note,
            ))

    entries.sort(key=lambda e: e.timestamp)
    return entries
