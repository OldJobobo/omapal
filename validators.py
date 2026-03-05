"""Validation helpers for palette tokens and color values."""

from __future__ import annotations

import re
from pathlib import Path

from mappings import CANONICAL_TOKENS

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def is_valid_token(token: str) -> bool:
    return token in CANONICAL_TOKENS


def is_valid_hex_color(value: str) -> bool:
    return bool(HEX_COLOR_RE.fullmatch(value))


def validate_token(token: str) -> None:
    if not is_valid_token(token):
        raise ValueError(f"Invalid token '{token}'.")


def validate_hex_color(value: str) -> None:
    if not is_valid_hex_color(value):
        raise ValueError(f"Invalid color '{value}'. Use #RRGGBB format.")


def validate_theme_dir(path: Path, home: Path) -> None:
    current_theme_root = (home / ".config/omarchy/current/theme").resolve()
    named_themes_root = (home / ".config/omarchy/themes").resolve()
    raw = path.expanduser().absolute()
    resolved = path.resolve()

    raw_in_current_root = raw == current_theme_root or current_theme_root in raw.parents
    raw_in_named_root = raw == named_themes_root or named_themes_root in raw.parents
    if raw_in_current_root or raw_in_named_root:
        return

    in_current_root = resolved == current_theme_root or current_theme_root in resolved.parents
    in_named_root = resolved == named_themes_root or named_themes_root in resolved.parents
    if not (in_current_root or in_named_root):
        raise ValueError(f"Unsafe theme path '{resolved}'. Refusing to operate outside theme dirs.")
