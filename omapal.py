"""CLI entrypoint for omapal."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mappings import (
    ALACRITTY_FIELD_MAP,
    BTOP_FIELD_MAP,
    CANONICAL_TOKENS,
    CHROMIUM_FIELD_MAP,
    CSS_VARIABLE_MAP,
    HYPRLAND_FIELD_MAP,
    KITTY_FIELD_MAP,
    SYNC_TARGET_FILES,
)
from validators import validate_hex_color, validate_theme_dir, validate_token
from writers import atomic_write, backup_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omapal", description="Omarchy palette manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    sync_parser.add_argument("--write", action="store_true", help="Apply changes")
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
    if args.dry_run and args.write:
        raise ValueError("Use either --dry-run or --write, not both.")

    theme_dir = resolve_theme_dir(args.theme)
    colors = read_colors_toml(theme_dir / "colors.toml")
    plans = build_sync_plan(theme_dir, colors)
    mode = "write" if args.write else "dry-run"

    print(f"sync: mode={mode} theme={args.theme or 'active'}")
    total_changes, write_candidates, error_count = print_plan_results(plans)

    if args.write and write_candidates:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = theme_dir / ".palette-backup" / timestamp
        for plan in write_candidates:
            if plan.updated_content is None:
                continue
            backup_file(plan.path, backup_root)
            atomic_write(plan.path, plan.updated_content)
        print(f"sync: wrote {len(write_candidates)} file(s)")
        print(f"sync: backups at {backup_root}")
        if not args.no_reload:
            changed_files = [plan.path.name for plan in write_candidates]
            reload_cmd = build_reload_command(args.reload_mode, changed_files, args.theme, theme_dir)
            run_reload_command(reload_cmd)
            print(f"sync: reload command={' '.join(reload_cmd)}")

    print(f"sync: total planned changes={total_changes}")
    if error_count:
        print(f"sync: encountered {error_count} error(s)", file=sys.stderr)
        return 2
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    theme_dir = resolve_theme_dir(args.theme)
    colors = read_colors_toml(theme_dir / "colors.toml")
    plans = build_sync_plan(theme_dir, colors)

    print(f"diff: theme={args.theme or 'active'}")
    total_changes, _, error_count = print_plan_results(plans)
    print(f"diff: total changes={total_changes}")
    if error_count:
        print(f"diff: encountered {error_count} error(s)", file=sys.stderr)
        return 2
    return 0


def resolve_theme_dir(theme_name: str | None) -> Path:
    home = Path.home()
    if theme_name:
        target = home / ".config/omarchy/themes" / theme_name
    else:
        target = home / ".config/omarchy/current/theme"
    validate_theme_dir(target, home)
    if not target.exists():
        raise ValueError(f"Theme directory not found: {target}")
    if not target.is_dir():
        raise ValueError(f"Theme path is not a directory: {target}")
    return target


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


def print_plan_results(plans: list[SyncPlan]) -> tuple[int, list[SyncPlan], int]:
    total_changes = 0
    write_candidates: list[SyncPlan] = []
    error_count = 0
    for plan in plans:
        if plan.status == "missing":
            print(f"{plan.path.name}: skipped (missing file)")
            continue
        if plan.status == "error":
            print(f"{plan.path.name}: error ({plan.message})")
            error_count += 1
            continue
        change_count = len(plan.changes)
        total_changes += change_count
        if change_count == 0:
            print(f"{plan.path.name}: no changes")
            continue
        write_candidates.append(plan)
        print(f"{plan.path.name}: {change_count} change(s)")
        for change in plan.changes:
            print(f"  - {change}")
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
    resolved = theme_dir.resolve()
    parts = resolved.parts
    if "themes" in parts:
        idx = parts.index("themes")
        if idx + 1 < len(parts):
            return parts[idx + 1]
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


def build_sync_plan(theme_dir: Path, colors: dict[str, str]) -> list[SyncPlan]:
    plans: list[SyncPlan] = []
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
        elif file_name == "colors.css":
            updated, changes = update_css_dry_run(content, colors)
        elif file_name == "hyprland.conf":
            updated, changes = update_hyprland_dry_run(content, colors)
        elif file_name == "btop.theme":
            updated, changes = update_btop_dry_run(content, colors)
        elif file_name == "chromium.theme":
            updated, changes = update_chromium_dry_run(content, colors)
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


def update_css_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    var_to_token = {value: key for key, value in CSS_VARIABLE_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(r"^(\s*)(--[\w-]+)(\s*:\s*)(#[0-9A-Fa-f]{6})(\s*;\s*(?:/\*.*\*/\s*)?)$", line)
        if not line_match:
            continue
        variable = line_match.group(2)
        token = var_to_token.get(variable)
        if token is None or token not in colors:
            continue
        desired = colors[token]
        current = line_match.group(4)
        if current.lower() == desired.lower():
            continue
        lines[idx] = f"{line_match.group(1)}{variable}{line_match.group(3)}{desired}{line_match.group(5)}\n"
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_hyprland_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token = {value: key for key, value in HYPRLAND_FIELD_MAP.items()}
    changes: list[str] = []
    lines = content.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        line_match = re.match(
            r"""^(\s*(?:\$)?)([A-Za-z_][\w-]*)(\s*=\s*)(['"]?)(#[0-9A-Fa-f]{6})(['"]?)(\s*(?:#.*)?)$""",
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
        closing_quote = line_match.group(6)
        lines[idx] = (
            f"{line_match.group(1)}{key}{line_match.group(3)}{quote}{desired}{closing_quote}{line_match.group(7)}\n"
        )
        changes.append(f"{token}: {current} -> {desired}")
    return "".join(lines), changes


def update_btop_dry_run(content: str, colors: dict[str, str]) -> tuple[str, list[str]]:
    key_to_token = {value: key for key, value in BTOP_FIELD_MAP.items()}
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
