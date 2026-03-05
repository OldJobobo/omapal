from pathlib import Path

import pytest

import omapal
from omapal import main


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Omarchy palette manager" in captured.out


def test_set_rejects_invalid_hex(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["set", "background", "#12"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Invalid color" in captured.err


def test_show_reads_active_theme_colors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    (theme / "colors.toml").write_text('background = "#101010"\nforeground = "#f0f0f0"\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    code = main(["show"])
    assert code == 0
    captured = capsys.readouterr()
    assert "background=#101010" in captured.out
    assert "foreground=#f0f0f0" in captured.out


def test_set_updates_token_in_active_theme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    colors = theme / "colors.toml"
    colors.write_text('background = "#000000"\nforeground = "#ffffff"\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    code = main(["set", "background", "#112233"])
    assert code == 0
    text = colors.read_text(encoding="utf-8")
    assert 'background = "#112233"' in text
    assert 'foreground = "#ffffff"' in text


def test_show_missing_theme_dir_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    code = main(["show"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Theme directory not found" in captured.err


def test_show_invalid_toml_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    (theme / "colors.toml").write_text("background = \n", encoding="utf-8")

    code = main(["show"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Invalid TOML" in captured.err


def test_show_invalid_color_value_in_colors_toml_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    (theme / "colors.toml").write_text('background = "not-a-color"\n', encoding="utf-8")

    code = main(["show"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Invalid color" in captured.err


def test_sync_dry_run_reports_changes_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#101010"',
                'foreground = "#f0f0f0"',
                'cursor = "#bbbbbb"',
                'selection_background = "#333333"',
                'selection_foreground = "#ffffff"',
                'color0 = "#000000"',
                'color1 = "#111111"',
                'color8 = "#888888"',
                'color9 = "#999999"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    alacritty = theme / "alacritty.toml"
    kitty = theme / "kitty.conf"
    css = theme / "colors.css"
    hypr = theme / "hyprland.conf"
    btop = theme / "btop.theme"
    chromium = theme / "chromium.theme"
    alacritty.write_text(
        "\n".join(
            [
                "[colors.primary]",
                'background = "#000000"',
                'foreground = "#ffffff"',
                "",
                "[colors.cursor]",
                'cursor = "#000000"',
                "",
                "[colors.selection]",
                'background = "#000000"',
                'text = "#000000"',
                "",
                "[colors.normal]",
                'black = "#121212"',
                'red = "#121212"',
                "",
                "[colors.bright]",
                'black = "#121212"',
                'red = "#121212"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    kitty.write_text(
        "\n".join(
            [
                "background #000000",
                "foreground #ffffff",
                "cursor #000000",
                "selection_background #000000",
                "selection_foreground #000000",
                "color0 #121212",
                "color1 #121212",
                "color8 #121212",
                "color9 #121212",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    css.write_text(
        "\n".join(
            [
                ":root {",
                "  --background: #000000;",
                "  --foreground: #ffffff;",
                "  --cursor: #000000;",
                "  --selection-background: #000000;",
                "  --selection-foreground: #000000;",
                "  --color0: #121212;",
                "  --color1: #121212;",
                "  --color8: #121212;",
                "  --color9: #121212;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hypr.write_text(
        "\n".join(
            [
                "$background = #000000",
                "$foreground = #ffffff",
                "$accent = #000000",
                "$color0 = #121212",
                "$color1 = #121212",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    btop.write_text(
        "\n".join(
            [
                'theme[main_bg] = "#000000"',
                'theme[main_fg] = "#ffffff"',
                'theme[title] = "#000000"',
                'theme[selected_bg] = "#000000"',
                'theme[selected_fg] = "#000000"',
                'theme[inactive_fg] = "#121212"',
                'theme[hi_fg] = "#121212"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    chromium.write_text(
        "\n".join(
            [
                "{",
                '  "background": "#000000",',
                '  "foreground": "#ffffff",',
                '  "accent": "#000000",',
                '  "selection_background": "#000000",',
                '  "selection_foreground": "#000000",',
                '  "color0": "#121212",',
                '  "color1": "#121212"',
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    before_alacritty = alacritty.read_text(encoding="utf-8")
    before_kitty = kitty.read_text(encoding="utf-8")
    before_css = css.read_text(encoding="utf-8")
    before_hypr = hypr.read_text(encoding="utf-8")
    before_btop = btop.read_text(encoding="utf-8")
    before_chromium = chromium.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "sync: mode=dry-run theme=active" in captured.out
    assert "alacritty.toml:" in captured.out
    assert "kitty.conf:" in captured.out
    assert "colors.css:" in captured.out
    assert "hyprland.conf:" in captured.out
    assert "btop.theme:" in captured.out
    assert "chromium.theme:" in captured.out
    assert "total planned changes=" in captured.out

    assert alacritty.read_text(encoding="utf-8") == before_alacritty
    assert kitty.read_text(encoding="utf-8") == before_kitty
    assert css.read_text(encoding="utf-8") == before_css
    assert hypr.read_text(encoding="utf-8") == before_hypr
    assert btop.read_text(encoding="utf-8") == before_btop
    assert chromium.read_text(encoding="utf-8") == before_chromium


def test_sync_conflicting_flags_returns_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["sync", "--dry-run", "--write"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Use either --dry-run or --write" in captured.err


def test_sync_returns_error_when_target_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#101010"\n', encoding="utf-8")
    (theme / "kitty.conf").mkdir()

    code = main(["sync"])
    assert code == 2
    captured = capsys.readouterr()
    assert "kitty.conf: error" in captured.out
    assert "encountered 1 error(s)" in captured.err


def test_sync_write_updates_files_and_creates_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#101010"',
                'foreground = "#f0f0f0"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    alacritty = theme / "alacritty.toml"
    alacritty.write_text(
        "\n".join(
            [
                "[colors.primary]",
                'background = "#000000"',
                'foreground = "#ffffff"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = alacritty.read_text(encoding="utf-8")

    code = main(["sync", "--write", "--no-reload"])
    assert code == 0
    captured = capsys.readouterr()
    assert "sync: mode=write theme=active" in captured.out
    assert "sync: wrote 1 file(s)" in captured.out

    after = alacritty.read_text(encoding="utf-8")
    assert after != before
    assert 'background = "#101010"' in after
    assert 'foreground = "#f0f0f0"' in after

    backup_root = theme / ".palette-backup"
    backup_dirs = [p for p in backup_root.iterdir() if p.is_dir()]
    assert len(backup_dirs) == 1
    backup_file = backup_dirs[0] / "alacritty.toml"
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == before


def test_diff_reports_planned_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#101010"\nforeground = "#f0f0f0"\n', encoding="utf-8")
    (theme / "alacritty.toml").write_text(
        "[colors.primary]\nbackground = \"#000000\"\nforeground = \"#ffffff\"\n", encoding="utf-8"
    )

    code = main(["diff"])
    assert code == 0
    captured = capsys.readouterr()
    assert "diff: theme=active" in captured.out
    assert "alacritty.toml: 2 change(s)" in captured.out
    assert "diff: total changes=2" in captured.out


def test_sync_write_auto_reload_uses_hypr_for_hypr_only_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#101010"\n', encoding="utf-8")
    (theme / "hyprland.conf").write_text("$background = #000000\n", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool) -> None:
        _ = (check, capture_output, text)
        calls.append(cmd)
        return None

    monkeypatch.setattr(omapal.subprocess, "run", fake_run)
    code = main(["sync", "--write"])
    assert code == 0
    assert calls == [["hyprctl", "reload"]]


def test_sync_write_auto_reload_uses_full_for_named_theme_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/themes/mytheme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#101010"\nforeground = "#f0f0f0"\n', encoding="utf-8")
    (theme / "alacritty.toml").write_text(
        "[colors.primary]\nbackground = \"#000000\"\nforeground = \"#ffffff\"\n", encoding="utf-8"
    )

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool) -> None:
        _ = (check, capture_output, text)
        calls.append(cmd)
        return None

    monkeypatch.setattr(omapal.subprocess, "run", fake_run)
    code = main(["sync", "--theme", "mytheme", "--write"])
    assert code == 0
    assert calls == [["omarchy-theme-set", "mytheme"]]


def test_sync_write_reload_failure_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    (theme / "colors.toml").write_text('background = "#101010"\n', encoding="utf-8")
    (theme / "hyprland.conf").write_text("$background = #000000\n", encoding="utf-8")

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool) -> None:
        _ = (cmd, check, capture_output, text)
        raise FileNotFoundError("missing")

    monkeypatch.setattr(omapal.subprocess, "run", fake_run)
    code = main(["sync", "--write"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Reload command not found" in captured.err
