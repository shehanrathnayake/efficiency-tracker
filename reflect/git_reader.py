"""Read-only git access.

Safety invariants (see CLAUDE.md §6, non-negotiable):
  1. Only subcommands in ALLOWED_GIT_SUBCOMMANDS may run. Any attempt to call
     another subcommand raises GitSafetyError before git is invoked.
  2. Working directory is never changed. Every call uses `git -C <repo_path>`.
  3. No network calls. Nothing here fetches, pushes, or contacts a remote.

All git invocations funnel through the single `_run_git` choke point so the
allowlist cannot be bypassed by adding a second subprocess call elsewhere.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import RepoConfig

ALLOWED_GIT_SUBCOMMANDS: frozenset[str] = frozenset({
    "log", "config", "branch", "rev-parse",
})

# ASCII control chars, extremely unlikely to appear in commit subjects.
_RS = "\x1e"  # between commits
_US = "\x1f"  # between fields within a commit header


class GitSafetyError(Exception):
    """Attempted to run a git subcommand not in the allowlist."""


class GitReadError(Exception):
    """Git invocation failed (missing repo, bad ref, git not on PATH, etc.)."""


@dataclass(frozen=True)
class FileChange:
    path: str
    added: int
    removed: int


@dataclass(frozen=True)
class Commit:
    hash: str
    timestamp: datetime
    author_email: str
    subject: str
    repo_key: str
    stack: str
    project: str
    files: tuple[FileChange, ...]


def _run_git(repo_path: Path, subcommand: str, *args: str) -> str:
    """Single entry point for every git call. Enforces the subcommand allowlist."""
    if subcommand not in ALLOWED_GIT_SUBCOMMANDS:
        raise GitSafetyError(
            f"git subcommand {subcommand!r} is not in the allowlist "
            f"{sorted(ALLOWED_GIT_SUBCOMMANDS)}. Refusing to run."
        )

    cmd = ["git", "-C", str(repo_path), subcommand, *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as e:
        raise GitReadError("git executable not found on PATH") from e

    if result.returncode != 0:
        raise GitReadError(
            f"git {subcommand} failed in {repo_path}: {result.stderr.strip()}"
        )
    return result.stdout


def read_commits(repo: RepoConfig) -> list[Commit]:
    """Read this repo's commits by the configured author across all local branches.

    Uses `git log --all --no-merges --author=<email>` plus numstat. Commits
    reachable from multiple branches are deduplicated by hash.
    """
    if not repo.path.exists():
        raise GitReadError(f"Repo path does not exist: {repo.path} (key={repo.key})")

    pretty = f"{_RS}%H{_US}%aI{_US}%ae{_US}%s"
    output = _run_git(
        repo.path,
        "log",
        "--all",
        "--no-merges",
        f"--author={repo.git_email}",
        f"--pretty=format:{pretty}",
        "--numstat",
    )

    commits: dict[str, Commit] = {}
    for record in output.split(_RS):
        record = record.strip("\n")
        if not record:
            continue

        lines = record.split("\n")
        header = lines[0]
        try:
            hash_, iso_ts, author_email, subject = header.split(_US, 3)
        except ValueError:
            # Malformed header — skip rather than crash the whole run.
            continue

        if hash_ in commits:
            continue

        files: list[FileChange] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            added_str, removed_str, path = parts
            # Binary files show "-" instead of a line count.
            added = 0 if added_str == "-" else int(added_str)
            removed = 0 if removed_str == "-" else int(removed_str)
            files.append(FileChange(path=path, added=added, removed=removed))

        commits[hash_] = Commit(
            hash=hash_,
            timestamp=datetime.fromisoformat(iso_ts).astimezone().replace(tzinfo=None),
            author_email=author_email,
            subject=subject,
            repo_key=repo.key,
            stack=repo.stack,
            project=repo.project,
            files=tuple(files),
        )

    return list(commits.values())


def read_all_commits(repos: list[RepoConfig]) -> list[Commit]:
    """Read commits across every configured repo, sorted by timestamp ascending."""
    out: list[Commit] = []
    for repo in repos:
        out.extend(read_commits(repo))
    out.sort(key=lambda c: c.timestamp)
    return out
