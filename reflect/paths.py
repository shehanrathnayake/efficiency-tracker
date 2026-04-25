"""Filesystem layout for reflect.

The data directory (%USERPROFILE%\\.reflect\\ on Windows, ~/.reflect/ elsewhere)
is deliberately kept separate from the installed package so the user can edit
config and log files without touching the install.
"""
from __future__ import annotations

from pathlib import Path

DATA_DIR_NAME = ".reflect"
CONFIG_FILENAME = "config.toml"
LOG_FILENAME = "log.csv"


def data_dir() -> Path:
    return Path.home() / DATA_DIR_NAME


def config_path() -> Path:
    return data_dir() / CONFIG_FILENAME


def log_path() -> Path:
    return data_dir() / LOG_FILENAME
