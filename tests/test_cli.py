from pathlib import Path

import pytest

import omapal
from omapal import main, resolve_theme_name


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Omarchy palette manager" in captured.out


def test_no_args_enters_interactive_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(omapal, "interactive_main", lambda: 7)
    assert main([]) == 7


def test_no_interactive_flag_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--no-interactive"])
    assert code == 0
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


def test_set_active_theme_prefers_themes_dir_from_theme_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    current = home / ".config/omarchy/current"
    current_theme = current / "theme"
    source_theme = home / ".config/omarchy/themes/sparta"
    current_theme.mkdir(parents=True)
    source_theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (current / "theme.name").write_text("sparta\n", encoding="utf-8")
    (current_theme / "colors.toml").write_text('background = "#000000"\n', encoding="utf-8")
    source_colors = source_theme / "colors.toml"
    source_colors.write_text('background = "#101010"\n', encoding="utf-8")

    code = main(["set", "background", "#112233"])
    assert code == 0
    assert 'background = "#000000"' in (current_theme / "colors.toml").read_text(encoding="utf-8")
    assert 'background = "#112233"' in source_colors.read_text(encoding="utf-8")


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
    ghostty = theme / "ghostty.conf"
    css = theme / "colors.css"
    aether_override = theme / "aether.override.css"
    gtk = theme / "gtk.css"
    hypr = theme / "hyprland.conf"
    hyprlock = theme / "hyprlock.conf"
    btop = theme / "btop.theme"
    chromium = theme / "chromium.theme"
    neovim = theme / "neovim.lua"
    zed = theme / "aether.zed.json"
    zed_template = tmp_path / "zed-template.json"
    zed_template.write_text(
        "\n".join(
            [
                "{",
                '  "themes": [',
                "    {",
                '      "appearance": "{theme_type}",',
                '      "style": {',
                '        "background": "{background}",',
                '        "editor.foreground": "{foreground}",',
                '        "terminal.ansi.red": "{red}",',
                '        "terminal.ansi.black": "{black}",',
                '        "terminal.ansi.bright_red": "{bright_red}"',
                "      }",
                "    }",
                "  ]",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMAPAL_AETHER_ZED_TEMPLATE", str(zed_template))
    vencord = theme / "vencord.theme.css"
    wofi = theme / "wofi.css"
    warp = theme / "warp.yaml"
    walker = theme / "walker.css"
    mako = theme / "mako.ini"
    swayosd = theme / "swayosd.css"
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
    ghostty.write_text(
        "\n".join(
            [
                "background = #000000",
                "foreground = #ffffff",
                "palette = 0=#121212",
                "palette = 1=#121212",
                "palette = 8=#121212",
                "palette = 9=#121212",
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
    aether_override.write_text(
        "\n".join(
            [
                "@define-color background #000000;",
                "@define-color foreground #ffffff;",
                "@define-color red #121212;",
                "@define-color cyan #121212;",
                "@define-color bright_red #121212;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    gtk.write_text(
        "\n".join(
            [
                "@define-color background #000000;",
                "@define-color foreground #ffffff;",
                "@define-color red #121212;",
                "@define-color cyan #121212;",
                "@define-color bright_red #121212;",
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
    hyprlock.write_text(
        "\n".join(
            [
                "$color = rgba(0, 0, 0, 1)",
                "$inner_color = rgba(0, 0, 0, 0.66)",
                "$outer_color = rgba(18, 18, 18, 1)",
                "$font_color = rgba(255, 255, 255, 1)",
                "$placeholder_color = rgba(255, 255, 255, 0.7)",
                "$check_color = rgba(18, 18, 18, 1)",
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
    neovim.write_text(
        "\n".join(
            [
                "return {",
                "  colors = {",
                '    bg = "#000000",',
                '    fg = "#ffffff",',
                '    red = "#121212",',
                "  },",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zed.write_text(
        "\n".join(
            [
                "{",
                '  "themes": [{',
                '    "style": {',
                '      "background": "#000000",',
                '      "editor.foreground": "#ffffff",',
                '      "terminal.ansi.red": "#121212",',
                '      "terminal.ansi.black": "#121212",',
                '      "terminal.ansi.bright_red": "#121212"',
                "    }",
                "  }]",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    vencord.write_text(
        "\n".join(
            [
                ":root {",
                "  --color00: #121212;",
                "  --color01: #121212;",
                "  --color06: #121212;",
                "  --color09: #121212;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    wofi.write_text(
        "\n".join(
            [
                "@define-color bg #000000;",
                "@define-color fg #ffffff;",
                "@define-color gray1 #121212;",
                "@define-color gray2 #121212;",
                "@define-color gray3 #121212;",
                "@define-color gray4 #121212;",
                "@define-color gray5 #121212;",
                "@define-color fg_bright #121212;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    warp.write_text(
        "\n".join(
            [
                'accent: "#121212"',
                'cursor: "#121212"',
                'background: "#000000"',
                'foreground: "#ffffff"',
                "terminal_colors:",
                "  normal:",
                '    black: "#121212"',
                '    red: "#121212"',
                '    cyan: "#121212"',
                "  bright:",
                '    black: "#121212"',
                '    red: "#121212"',
                '    cyan: "#121212"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    walker.write_text(
        "\n".join(
            [
                "@define-color selected-text #000000;",
                "@define-color text #ffffff;",
                "@define-color base #000000;",
                "@define-color border #121212;",
                "@define-color foreground #ffffff;",
                "@define-color background #000000;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    mako.write_text(
        "\n".join(
            [
                "text-color=#ffffff",
                "border-color=#121212",
                "background-color=#000000",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    swayosd.write_text(
        "\n".join(
            [
                "@define-color background-color #000000;",
                "@define-color border-color #121212;",
                "@define-color label #ffffff;",
                "@define-color image #ffffff;",
                "@define-color progress #121212;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    before_alacritty = alacritty.read_text(encoding="utf-8")
    before_kitty = kitty.read_text(encoding="utf-8")
    before_ghostty = ghostty.read_text(encoding="utf-8")
    before_css = css.read_text(encoding="utf-8")
    before_aether_override = aether_override.read_text(encoding="utf-8")
    before_gtk = gtk.read_text(encoding="utf-8")
    before_hypr = hypr.read_text(encoding="utf-8")
    before_hyprlock = hyprlock.read_text(encoding="utf-8")
    before_btop = btop.read_text(encoding="utf-8")
    before_chromium = chromium.read_text(encoding="utf-8")
    before_neovim = neovim.read_text(encoding="utf-8")
    before_zed = zed.read_text(encoding="utf-8")
    before_vencord = vencord.read_text(encoding="utf-8")
    before_wofi = wofi.read_text(encoding="utf-8")
    before_warp = warp.read_text(encoding="utf-8")
    before_walker = walker.read_text(encoding="utf-8")
    before_mako = mako.read_text(encoding="utf-8")
    before_swayosd = swayosd.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "sync: mode=dry-run theme=active" in captured.out
    assert "alacritty.toml:" in captured.out
    assert "kitty.conf:" in captured.out
    assert "ghostty.conf:" in captured.out
    assert "colors.css:" in captured.out
    assert "aether.override.css:" in captured.out
    assert "gtk.css:" in captured.out
    assert "hyprland.conf:" in captured.out
    assert "hyprlock.conf:" in captured.out
    assert "btop.theme:" in captured.out
    assert "chromium.theme:" in captured.out
    assert "neovim.lua:" in captured.out
    assert "aether.zed.json:" in captured.out
    assert "vencord.theme.css:" in captured.out
    assert "wofi.css:" in captured.out
    assert "warp.yaml:" in captured.out
    assert "walker.css:" in captured.out
    assert "mako.ini:" in captured.out
    assert "swayosd.css:" in captured.out
    assert "total planned changes=" in captured.out

    assert alacritty.read_text(encoding="utf-8") == before_alacritty
    assert kitty.read_text(encoding="utf-8") == before_kitty
    assert ghostty.read_text(encoding="utf-8") == before_ghostty
    assert css.read_text(encoding="utf-8") == before_css
    assert aether_override.read_text(encoding="utf-8") == before_aether_override
    assert gtk.read_text(encoding="utf-8") == before_gtk
    assert hypr.read_text(encoding="utf-8") == before_hypr
    assert hyprlock.read_text(encoding="utf-8") == before_hyprlock
    assert btop.read_text(encoding="utf-8") == before_btop
    assert chromium.read_text(encoding="utf-8") == before_chromium
    assert neovim.read_text(encoding="utf-8") == before_neovim
    assert zed.read_text(encoding="utf-8") == before_zed
    assert vencord.read_text(encoding="utf-8") == before_vencord
    assert wofi.read_text(encoding="utf-8") == before_wofi
    assert warp.read_text(encoding="utf-8") == before_warp
    assert walker.read_text(encoding="utf-8") == before_walker
    assert mako.read_text(encoding="utf-8") == before_mako
    assert swayosd.read_text(encoding="utf-8") == before_swayosd


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


def test_sync_maps_active_border_color_to_hyprland_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('active_border_color = "#112233"\n', encoding="utf-8")
    hypr = theme / "hyprland.conf"
    hypr.write_text(
        "\n".join(
            [
                "$activeBorderColor = rgb(fb6c5b)",
                "general {",
                "  col.active_border = $activeBorderColor",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = hypr.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "hyprland.conf: 1 change(s)" in captured.out
    assert "active_border_color: #fb6c5b -> #112233" in captured.out
    assert hypr.read_text(encoding="utf-8") == before


def test_sync_maps_accent_to_css_define_color(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('accent = "#fb6c5b"\n', encoding="utf-8")
    css = theme / "colors.css"
    css.write_text("@define-color accent #fba66a;\n", encoding="utf-8")
    before = css.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "colors.css: 1 change(s)" in captured.out
    assert "accent: #fba66a -> #fb6c5b" in captured.out
    assert css.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_neovim_lua(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color1 = "#f93e2e"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    neovim = theme / "neovim.lua"
    neovim.write_text(
        "\n".join(
            [
                "return {",
                "  colors = {",
                '    bg = "#000000",',
                '    fg = "#ffffff",',
                '    red = "#111111",',
                "  },",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = neovim.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "neovim.lua: 3 change(s)" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color1: #111111 -> #f93e2e" in captured.out
    assert neovim.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_walker_waybar_mako_and_swayosd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'accent = "#fb6c5b"',
                'foreground = "#d2b476"',
                'background = "#171212"',
                'color8 = "#9d7b7b"',
                'color5 = "#fba66a"',
                'color3 = "#fbc95c"',
                'active_border_color = "#f93e2e"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (theme / "walker.css").write_text(
        "@define-color selected-text #000000;\n@define-color text #ffffff;\n", encoding="utf-8"
    )
    (theme / "mako.ini").write_text(
        "text-color=#ffffff\nborder-color=#000000\nbackground-color=#000000\n", encoding="utf-8"
    )
    (theme / "waybar.css").write_text(
        "\n".join(
            [
                "@define-color background #000000;",
                "@define-color foreground #ffffff;",
                "@define-color accent #111111;",
                "@define-color active_border_color #222222;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (theme / "swayosd.css").write_text(
        "@define-color progress #000000;\n@define-color label #ffffff;\n", encoding="utf-8"
    )

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "walker.css: 2 change(s)" in captured.out
    assert "mako.ini: 3 change(s)" in captured.out
    assert "waybar.css: 4 change(s)" in captured.out
    assert "swayosd.css: 2 change(s)" in captured.out


def test_sync_maps_colors_to_ghostty_conf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color0 = "#171212"',
                'color1 = "#f93e2e"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ghostty = theme / "ghostty.conf"
    ghostty.write_text(
        "\n".join(
            [
                "background = #000000",
                "foreground = #ffffff",
                "palette = 0=#000000",
                "palette = 1=#111111",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = ghostty.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "ghostty.conf: 4 change(s)" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color1: #111111 -> #f93e2e" in captured.out
    assert ghostty.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_hyprlock_conf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color5 = "#fba66a"',
                'color6 = "#f0a80f"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hyprlock = theme / "hyprlock.conf"
    hyprlock.write_text(
        "\n".join(
            [
                "$color = rgba(0, 0, 0, 1)",
                "$inner_color = rgba(0, 0, 0, 0.66)",
                "$outer_color = rgba(18, 18, 18, 1)",
                "$font_color = rgba(255, 255, 255, 1)",
                "$placeholder_color = rgba(255, 255, 255, 0.7)",
                "$check_color = rgba(18, 18, 18, 1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = hyprlock.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "hyprlock.conf: 6 change(s)" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color5: #121212 -> #fba66a" in captured.out
    assert "color6: #121212 -> #f0a80f" in captured.out
    assert hyprlock.read_text(encoding="utf-8") == before


def test_sync_write_does_not_add_blank_lines_to_ghostty_or_colors_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'color1 = "#f93e2e"',
                'color6 = "#f0a80f"',
                'color9 = "#ff8e84"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ghostty = theme / "ghostty.conf"
    ghostty.write_text(
        "\n".join(
            [
                "palette = 1=#111111",
                "palette = 6=#222222",
                "palette = 9=#333333",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    css = theme / "colors.css"
    css.write_text(
        "\n".join(
            [
                "@define-color color1 #111111;",
                "@define-color color6 #222222;",
                "@define-color color9 #333333;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    code = main(["sync", "-w", "--no-reload"])
    assert code == 0

    ghostty_text = ghostty.read_text(encoding="utf-8")
    css_text = css.read_text(encoding="utf-8")
    assert "\n\n" not in ghostty_text
    assert "\n\n" not in css_text


def test_sync_maps_colors_to_gtk_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color1 = "#f93e2e"',
                'color6 = "#f0a80f"',
                'color9 = "#ff8e84"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    gtk = theme / "gtk.css"
    gtk.write_text(
        "\n".join(
            [
                "@define-color background #000000;",
                "@define-color foreground #ffffff;",
                "@define-color red #111111;",
                "@define-color cyan #222222;",
                "@define-color bright_red #333333;",
                "@define-color accent_bg_color @blue;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = gtk.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "gtk.css: 5 change(s)" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color1: #111111 -> #f93e2e" in captured.out
    assert "color6: #222222 -> #f0a80f" in captured.out
    assert "color9: #333333 -> #ff8e84" in captured.out
    assert gtk.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_vencord_theme_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'color1 = "#f93e2e"',
                'color6 = "#f0a80f"',
                'color9 = "#ff8e84"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    vencord = theme / "vencord.theme.css"
    vencord.write_text(
        "\n".join(
            [
                ":root {",
                "  --color01: #111111;",
                "  --color06: #222222;",
                "  --color09: #333333;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = vencord.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "vencord.theme.css: 3 change(s)" in captured.out
    assert "color1: #111111 -> #f93e2e" in captured.out
    assert "color6: #222222 -> #f0a80f" in captured.out
    assert "color9: #333333 -> #ff8e84" in captured.out
    assert vencord.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_wofi_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color2 = "#ec9a4e"',
                'color8 = "#9d7b7b"',
                'color4 = "#fb6c5b"',
                'color3 = "#fbc95c"',
                'color5 = "#fba66a"',
                'color15 = "#fae084"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    wofi = theme / "wofi.css"
    wofi.write_text(
        "\n".join(
            [
                "@define-color bg #000000;",
                "@define-color fg #ffffff;",
                "@define-color gray1 #111111;",
                "@define-color gray2 #222222;",
                "@define-color gray3 #333333;",
                "@define-color gray4 #444444;",
                "@define-color gray5 #555555;",
                "@define-color fg_bright #666666;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = wofi.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "wofi.css: 8 change(s)" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color2: #111111 -> #ec9a4e" in captured.out
    assert "color8: #222222 -> #9d7b7b" in captured.out
    assert "color4: #333333 -> #fb6c5b" in captured.out
    assert "color3: #444444 -> #fbc95c" in captured.out
    assert "color5: #555555 -> #fba66a" in captured.out
    assert "color15: #666666 -> #fae084" in captured.out
    assert wofi.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_warp_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'accent = "#fb6c5b"',
                'cursor = "#d2b476"',
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color0 = "#171212"',
                'color1 = "#f93e2e"',
                'color6 = "#f0a80f"',
                'color8 = "#9d7b7b"',
                'color9 = "#ff8e84"',
                'color14 = "#f8b62c"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    warp = theme / "warp.yaml"
    warp.write_text(
        "\n".join(
            [
                'accent: "#111111"',
                'cursor: "#111111"',
                'background: "#000000"',
                'foreground: "#ffffff"',
                "terminal_colors:",
                "  normal:",
                '    black: "#222222"',
                '    red: "#222222"',
                '    cyan: "#222222"',
                "  bright:",
                '    black: "#333333"',
                '    red: "#333333"',
                '    cyan: "#333333"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = warp.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "warp.yaml: 10 change(s)" in captured.out
    assert "accent: #111111 -> #fb6c5b" in captured.out
    assert "cursor: #111111 -> #d2b476" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color0: #222222 -> #171212" in captured.out
    assert "color1: #222222 -> #f93e2e" in captured.out
    assert "color6: #222222 -> #f0a80f" in captured.out
    assert "color8: #333333 -> #9d7b7b" in captured.out
    assert "color9: #333333 -> #ff8e84" in captured.out
    assert "color14: #333333 -> #f8b62c" in captured.out
    assert warp.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_aether_override_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color1 = "#f93e2e"',
                'color6 = "#f0a80f"',
                'color9 = "#ff8e84"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    override_css = theme / "aether.override.css"
    override_css.write_text(
        "\n".join(
            [
                "@define-color background #000000;",
                "@define-color foreground #ffffff;",
                "@define-color red #111111;",
                "@define-color cyan #222222;",
                "@define-color bright_red #333333;",
                "@define-color accent_color @cyan;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = override_css.read_text(encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "aether.override.css: 5 change(s)" in captured.out
    assert "background: #000000 -> #171212" in captured.out
    assert "foreground: #ffffff -> #d2b476" in captured.out
    assert "color1: #111111 -> #f93e2e" in captured.out
    assert "color6: #222222 -> #f0a80f" in captured.out
    assert "color9: #333333 -> #ff8e84" in captured.out
    assert override_css.read_text(encoding="utf-8") == before


def test_sync_maps_colors_to_aether_zed_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text(
        "\n".join(
            [
                'background = "#171212"',
                'foreground = "#d2b476"',
                'color1 = "#f93e2e"',
                'color6 = "#f0a80f"',
                'color9 = "#ff8e84"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zed_template = tmp_path / "zed-template.json"
    zed_template.write_text(
        "\n".join(
            [
                "{",
                '  "themes": [',
                "    {",
                '      "appearance": "{theme_type}",',
                '      "style": {',
                '        "background": "{background}",',
                '        "editor.foreground": "{foreground}",',
                '        "terminal.ansi.red": "{red}",',
                '        "terminal.ansi.cyan": "{cyan}",',
                '        "terminal.ansi.bright_red": "{bright_red}"',
                "      }",
                "    }",
                "  ]",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zed = theme / "aether.zed.json"
    zed.write_text(
        "\n".join(
            [
                "{",
                '  "themes": [{',
                '    "style": {',
                '      "background": "#000000",',
                '      "editor.foreground": "#ffffff",',
                '      "terminal.ansi.red": "#111111",',
                '      "terminal.ansi.cyan": "#222222",',
                '      "terminal.ansi.bright_red": "#333333"',
                "    }",
                "  }]",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    before = zed.read_text(encoding="utf-8")

    code = main(["sync", "--zed-template", str(zed_template)])
    assert code == 0
    captured = capsys.readouterr()
    assert "aether.zed.json: 5 change(s)" in captured.out
    assert "themes[0].style.background: #000000 -> #171212" in captured.out
    assert "themes[0].style.editor.foreground: #ffffff -> #d2b476" in captured.out
    assert "themes[0].style.terminal.ansi.red: #111111 -> #f93e2e" in captured.out
    assert "themes[0].style.terminal.ansi.cyan: #222222 -> #f0a80f" in captured.out
    assert "themes[0].style.terminal.ansi.bright_red: #333333 -> #ff8e84" in captured.out
    assert zed.read_text(encoding="utf-8") == before


def test_sync_uses_env_zed_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#171212"\n', encoding="utf-8")
    zed_template = tmp_path / "zed-template-env.json"
    zed_template.write_text('{"style":{"background":"{background}"}}\n', encoding="utf-8")
    monkeypatch.setenv("OMAPAL_AETHER_ZED_TEMPLATE", str(zed_template))

    zed = theme / "aether.zed.json"
    zed.write_text('{"style":{"background":"#000000"}}\n', encoding="utf-8")

    code = main(["sync"])
    assert code == 0
    captured = capsys.readouterr()
    assert "aether.zed.json: 1 change(s)" in captured.out
    assert "style.background: #000000 -> #171212" in captured.out


def test_sync_zed_template_cli_override_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#171212"\n', encoding="utf-8")
    env_template = tmp_path / "zed-template-env.json"
    env_template.write_text('{"style":{"background":"#abcdef"}}\n', encoding="utf-8")
    cli_template = tmp_path / "zed-template-cli.json"
    cli_template.write_text('{"style":{"background":"{background}"}}\n', encoding="utf-8")
    monkeypatch.setenv("OMAPAL_AETHER_ZED_TEMPLATE", str(env_template))

    zed = theme / "aether.zed.json"
    zed.write_text('{"style":{"background":"#000000"}}\n', encoding="utf-8")

    code = main(["sync", "--zed-template", str(cli_template), "-w", "--no-reload"])
    assert code == 0
    updated = zed.read_text(encoding="utf-8")
    assert '"#171212"' in updated
    assert '"#abcdef"' not in updated


def test_sync_fails_when_zed_template_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    theme = home / ".config/omarchy/current/theme"
    theme.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    (theme / "colors.toml").write_text('background = "#171212"\n', encoding="utf-8")
    (theme / "aether.zed.json").write_text('{"style":{"background":"#000000"}}\n', encoding="utf-8")
    monkeypatch.setenv("OMAPAL_AETHER_ZED_TEMPLATE", str(tmp_path / "missing-template.json"))

    code = main(["sync"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Zed template not found" in captured.err


def test_resolve_theme_name_uses_logical_theme_dir_name_for_symlinked_theme() -> None:
    theme_dir = Path("/home/user/.config/omarchy/themes/sparta")
    assert resolve_theme_name(None, theme_dir) == "sparta"
