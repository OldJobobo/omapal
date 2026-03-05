"""CLI entrypoint for omapal."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mappings import (
    AETHER_OVERRIDE_CSS_COLOR_MAP,
    ALACRITTY_FIELD_MAP,
    BTOP_FIELD_MAP,
    CANONICAL_TOKENS,
    CHROMIUM_FIELD_MAP,
    CSS_DEFINE_COLOR_MAP,
    CSS_VARIABLE_MAP,
    HYPRLAND_FIELD_MAP,
    HYPRLOCK_FIELD_MAP,
    KITTY_FIELD_MAP,
    MAKO_INI_COLOR_MAP,
    GHOSTTY_FIELD_MAP,
    GTK_CSS_COLOR_MAP,
    NEOVIM_LUA_COLOR_MAP,
    SWAYOSD_CSS_COLOR_MAP,
    SYNC_TARGET_FILES,
    VENCORD_CSS_COLOR_MAP,
    WARP_YAML_COLOR_MAP,
    WALKER_CSS_COLOR_MAP,
    WAYBAR_CSS_COLOR_MAP,
    WOFI_CSS_COLOR_MAP,
)
from validators import validate_hex_color, validate_theme_dir, validate_token
from writers import atomic_write, backup_file

DEFAULT_AETHER_ZED_TEMPLATE = Path(__file__).resolve().parent / "templates" / "aether.zed.json"
ENV_AETHER_ZED_TEMPLATE = "OMAPAL_AETHER_ZED_TEMPLATE"
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
TEMPLATE_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omapal", description="Omarchy palette manager")
    parser.add_argument("--no-interactive", action="store_true", help="Disable interactive mode")
    subparsers = parser.add_subparsers(dest="command", required=False)

    show_parser = subparsers.add_parser("show", help="Show palette values")
    show_parser.add_argument("--theme", help="Theme name override")
    show_parser.set_defaults(func=cmd_show)

    set_parser = subparsers.add_parser("set", help="Set a token value")
    set_parser.add_argument("token", help="Canonical token to set")
    set_parser.add_argument("value", help="Hex color in #RRGGBB")
    set_parser.add_argument("--theme", help="Theme name override")
    set_parser.set_defaults(func=cmd_set)

    sync_parser = subparsers.add_parser("sync", help="Sync colors.toml to target files")
    sync_parser.add_argument("--theme", help="Theme name override")
    sync_parser.add_argument("--dry-run", action="store_true", help="Show planned changes only")
    sync_parser.add_argument("-w", "--write", action="store_true", help="Apply changes")
    sync_parser.add_argument("--zed-template", help="Path to aether.zed.json template override")
    sync_parser.add_argument(
        "--reload-mode",
        choices=("auto", "full", "hypr"),
        default="auto",
        help="Reload strategy after --write (default: auto)",
    )
    sync_parser.add_argument("--no-reload", action="store_true", help="Skip reload after --write")
    sync_parser.set_defaults(func=cmd_sync)

    diff_parser = subparsers.add_parser("diff", help="Show out-of-sync changes")
    diff_parser.add_argument("--theme", help="Theme name override")
    diff_parser.add_argument("--zed-template", help="Path to aether.zed.json template override")
    diff_parser.set_defaults(func=cmd_diff)

    return parser


def cmd_show(args: argparse.Namespace) -> int:
    theme_dir = resolve_theme_dir(args.theme)
    colors = read_colors_toml(theme_dir / "colors.toml")
    for token in CANONICAL_TOKENS:
        if token in colors:
            print(f"{token}={colors[token]}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    theme_dir = resolve_theme_dir(args.theme)
    validate_token(args.token)
    validate_hex_color(args.value)
    colors_toml = theme_dir / "colors.toml"
    _ = read_colors_toml(colors_toml)
    update_colors_toml(colors_toml, args.token, args.value)
    print(f"set: updated {args.token}={args.value} in {colors_toml}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    return run_sync(
        theme=args.theme,
        write=args.write,
        dry_run=args.dry_run,
        zed_template=args.zed_template,
        reload_mode=args.reload_mode,
        no_reload=args.no_reload,
        reporter=print,
        err_reporter=lambda msg: print(msg, file=sys.stderr),
    )


def run_sync(
    theme: str | None,
    write: bool,
    dry_run: bool,
    zed_template: str | None,
    reload_mode: str,
    no_reload: bool,
    reporter: callable,
    err_reporter: callable,
) -> int:
    if dry_run and write:
        raise ValueError("Use either --dry-run or --write, not both.")

    theme_dir = resolve_theme_dir(theme)
    colors = read_colors_toml(theme_dir / "colors.toml")
    zed_template_path = resolve_zed_template_path(zed_template) if zed_template else None
    plans = build_sync_plan(theme_dir, colors, zed_template_path=zed_template_path)
    mode = "write" if write else "dry-run"

    reporter(f"sync: mode={mode} theme={theme or 'active'}")
    total_changes, write_candidates, error_count = print_plan_results(plans, reporter=reporter)

    if write and write_candidates:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = theme_dir / ".palette-backup" / timestamp
        for plan in write_candidates:
            if plan.updated_content is None:
                continue
            backup_file(plan.path, backup_root)
            atomic_write(plan.path, plan.updated_content)
        reporter(f"sync: wrote {len(write_candidates)} file(s)")
        reporter(f"sync: backups at {backup_root}")
        if not no_reload:
            changed_files = [plan.path.name for plan in write_candidates]
            reload_cmd = build_reload_command(reload_mode, changed_files, theme, theme_dir)
            run_reload_command(reload_cmd)
            reporter(f"sync: reload command={' '.join(reload_cmd)}")

    reporter(f"sync: total planned changes={total_changes}")
    if error_count:
        err_reporter(f"sync: encountered {error_count} error(s)")
        return 2
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    return run_diff(
        args.theme,
        zed_template=args.zed_template,
        reporter=print,
        err_reporter=lambda msg: print(msg, file=sys.stderr),
    )


def run_diff(theme: str | None, zed_template: str | None, reporter: callable, err_reporter: callable) -> int:
    theme_dir = resolve_theme_dir(theme)
    colors = read_colors_toml(theme_dir / "colors.toml")
    zed_template_path = resolve_zed_template_path(zed_template) if zed_template else None
    plans = build_sync_plan(theme_dir, colors, zed_template_path=zed_template_path)

    reporter(f"diff: theme={theme or 'active'}")
    total_changes, _, error_count = print_plan_results(plans, reporter=reporter)
    reporter(f"diff: total changes={total_changes}")
    if error_count:
        err_reporter(f"diff: encountered {error_count} error(s)")
        return 2
    return 0


def resolve_theme_dir(theme_name: str | None) -> Path:
    home = Path.home()
    if theme_name:
        target = home / ".config/omarchy/themes" / theme_name
    else:
        target = resolve_active_theme_source_dir(home)
    validate_theme_dir(target, home)
    if not target.exists():
        raise ValueError(f"Theme directory not found: {target}")
    if not target.is_dir():
        raise ValueError(f"Theme path is not a directory: {target}")
    return target


def resolve_active_theme_source_dir(home: Path) -> Path:
    themes_root = home / ".config/omarchy/themes"
    current_root = home / ".config/omarchy/current"
    theme_name_file = current_root / "theme.name"
    if theme_name_file.exists():
        try:
            theme_name = theme_name_file.read_text(encoding="utf-8").strip()
        except OSError:
            theme_name = ""
        if theme_name:
            source_dir = themes_root / theme_name
            if source_dir.exists() and source_dir.is_dir():
                return source_dir
    current_theme = current_root / "theme"
    if current_theme.is_symlink():
        try:
            resolved = current_theme.resolve()
        except OSError:
            resolved = current_theme
        if resolved.exists() and resolved.is_dir():
            return resolved
    return current_theme


def read_colors_toml(path: Path) -> dict[str, str]:
    if not path.exists():
        raise ValueError(f"colors.toml not found: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as err:
        raise ValueError(f"Invalid TOML in {path}: {err}") from err
    except OSError as err:
        raise ValueError(f"Failed to read {path}: {err}") from err

    colors: dict[str, str] = {}
    for token in CANONICAL_TOKENS:
        value = find_token_value(data, token)
        if isinstance(value, str):
            validate_hex_color(value)
            colors[token] = value
    return colors


def find_token_value(data: object, token: str) -> object | None:
    if not isinstance(data, dict):
        return None
    if token in data:
        return data[token]
    for value in data.values():
        if isinstance(value, dict):
            nested = find_token_value(value, token)
            if nested is not None:
                return nested
    return None


def update_colors_toml(path: Path, token: str, value: str) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as err:
        raise ValueError(f"Failed to read {path}: {err}") from err
    line_re = re.compile(rf"^(\s*{re.escape(token)}\s*=\s*)(['\"]).*?\2(\s*(?:#.*)?)$", re.MULTILINE)
    if line_re.search(content):
        def replace(match: re.Match[str]) -> str:
            return f'{match.group(1)}"{value}"{match.group(3)}'

        updated = line_re.sub(replace, content, count=1)
    else:
        newline = "" if content.endswith("\n") else "\n"
        updated = f"{content}{newline}{token} = \"{value}\"\n"
    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as err:
        raise ValueError(f"Failed to write {path}: {err}") from err


@dataclass(frozen=True)
class SyncPlan:
    path: Path
    status: str
    changes: tuple[str, ...]
    updated_content: str | None = None
    message: str | None = None


def print_plan_results(plans: list[SyncPlan], reporter: callable = print) -> tuple[int, list[SyncPlan], int]:
    total_changes = 0
    write_candidates: list[SyncPlan] = []
    error_count = 0
    for plan in plans:
        if plan.status == "missing":
            reporter(f"{plan.path.name}: skipped (missing file)")
            continue
        if plan.status == "error":
            reporter(f"{plan.path.name}: error ({plan.message})")
            error_count += 1
            continue
        change_count = len(plan.changes)
        total_changes += change_count
        if change_count == 0:
            reporter(f"{plan.path.name}: no changes")
            continue
        write_candidates.append(plan)
        reporter(f"{plan.path.name}: {change_count} change(s)")
        for change in plan.changes:
            reporter(f"  - {change}")
    return total_changes, write_candidates, error_count


def build_reload_command(reload_mode: str, changed_files: list[str], theme_arg: str | None, theme_dir: Path) -> list[str]:
    mode = reload_mode
    if reload_mode == "auto":
        only_hyprland = bool(changed_files) and all(file_name == "hyprland.conf" for file_name in changed_files)
        mode = "hypr" if only_hyprland else "full"

    if mode == "hypr":
        return ["hyprctl", "reload"]
    if mode == "full":
        theme_name = resolve_theme_name(theme_arg, theme_dir)
        return ["omarchy-theme-set", theme_name]
    raise ValueError(f"Unsupported reload mode: {reload_mode}")


def resolve_theme_name(theme_arg: str | None, theme_dir: Path) -> str:
    if theme_arg:
        return theme_arg
    name = theme_dir.name
    if name and name not in {"theme", "current"}:
        return name
    theme_name_file = Path.home() / ".config/omarchy/current/theme.name"
    if theme_name_file.exists():
        try:
            from_file = theme_name_file.read_text(encoding="utf-8").strip()
        except OSError:
            from_file = ""
        if from_file:
            return from_file
    return "current"


def run_reload_command(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as err:
        raise ValueError(f"Reload command not found: {cmd[0]}") from err
    except subprocess.CalledProcessError as err:
        stderr = err.stderr.strip() if err.stderr else ""
        stdout = err.stdout.strip() if err.stdout else ""
        detail = stderr or stdout or f"exit status {err.returncode}"
        raise ValueError(f"Reload command failed ({' '.join(cmd)}): {detail}") from err


def build_sync_plan(
    theme_dir: Path, colors: dict[str, str], zed_template_path: Path | None = None
) -> list[SyncPlan]:
    plans: list[SyncPlan] = []
    resolved_zed_template_path = zed_template_path
    for file_name in SYNC_TARGET_FILES:
        path = theme_dir / file_name
        if not path.exists():
            plans.append(SyncPlan(path=path, status="missing", changes=()))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as err:
            plans.append(SyncPlan(path=path, status="error", changes=(), message=str(err)))
            continue

        if file_name == "alacritty.toml":
            updated, changes = update_alacritty_dry_run(content, colors)
        elif file_name == "kitty.conf":
            updated, changes = update_kitty_dry_run(content, colors)
        elif file_name == "ghostty.conf":
            updated, changes = update_ghostty_dry_run(content, colors)
        elif file_name == "colors.css":
            updated, changes = update_css_dry_run(content, colors)
        elif file_name == "aether.override.css":
            updated, changes = update_aether_override_css_dry_run(content, colors)
        elif file_name == "gtk.css":
            updated, changes = update_gtk_css_dry_run(content, colors)
        elif file_name == "hyprland.conf":
            updated, changes = update_hyprland_dry_run(content, colors)
        elif file_name == "hyprlock.conf":
            updated, changes = update_hyprlock_dry_run(content, colors)
        elif file_name == "btop.theme":
            updated, changes = update_btop_dry_run(content, colors)
        elif file_name == "chromium.theme":
            updated, changes = update_chromium_dry_run(content, colors)
        elif file_name == "neovim.lua":
            updated, changes = update_neovim_lua_dry_run(content, colors)
        elif file_name == "aether.zed.json":
            if resolved_zed_template_path is None:
                resolved_zed_template_path = resolve_zed_template_path(None)
            updated, changes = update_aether_zed_json_dry_run(content, colors, resolved_zed_template_path)
        elif file_name == "vencord.theme.css":
            updated, changes = update_vencord_css_dry_run(content, colors)
        elif file_name == "wofi.css":
            updated, changes = update_wofi_css_dry_run(content, colors)
        elif file_name == "warp.yaml":
            updated, changes = update_warp_yaml_dry_run(content, colors)
        elif file_name == "walker.css":
            updated, changes = update_walker_css_dry_run(content, colors)
        elif file_name == "waybar.css":
            updated, changes = update_waybar_css_dry_run(content, colors)
        elif file_name == "mako.ini":
            updated, changes = update_mako_ini_dry_run(content, colors)
        elif file_name == "swayosd.css":
            updated, changes = update_swayosd_css_dry_run(content, colors)
        else:
            updated = content
            changes = []
        updated_content = updated if changes else None
        plans.append(SyncPlan(path=path, status="ok", changes=tuple(changes), updated_content=updated_content))
    return plans


def update_alacritty_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    section_key_to_token = {value: key for key, value in ALACRITTY_FIELD_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    section = ""
    for idx, line in enumerate(lines):
        section_match = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if section_match:
            section = section_match.group(1).strip()
            continue
        line_match = re.match(
            r"""^(\s*)([A-Za-z_][\w-]*)(\s*=\s*)(['"])(#[0-9A-Fa-f]{6})(['"])(\s*(?:#.*)?)$""",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(2)
        token = section_key_to_token.get((section, key))
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(5)
        if current.lower() == desired.lower():
            continue
        quote = line_match.group(4)
        lines[idx] = f"{line_match.group(1)}{key}{line_match.group(3)}{quote}{desired}{quote}{line_match.group(7)}\n"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_kitty_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token = {value: key for key, value in KITTY_FIELD_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(r"^(\s*)([A-Za-z_][\w-]*)(\s+)(#[0-9A-Fa-f]{6})(\s*(?:#.*)?)$", line)
        if not line_match:
            continue
        key = line_match.group(2)
        token = key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(4)
        if current.lower() == desired.lower():
            continue
        lines[idx] = f"{line_match.group(1)}{key}{line_match.group(3)}{desired}{line_match.group(5)}\n"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_ghostty_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    palette_to_token = {value: key for key, value in GHOSTTY_FIELD_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)
        base_match = re.match(r"^(\s*)(background|foreground)(\s*=\s*)(#[0-9A-Fa-f]{6})([ \t]*(?:#.*)?)$", core_line)
        if base_match:
            key = base_match.group(2)
            token = key
            if token in colors:
                desired = colors[token]
                current = base_match.group(4)
                if current.lower() != desired.lower():
                    lines[idx] = f"{base_match.group(1)}{key}{base_match.group(3)}{desired}{base_match.group(5)}{line_end}"
                    changes.append(f"{token}: {current} -> {desired}")
            continue

        palette_match = re.match(
            r"^(\s*)(palette)(\s*=\s*)(1[0-5]|[0-9])(\s*=\s*)(#[0-9A-Fa-f]{6})([ \t]*(?:#.*)?)$",
            core_line,
        )
        if not palette_match:
            continue
        palette_index = palette_match.group(4)
        token = palette_to_token.get(palette_index)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = palette_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{palette_match.group(1)}{palette_match.group(2)}{palette_match.group(3)}{palette_index}"
            f"{palette_match.group(5)}{desired}{palette_match.group(7)}{line_end}"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    var_to_token = {value: key for key, value in CSS_VARIABLE_MAP.items()}
    define_to_token = {value: key for key, value in CSS_DEFINE_COLOR_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)
        var_match = re.match(r"^(\s*)(--[\w-]+)(\s*:\s*)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/[ \t]*)?)$", core_line)
        if var_match:
            variable = var_match.group(2)
            token = var_to_token.get(variable)
            if token is None or token not in colors:
                continue
            desired = colors[token]
            current = var_match.group(4)
            if current.lower() == desired.lower():
                continue
            lines[idx] = f"{var_match.group(1)}{variable}{var_match.group(3)}{desired}{var_match.group(5)}{line_end}"
            changes.append(f"{token}: {current} -> {desired}")
            continue

        define_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/[ \t]*)?)$",
            core_line,
        )
        if define_match:
            name = define_match.group(4)
            token = define_to_token.get(name)
            if token is None or token not in colors:
                continue
            desired = colors[token]
            current = define_match.group(6)
            if current.lower() == desired.lower():
                continue
            lines[idx] = (
                f"{define_match.group(1)}{define_match.group(2)}{define_match.group(3)}{name}"
                f"{define_match.group(5)}{desired}{define_match.group(7)}{line_end}"
            )
            changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_aether_override_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token: dict[str, str] = {}
    for token, css_keys in AETHER_OVERRIDE_CSS_COLOR_MAP.items():
        for css_key in css_keys:
            key_to_token[css_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)
        line_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/[ \t]*)?)$",
            core_line,
        )
        if not line_match:
            continue
        key = line_match.group(4)
        token = key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{line_match.group(1)}{line_match.group(2)}{line_match.group(3)}{key}"
            f"{line_match.group(5)}{desired}{line_match.group(7)}{line_end}"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_gtk_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    gtk_key_to_token: dict[str, str] = {}
    for token, gtk_keys in GTK_CSS_COLOR_MAP.items():
        for gtk_key in gtk_keys:
            gtk_key_to_token[gtk_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)
        line_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/[ \t]*)?)$",
            core_line,
        )
        if not line_match:
            continue
        key = line_match.group(4)
        token = gtk_key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{line_match.group(1)}{line_match.group(2)}{line_match.group(3)}{key}"
            f"{line_match.group(5)}{desired}{line_match.group(7)}{line_end}"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def update_hyprland_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token = {value: key for key, value in HYPRLAND_FIELD_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"""^(\s*(?:\$)?)([A-Za-z_][\w.-]*)(\s*=\s*)(rgb\([0-9A-Fa-f]{6}\)|['"]?#[0-9A-Fa-f]{6}['"]?)(\s*(?:#.*)?)$""",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(2)
        token = key_to_token.get(key)
        if token is None or token not in colors:
            continue
        raw_value = line_match.group(4)
        replacement: str | None = None
        current_for_log: str | None = None
        hex_match = re.fullmatch(r"""(['"]?)(#[0-9A-Fa-f]{6})(['"]?)""", raw_value)
        rgb_match = re.fullmatch(r"""rgb\(([0-9A-Fa-f]{6})\)""", raw_value)
        if hex_match:
            current_for_log = hex_match.group(2)
            quote_open = hex_match.group(1)
            quote_close = hex_match.group(3)
            replacement = f"{quote_open}{colors[token]}{quote_close}"
        elif rgb_match:
            current_for_log = f"#{rgb_match.group(1)}"
            replacement = f"rgb({colors[token].lstrip('#')})"
        else:
            continue

        desired = colors[token]
        if current_for_log is None or current_for_log.lower() == desired.lower():
            continue
        lines[idx] = f"{line_match.group(1)}{key}{line_match.group(3)}{replacement}{line_match.group(5)}\n"
        changes.append(f"{token}: {current_for_log} -> {desired}")
    return "".join(lines), changes


def update_hyprlock_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    var_to_token: dict[str, str] = {}
    for token, vars_ in HYPRLOCK_FIELD_MAP.items():
        for var_name in vars_:
            var_to_token[var_name] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"""^(\s*\$)([A-Za-z_][\w]*)(\s*=\s*)rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9.]+)\s*\)(\s*(?:#.*)?)$""",
            line,
        )
        if not line_match:
            continue
        var_name = line_match.group(2)
        token = var_to_token.get(var_name)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        desired_rgb = hex_to_rgb(desired)
        current_hex = rgb_to_hex(int(line_match.group(4)), int(line_match.group(5)), int(line_match.group(6)))
        if current_hex.lower() == desired.lower():
            continue
        alpha = line_match.group(7)
        lines[idx] = (
            f"{line_match.group(1)}{var_name}{line_match.group(3)}"
            f"rgba({desired_rgb[0]}, {desired_rgb[1]}, {desired_rgb[2]}, {alpha}){line_match.group(8)}\n"
        )
        changes.append(f"{token}: {current_hex} -> {desired}")
    return "".join(lines), changes


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def update_btop_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token: dict[str, str] = {}
    for token, fields in BTOP_FIELD_MAP.items():
        for field in fields:
            key_to_token[field] = token
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"""^(\s*)(theme\[[^\]]+\])(\s*=\s*)(['"])(#[0-9A-Fa-f]{6})(['"])(\s*(?:#.*)?)$""",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(2)
        token = key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(5)
        if current.lower() == desired.lower():
            continue
        quote = line_match.group(4)
        lines[idx] = f"{line_match.group(1)}{key}{line_match.group(3)}{quote}{desired}{quote}{line_match.group(7)}\n"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_chromium_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token = {value: key for key, value in CHROMIUM_FIELD_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"""^(\s*)(["']?)([A-Za-z_][\w-]*)(["']?)(\s*:\s*)(['"])(#[0-9A-Fa-f]{6})(['"])(\s*,?\s*)$""",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(3)
        token = key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(7)
        if current.lower() == desired.lower():
            continue
        key_open = line_match.group(2)
        key_close = line_match.group(4)
        value_quote = line_match.group(6)
        lines[idx] = (
            f"{line_match.group(1)}{key_open}{key}{key_close}{line_match.group(5)}{value_quote}{desired}"
            f"{value_quote}{line_match.group(9)}\n"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_neovim_lua_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    lua_key_to_token: dict[str, str] = {}
    for token, lua_keys in NEOVIM_LUA_COLOR_MAP.items():
        for lua_key in lua_keys:
            lua_key_to_token[lua_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"""^(\s*)([A-Za-z_][\w]*)(\s*=\s*)(['"])(#[0-9A-Fa-f]{6})(['"])(\s*,?\s*(?:--.*)?)$""",
            line,
        )
        if not line_match:
            continue
        lua_key = line_match.group(2)
        token = lua_key_to_token.get(lua_key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(5)
        if current.lower() == desired.lower():
            continue
        quote = line_match.group(4)
        lines[idx] = f"{line_match.group(1)}{lua_key}{line_match.group(3)}{quote}{desired}{quote}{line_match.group(7)}\n"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def resolve_zed_template_path(cli_override: str | None) -> Path:
    if cli_override:
        raw_path = cli_override
    else:
        raw_path = os.environ.get(ENV_AETHER_ZED_TEMPLATE, str(DEFAULT_AETHER_ZED_TEMPLATE))
    template_path = Path(raw_path).expanduser()
    if not template_path.is_absolute():
        template_path = (Path.cwd() / template_path).resolve()
    if not template_path.exists():
        raise ValueError(f"Zed template not found: {template_path}")
    if not template_path.is_file():
        raise ValueError(f"Zed template is not a file: {template_path}")
    return template_path


def build_zed_template_context(colors: dict[str, str]) -> dict[str, str]:
    alias_map = {
        "black": "color0",
        "red": "color1",
        "green": "color2",
        "yellow": "color3",
        "blue": "color4",
        "magenta": "color5",
        "cyan": "color6",
        "white": "color7",
        "bright_black": "color8",
        "bright_red": "color9",
        "bright_green": "color10",
        "bright_yellow": "color11",
        "bright_blue": "color12",
        "bright_magenta": "color13",
        "bright_cyan": "color14",
        "bright_white": "color15",
    }
    context = {key: value for key, value in colors.items()}
    for alias, token in alias_map.items():
        if token in colors:
            context[alias] = colors[token]
    context["theme_type"] = "dark"
    return context


def render_zed_template_value(value: object, context: dict[str, str], template_path: Path) -> object:
    if isinstance(value, dict):
        return {k: render_zed_template_value(v, context, template_path) for k, v in value.items()}
    if isinstance(value, list):
        return [render_zed_template_value(item, context, template_path) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise ValueError(f"Missing template variable '{key}' in {template_path}")
        return context[key]

    return TEMPLATE_VAR_RE.sub(replace, value)


def render_zed_template(colors: dict[str, str], template_path: Path) -> str:
    try:
        template_obj = json.loads(template_path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise ValueError(f"Zed template not found: {template_path}") from err
    except OSError as err:
        raise ValueError(f"Failed to read Zed template {template_path}: {err}") from err
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in Zed template {template_path}: {err}") from err

    context = build_zed_template_context(colors)
    rendered = render_zed_template_value(template_obj, context, template_path)
    return f"{json.dumps(rendered, indent=2, ensure_ascii=True)}\n"


def collect_json_color_changes(old_obj: object, new_obj: object, prefix: str = "") -> list[str]:
    changes: list[str] = []
    if isinstance(old_obj, dict) and isinstance(new_obj, dict):
        for key in old_obj.keys() & new_obj.keys():
            next_prefix = f"{prefix}.{key}" if prefix else key
            changes.extend(collect_json_color_changes(old_obj[key], new_obj[key], next_prefix))
        return changes
    if isinstance(old_obj, list) and isinstance(new_obj, list):
        for idx, (old_item, new_item) in enumerate(zip(old_obj, new_obj)):
            next_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            changes.extend(collect_json_color_changes(old_item, new_item, next_prefix))
        return changes
    if isinstance(old_obj, str) and isinstance(new_obj, str) and old_obj != new_obj:
        if HEX_COLOR_RE.match(old_obj) and HEX_COLOR_RE.match(new_obj):
            path = prefix or "<root>"
            changes.append(f"{path}: {old_obj} -> {new_obj}")
    return changes


def update_aether_zed_json_dry_run(content: str, colors: dict[str, str], template_path: Path) -> tuple[str, list[str]]:
    rendered = render_zed_template(colors, template_path)
    if content == rendered:
        return content, []

    try:
        old_obj = json.loads(content)
        new_obj = json.loads(rendered)
        changes = collect_json_color_changes(old_obj, new_obj)
    except json.JSONDecodeError:
        changes = []

    if not changes:
        changes = ["template-rendered output differs"]
    return rendered, changes


def update_vencord_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    css_var_to_token = {value: key for key, value in VENCORD_CSS_COLOR_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)
        line_match = re.match(r"^(\s*)(--color\d{2})(\s*:\s*)(#[0-9A-Fa-f]{6})(\s*;\s*)$", core_line)
        if not line_match:
            continue
        variable = line_match.group(2)
        token = css_var_to_token.get(variable)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(4)
        if current.lower() == desired.lower():
            continue
        lines[idx] = f"{line_match.group(1)}{variable}{line_match.group(3)}{desired}{line_match.group(5)}{line_end}"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_wofi_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    wofi_key_to_token: dict[str, str] = {}
    for token, css_keys in WOFI_CSS_COLOR_MAP.items():
        for css_key in css_keys:
            wofi_key_to_token[css_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)
        line_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/[ \t]*)?)$",
            core_line,
        )
        if not line_match:
            continue
        key = line_match.group(4)
        token = wofi_key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{line_match.group(1)}{line_match.group(2)}{line_match.group(3)}{key}"
            f"{line_match.group(5)}{desired}{line_match.group(7)}{line_end}"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_warp_yaml_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    path_to_token: dict[str, str] = {}
    for token, paths in WARP_YAML_COLOR_MAP.items():
        for p in paths:
            path_to_token[p] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    section: str | None = None
    for idx, line in enumerate(lines):
        core_line, line_end = split_line_ending(line)

        section_match = re.match(r"^(\s*)(terminal_colors)\s*:\s*$", core_line)
        if section_match:
            section = None
            continue
        normal_match = re.match(r"^(\s{2})normal\s*:\s*$", core_line)
        if normal_match:
            section = "normal"
            continue
        bright_match = re.match(r"^(\s{2})bright\s*:\s*$", core_line)
        if bright_match:
            section = "bright"
            continue

        top_match = re.match(r'^(\s*)(accent|cursor|background|foreground)(\s*:\s*)(["\'])(#[0-9A-Fa-f]{6})(["\'])(\s*)$', core_line)
        if top_match:
            key = top_match.group(2)
            token = path_to_token.get(key)
            if token is None or token not in colors:
                continue
            current = top_match.group(5)
            desired = colors[token]
            if current.lower() == desired.lower():
                continue
            lines[idx] = (
                f"{top_match.group(1)}{key}{top_match.group(3)}{top_match.group(4)}{desired}"
                f"{top_match.group(6)}{top_match.group(7)}{line_end}"
            )
            changes.append(f"{token}: {current} -> {desired}")
            continue

        nested_match = re.match(r'^(\s{4})(black|red|green|yellow|blue|magenta|cyan|white)(\s*:\s*)(["\'])(#[0-9A-Fa-f]{6})(["\'])(\s*)$', core_line)
        if nested_match and section in {"normal", "bright"}:
            key = nested_match.group(2)
            token = path_to_token.get(f"{section}.{key}")
            if token is None or token not in colors:
                continue
            current = nested_match.group(5)
            desired = colors[token]
            if current.lower() == desired.lower():
                continue
            lines[idx] = (
                f"{nested_match.group(1)}{key}{nested_match.group(3)}{nested_match.group(4)}{desired}"
                f"{nested_match.group(6)}{nested_match.group(7)}{line_end}"
            )
            changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_walker_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    css_key_to_token: dict[str, str] = {}
    for token, css_keys in WALKER_CSS_COLOR_MAP.items():
        for css_key in css_keys:
            css_key_to_token[css_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/\s*)?)$",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(4)
        token = css_key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{line_match.group(1)}{line_match.group(2)}{line_match.group(3)}{key}"
            f"{line_match.group(5)}{desired}{line_match.group(7)}\n"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_waybar_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    css_key_to_token: dict[str, str] = {}
    for token, css_keys in WAYBAR_CSS_COLOR_MAP.items():
        for css_key in css_keys:
            css_key_to_token[css_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/\s*)?)$",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(4)
        token = css_key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{line_match.group(1)}{line_match.group(2)}{line_match.group(3)}{key}"
            f"{line_match.group(5)}{desired}{line_match.group(7)}\n"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_mako_ini_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token = {value: key for key, value in MAKO_INI_COLOR_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"^(\s*)([A-Za-z_][\w-]*)(\s*=\s*)(#[0-9A-Fa-f]{6})(\s*(?:#.*)?)$",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(2)
        token = key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(4)
        if current.lower() == desired.lower():
            continue
        lines[idx] = f"{line_match.group(1)}{key}{line_match.group(3)}{desired}{line_match.group(5)}\n"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_swayosd_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    css_key_to_token: dict[str, str] = {}
    for token, css_keys in SWAYOSD_CSS_COLOR_MAP.items():
        for css_key in css_keys:
            css_key_to_token[css_key] = token

    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"^(\s*)(@define-color)(\s+)([\w-]+)(\s+)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/\s*)?)$",
            line,
        )
        if not line_match:
            continue
        key = line_match.group(4)
        token = css_key_to_token.get(key)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(6)
        if current.lower() == desired.lower():
            continue
        lines[idx] = (
            f"{line_match.group(1)}{line_match.group(2)}{line_match.group(3)}{key}"
            f"{line_match.group(5)}{desired}{line_match.group(7)}\n"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


class InteractiveUI:
    def __init__(self, use_gum: bool) -> None:
        self.use_gum = use_gum

    @classmethod
    def autodetect(cls) -> "InteractiveUI":
        return cls(use_gum=shutil.which("gum") is not None)

    def _run_gum(self, args: list[str]) -> str:
        proc = subprocess.run(["gum", *args], check=True, capture_output=True, text=True)
        return proc.stdout.strip()

    def info(self, message: str) -> None:
        self._styled(message, "4")

    def success(self, message: str) -> None:
        self._styled(message, "2")

    def warning(self, message: str) -> None:
        self._styled(message, "3")

    def error(self, message: str) -> None:
        self._styled(message, "1")

    def muted(self, message: str) -> None:
        self._styled(message, "8")

    def _styled(self, message: str, color: str) -> None:
        if self.use_gum:
            try:
                out = self._run_gum(["style", "--foreground", color, message])
                print(out)
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.use_gum = False
        print(message)

    def choose(self, header: str, options: list[str]) -> str | None:
        if self.use_gum:
            try:
                return self._run_gum(["choose", "--header", header, *options]) or None
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.use_gum = False
        print(header)
        for i, option in enumerate(options, start=1):
            print(f"{i}. {option}")
        raw = input("Select: ").strip()
        if not raw:
            return None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        return None

    def prompt(self, prompt: str, placeholder: str = "") -> str:
        if self.use_gum:
            try:
                args = ["input", "--prompt", f"{prompt}: "]
                if placeholder:
                    args += ["--placeholder", placeholder]
                return self._run_gum(args)
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.use_gum = False
        return input(f"{prompt}: ").strip()

    def confirm(self, prompt: str) -> bool:
        if self.use_gum:
            try:
                subprocess.run(["gum", "confirm", prompt], check=True)
                return True
            except subprocess.CalledProcessError:
                return False
            except FileNotFoundError:
                self.use_gum = False
        answer = input(f"{prompt} [y/N]: ").strip().lower()
        return answer in {"y", "yes"}

    def report_line(self, line: str) -> None:
        if ": error (" in line:
            self.error(line)
        elif "change(s)" in line or line.startswith("  - "):
            self.warning(line)
        elif "no changes" in line or "skipped (missing file)" in line:
            self.muted(line)
        elif line.startswith("sync: wrote") or line.startswith("sync: backups") or line.startswith("sync: reload"):
            self.success(line)
        else:
            self.info(line)


def interactive_main() -> int:
    ui = InteractiveUI.autodetect()
    theme: str | None = None
    if ui.use_gum:
        ui.success("Interactive mode enabled (gum)")
    else:
        ui.warning("gum not found; using plain prompts")

    while True:
        context = theme or "active"
        choice = ui.choose(
            f"omapal ({context})",
            [
                "Show Palette",
                "Set Token",
                "Sync (Preview)",
                "Sync (Apply)",
                "Diff",
                "Theme Context",
                "Exit",
            ],
        )
        if choice in {None, "Exit"}:
            return 0
        if choice == "Show Palette":
            if run_show_interactive(ui, theme) != 0:
                return 2
        elif choice == "Set Token":
            if run_set_interactive(ui, theme) != 0:
                return 2
        elif choice == "Sync (Preview)":
            code = run_sync(
                theme=theme,
                write=False,
                dry_run=True,
                zed_template=None,
                reload_mode="auto",
                no_reload=True,
                reporter=ui.report_line,
                err_reporter=ui.error,
            )
            if code != 0:
                return code
        elif choice == "Sync (Apply)":
            if not ui.confirm("Apply sync changes?"):
                continue
            reload_choice = ui.choose("Reload mode", ["auto", "full", "hypr", "no-reload"]) or "auto"
            code = run_sync(
                theme=theme,
                write=True,
                dry_run=False,
                zed_template=None,
                reload_mode="auto" if reload_choice == "no-reload" else reload_choice,
                no_reload=reload_choice == "no-reload",
                reporter=ui.report_line,
                err_reporter=ui.error,
            )
            if code != 0:
                return code
        elif choice == "Diff":
            code = run_diff(theme=theme, zed_template=None, reporter=ui.report_line, err_reporter=ui.error)
            if code != 0:
                return code
        elif choice == "Theme Context":
            selection = ui.choose("Theme selection", ["Use active theme", "Use named theme", "Back"])
            if selection == "Use active theme":
                theme = None
                ui.success("Theme context set to active")
            elif selection == "Use named theme":
                named = ui.prompt("Theme name", "sparta")
                if not named:
                    continue
                resolve_theme_dir(named)
                theme = named
                ui.success(f"Theme context set to {named}")


def run_show_interactive(ui: InteractiveUI, theme: str | None) -> int:
    theme_dir = resolve_theme_dir(theme)
    colors = read_colors_toml(theme_dir / "colors.toml")
    ui.info(f"show: theme={theme or 'active'} path={theme_dir}")
    for token in CANONICAL_TOKENS:
        if token in colors:
            ui.report_line(f"{token}={colors[token]}")
    return 0


def run_set_interactive(ui: InteractiveUI, theme: str | None) -> int:
    token = ui.choose("Token", list(CANONICAL_TOKENS))
    if not token:
        return 0
    value = ui.prompt("Hex value", "#112233")
    if not value:
        return 0
    validate_token(token)
    validate_hex_color(value)
    theme_dir = resolve_theme_dir(theme)
    colors_toml = theme_dir / "colors.toml"
    current = read_colors_toml(colors_toml).get(token, "(unset)")
    ui.warning(f"{token}: {current} -> {value}")
    if not ui.confirm("Apply token change?"):
        return 0
    update_colors_toml(colors_toml, token, value)
    ui.success(f"set: updated {token}={value} in {colors_toml}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command is None:
            if args.no_interactive:
                parser.print_help()
                return 0
            return interactive_main()
        return int(args.func(args))
    except (ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
