# INITINFO

## Purpose
Working context for upcoming `init` command for `omapal`.

## Source Read
- `PLAN.md` (project plan and constraints)

## Project Goal
Create a local Python CLI (`omapal`) to edit Omarchy theme palette colors from `colors.toml` as the source of truth and sync to other theme files.

## Hard Constraints
- Only operate inside theme directories:
  - `~/.config/omarchy/current/theme/*`
  - `~/.config/omarchy/themes/<theme-name>/*`
- Do not modify global app configs outside theme directories.
- Start with active theme support before broader theme management.

## Tech Decisions (from plan)
- Python 3.11+
- `argparse` CLI
- `tomllib` for TOML parsing
- `pytest` for tests

## Expected Initial Repo Layout
- `omapal.py`
- `mappings.py`
- `writers.py`
- `validators.py`
- `tests/`
- supporting docs

## MVP Commands
- `omapal show [--theme <name>]`
- `omapal set <token> <#hex> [--theme <name>]`
- `omapal sync [--theme <name>] [--dry-run]`
- `omapal diff [--theme <name>]`

## Canonical Tokens
- `background`, `foreground`, `accent`, `cursor`
- `selection_background`, `selection_foreground`
- `color0`..`color15`
- optional semantic tokens (example: `active_border_color`)

## MVP Sync Targets
- `colors.toml`
- `alacritty.toml`
- `kitty.conf`
- `colors.css`
- `hyprland.conf`
- `btop.theme`
- `chromium.theme`

## Safety Requirements
- Validate token names and hex values before writing.
- `sync` should behave as dry-run by default unless explicit write flag is passed.
- Backups in `.palette-backup/<timestamp>/`.
- Atomic writes (temp file + rename).

## Apply/Reload Behavior
- Default refresh after write: `omarchy-theme-set <theme-name>`.
- Optional faster path: `hyprctl reload` for Hyprland-only changes.

## Init Priorities (Milestone 1)
1. Bootstrap CLI entrypoint and argument parser.
2. Implement theme path resolution for active theme and `--theme` override.
3. Scaffold validators, mappings, and writer interfaces.
4. Add `show`/`set` for `colors.toml` first.
5. Add tests for path resolution and input validation.

## Acceptance Signals for Early Init
- Running `omapal --help` works.
- `omapal show` can read `colors.toml` from resolved theme path.
- Invalid token/hex returns clear non-zero errors.

## Notes
- Repository currently contains only `PLAN.md` plus this `INITINFO.md`.
- No `main` file was found at this time.
