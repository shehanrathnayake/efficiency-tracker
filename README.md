# reflect

A personal self-reflection tool. Reads local git repositories and a simple
manual time-log, prints a daily (or weekly/monthly) dashboard in the terminal,
and ends each day with one reflection question drawn from whatever stood out
in the numbers.

This is a solo tool for a single engineer. It is **not** a productivity score
generator, a team tool, or a dashboard for anyone else. See `CLAUDE.md` for
the full design brief, especially the design principle and negative roadmap.

---

## Install

Requires Python 3.13+.

```powershell
cd C:\path\to\efficiency-tracker
pip install -e .
```

That installs the `reflect` command on your PATH.

## First run

```powershell
reflect config
```

This creates `%USERPROFILE%\.reflect\` with a scaffold `config.toml` and an
empty `log.csv`. Open `config.toml` and add your repos:

```toml
[repos.acme_fe]
path = "C:/Users/you/work/acme-frontend"
stack = "frontend"
project = "acme"
git_email = "you@acme.com"

[repos.acme_be]
path = "C:/Users/you/work/acme-backend"
stack = "backend"
project = "acme"
git_email = "you@acme.com"
```

Then run `reflect config` again to verify: every repo should show a `✓`.

## Daily use

```powershell
reflect today
reflect yesterday
reflect day 2026-04-22
reflect week                # current ISO week
reflect week 2026-17
reflect month               # current month
reflect month 2026-04
```

## Logging time

Dot-source the PowerShell helper from your profile so `log` is available in
every session:

```powershell
. C:\path\to\efficiency-tracker\scripts\log.ps1
```

(Open your profile with `notepad $PROFILE`. Create the file if it doesn't
exist yet.)

Then during the day:

```powershell
log meeting 30 "standup"
log testing 90 "pre-merge with M"
log interrupt 15 "slack thread"
log deepthink 45 "design sketch for billing flow"
log merge_event 0 "merged bank details to staging"
log tasks "bank details crud, login fix, dashboard prep"
log reflect "rework spike was from yesterday's testing catches"
```

Categories: `meeting`, `testing`, `deepthink`, `interrupt`, `review`, `admin`,
`merge_event`, `reflect`, `tasks`.

For `tasks` and `reflect` you can omit the duration (it defaults to 1):

```powershell
log tasks "bank details crud, login fix"
log reflect "good flow after lunch"
```

End-of-day ritual: run `log tasks "..."` with the tasks you actually worked
on. The dashboard uses that list to attribute commits.

## Safety guarantees

This tool is **read-only** against your git repos. From `CLAUDE.md §6`:

- All git calls funnel through one wrapper with a hard-coded allowlist:
  `log`, `config`, `branch`, `rev-parse`. Any other subcommand raises before
  git is invoked.
- Every git call uses `git -C <repo>`; the working directory is never changed.
- No network calls. No remote fetches, pushes, or telemetry.

## Layout

```
reflect/
  config.py        load + validate config.toml, bootstrap ~/.reflect/
  git_reader.py    whitelisted git wrapper, commit parsing (safety-critical)
  log_reader.py    parse log.csv
  classify.py      first-word commit categorization
  sessions.py      cluster commits into coding sessions
  attribution.py   match commits to end-of-day task list
  metrics.py       the 14 daily metrics + weekly/monthly aggregation
  dashboard.py     rich-based terminal rendering + reflection prompt
  cli.py           argparse entry point
  paths.py         resolves %USERPROFILE%\.reflect\
scripts/
  log.ps1          PowerShell `log` function to append CSV rows
CLAUDE.md          full design brief — read this before changing anything
```

## Reading the dashboard

Every number is a prompt, not a target (see `CLAUDE.md §1`). Neutral markers
(`✓`, `⚠`, `—`) instead of judgment emoji. Estimated values prefixed with
`~`. The daily view ends with one reflection question picked from whatever
stood out — a stale task, a bugfix spike, a long deep-work block, etc.

If a number surprises you, that's the signal. Not the number itself.
