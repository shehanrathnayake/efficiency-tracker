"""Load and validate config.toml; bootstrap the data directory on first run."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import paths


@dataclass(frozen=True)
class RepoConfig:
    key: str
    path: Path
    stack: str
    project: str
    git_email: str


@dataclass(frozen=True)
class Settings:
    deep_work_min_block_minutes: int = 90
    deep_work_max_interruptions: int = 3
    rework_lookback_days: int = 3
    session_gap_minutes: int = 75
    first_commit_credit_minutes: int = 25


@dataclass(frozen=True)
class Config:
    repos: list[RepoConfig]
    settings: Settings


REQUIRED_REPO_FIELDS: tuple[str, ...] = ("path", "stack", "project", "git_email")


class ConfigError(Exception):
    """Raised when config.toml is missing, malformed, or incomplete."""


SCAFFOLD_CONFIG = """\
# reflect config — edit the repo entries below to match your working directories.
# Each repo needs a unique key (e.g. acme_fe) and the four fields shown.
# Forward slashes work fine on Windows inside TOML strings.

# [repos.acme_fe]
# path = "C:/Users/you/work/acme-frontend"
# stack = "frontend"
# project = "acme"
# git_email = "you@acme.com"

# [repos.acme_be]
# path = "C:/Users/you/work/acme-backend"
# stack = "backend"
# project = "acme"
# git_email = "you@acme.com"

# Optional: override defaults.
# [settings]
# deep_work_min_block_minutes = 90
# deep_work_max_interruptions = 3
# rework_lookback_days = 3
# session_gap_minutes = 75
# first_commit_credit_minutes = 25
"""


def bootstrap_if_missing() -> bool:
    """Ensure the data directory, config file, and log file exist.

    Returns True if anything was created (so the caller can show a first-run
    message), False if everything was already in place.
    """
    created = False

    d = paths.data_dir()
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        created = True

    cfg = paths.config_path()
    if not cfg.exists():
        cfg.write_text(SCAFFOLD_CONFIG, encoding="utf-8")
        created = True

    log = paths.log_path()
    if not log.exists():
        log.touch()
        created = True

    return created


def load() -> Config:
    """Load and validate config.toml. Raises ConfigError with a helpful message if invalid."""
    cfg_path = paths.config_path()
    if not cfg_path.exists():
        raise ConfigError(
            f"Config file not found: {cfg_path}\n"
            f"Run `reflect config` once to bootstrap the data directory, then edit it."
        )

    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)

    repos_raw = raw.get("repos", {})
    if not isinstance(repos_raw, dict) or not repos_raw:
        raise ConfigError(
            f"No repos defined in {cfg_path}. Add at least one [repos.<key>] entry."
        )

    repos: list[RepoConfig] = []
    for key, entry in repos_raw.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"[repos.{key}] must be a table, got {type(entry).__name__}.")
        missing = [f for f in REQUIRED_REPO_FIELDS if f not in entry]
        if missing:
            raise ConfigError(
                f"Repo [repos.{key}] is missing required field(s): {', '.join(missing)}"
            )
        repos.append(
            RepoConfig(
                key=key,
                path=Path(str(entry["path"])),
                stack=str(entry["stack"]),
                project=str(entry["project"]),
                git_email=str(entry["git_email"]),
            )
        )

    settings_raw = raw.get("settings", {}) or {}
    settings = Settings(
        deep_work_min_block_minutes=int(settings_raw.get("deep_work_min_block_minutes", 90)),
        deep_work_max_interruptions=int(settings_raw.get("deep_work_max_interruptions", 3)),
        rework_lookback_days=int(settings_raw.get("rework_lookback_days", 3)),
        session_gap_minutes=int(settings_raw.get("session_gap_minutes", 75)),
        first_commit_credit_minutes=int(settings_raw.get("first_commit_credit_minutes", 25)),
    )

    return Config(repos=repos, settings=settings)
