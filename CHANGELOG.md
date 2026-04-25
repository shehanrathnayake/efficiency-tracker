# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-04-25

### Added
- `reflect log` subcommand for appending entries to `log.csv` directly via the
  `reflect` CLI — no PowerShell profile setup required.
- Category validation against the known set (`meeting`, `testing`, `deepthink`,
  `interrupt`, `review`, `admin`, `merge_event`, `reflect`, `tasks`).
- Optional duration for note-only categories (`tasks`, `reflect`,
  `merge_event`); defaults to `1`.
- Backdating support via `--date` (`today`, `yesterday`, `YYYY-MM-DD`) and
  `--time` (`HH:MM`, 24-hour). `--time` is required whenever `--date` is not
  today.
- CSV-quoting of notes containing commas, quotes, or newlines.

### Changed
- Default start time for new log entries is now `now - duration`, so logging
  right after an activity records the correct start time without typing one.
- Git commit timestamps are normalized to local naive datetimes so day,
  week, and month bucketing matches the user's wall clock instead of UTC.
- README rewritten around the new `reflect log` subcommand, with a
  backdating section and a note that TOML `path` values accept forward
  slashes (`C:/Users/...`) as well as escaped backslashes.

### Removed
- `scripts/log.ps1` and the requirement to dot-source it from `$PROFILE`.
  The Python CLI fully replaces it.

## [0.1.0] - 2026-04-19

### Added
- Initial release.
- Config loader for `%USERPROFILE%\.reflect\config.toml` with multi-repo,
  multi-project, multi-stack support.
- Read-only git reader with a strict subcommand allowlist (`log`, `config`,
  `branch`, `rev-parse`); reads commits across all local branches with
  `git log --all` and deduplicates by hash.
- CSV log reader for `%USERPROFILE%\.reflect\log.csv`.
- Metrics: focused coding time, non-committed focus time, meeting time,
  pre-merge testing time, interruptions, longest session, deep-work day
  flag, first-commit latency, commits per task, stack split, bugfix ratio,
  rework ratio, project switches, stale tasks.
- Task attribution by keyword and file-path overlap against the day's
  `tasks` log entry.
- `rich`-based terminal dashboard with a closing reflection prompt.
- CLI entry point: `reflect today | yesterday | day | week | month | config`.
- First-run bootstrap that scaffolds `%USERPROFILE%\.reflect\` with a
  commented `config.toml`.

[Unreleased]: https://github.com/shehanrathnayake/efficiency-tracker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/shehanrathnayake/efficiency-tracker/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/shehanrathnayake/efficiency-tracker/releases/tag/v0.1.0
