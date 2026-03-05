from pathlib import Path

import pytest

from validators import is_valid_hex_color, is_valid_token, validate_theme_dir


def test_valid_token() -> None:
    assert is_valid_token("background")
    assert is_valid_token("color15")
    assert not is_valid_token("bogus_token")


def test_valid_hex_color() -> None:
    assert is_valid_hex_color("#a1b2c3")
    assert is_valid_hex_color("#A1B2C3")
    assert not is_valid_hex_color("a1b2c3")
    assert not is_valid_hex_color("#abcd")


def test_validate_theme_dir_allows_supported_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    current = home / ".config/omarchy/current/theme"
    named = home / ".config/omarchy/themes/my-theme"
    current.mkdir(parents=True)
    named.mkdir(parents=True)
    validate_theme_dir(current, home)
    validate_theme_dir(named, home)


def test_validate_theme_dir_blocks_other_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "etc/theme"
    outside.mkdir(parents=True)
    with pytest.raises(ValueError):
        validate_theme_dir(outside, home)
