"""Automated version bumping utility for omapal."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

VERSION_RE = re.compile(r'^__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$', re.MULTILINE)
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "version.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid version '{value}'. Use MAJOR.MINOR.PATCH format.")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_semver(parts: tuple[int, int, int]) -> str:
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def bump_semver(current: str, part: str) -> str:
    major, minor, patch = parse_semver(current)
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unsupported bump part: {part}")
    return format_semver((major, minor, patch))


def read_version(path: Path | None = None) -> str:
    if path is None:
        path = VERSION_FILE
    text = path.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise ValueError(f"Could not find __version__ assignment in {path}")
    return format_semver((int(match.group(1)), int(match.group(2)), int(match.group(3))))


def write_version(new_version: str, path: Path | None = None) -> None:
    if path is None:
        path = VERSION_FILE
    _ = parse_semver(new_version)
    text = path.read_text(encoding="utf-8")
    if not VERSION_RE.search(text):
        raise ValueError(f"Could not find __version__ assignment in {path}")
    updated = VERSION_RE.sub(f'__version__ = "{new_version}"', text, count=1)
    path.write_text(updated, encoding="utf-8")


def ensure_changelog_entry(new_version: str, changelog_path: Path | None = None) -> bool:
    if changelog_path is None:
        changelog_path = CHANGELOG_FILE
    today = date.today().isoformat()
    new_header = f"## [{new_version}] - {today}"
    if not changelog_path.exists():
        changelog_path.write_text(
            "\n".join(
                [
                    "# Changelog",
                    "",
                    "All notable changes to this project will be documented in this file.",
                    "",
                    f"{new_header}",
                    "",
                    "### Changed",
                    "- TBD",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return True

    text = changelog_path.read_text(encoding="utf-8")
    if new_header in text:
        return False

    lines = text.splitlines()
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_at = i
            break

    entry_lines = [new_header, "", "### Changed", "- TBD", ""]
    if insert_at is None:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(entry_lines)
    else:
        lines[insert_at:insert_at] = entry_lines

    changelog_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="versioning", description="Version management tool for omapal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    current_parser = subparsers.add_parser("current", help="Print current project version")
    current_parser.set_defaults(func=cmd_current)

    bump_parser = subparsers.add_parser("bump", help="Bump semantic version")
    bump_parser.add_argument("part", choices=("patch", "minor", "major"))
    bump_parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    bump_parser.add_argument("--no-changelog", action="store_true", help="Do not add changelog entry")
    bump_parser.set_defaults(func=cmd_bump)

    set_parser = subparsers.add_parser("set", help="Set explicit semantic version")
    set_parser.add_argument("version", help="Semantic version (MAJOR.MINOR.PATCH)")
    set_parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    set_parser.add_argument("--no-changelog", action="store_true", help="Do not add changelog entry")
    set_parser.set_defaults(func=cmd_set)
    return parser


def cmd_current(_: argparse.Namespace) -> int:
    print(read_version())
    return 0


def _apply_version_change(new_version: str, *, dry_run: bool, no_changelog: bool) -> int:
    old_version = read_version()
    parse_semver(new_version)
    print(f"version: {old_version} -> {new_version}")
    if dry_run:
        if not no_changelog:
            print("changelog: would ensure release entry")
        print("mode: dry-run")
        return 0

    write_version(new_version)
    print(f"updated: {VERSION_FILE}")
    if not no_changelog:
        changed = ensure_changelog_entry(new_version)
        if changed:
            print(f"updated: {CHANGELOG_FILE}")
        else:
            print(f"unchanged: {CHANGELOG_FILE} (entry already exists)")
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    old_version = read_version()
    new_version = bump_semver(old_version, args.part)
    return _apply_version_change(new_version, dry_run=args.dry_run, no_changelog=args.no_changelog)


def cmd_set(args: argparse.Namespace) -> int:
    return _apply_version_change(args.version, dry_run=args.dry_run, no_changelog=args.no_changelog)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, OSError) as err:
        print(f"error: {err}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
