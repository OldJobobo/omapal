# omapal Project Plan

## Goal
Create a local tool named `omapal` that lets you change Omarchy theme palette colors from one source of truth, then sync those changes across theme files automatically.

## Scope Rules
- Only read/write inside theme directories:
  - `~/.config/omarchy/current/theme/*`
  - `~/.config/omarchy/themes/<theme-name>/*`
- Do not edit global app configs outside theme directories.
- Start with active theme support first, then expand.

## Tech Stack
- Python 3.11+
- CLI: `argparse` (stdlib)
- Parsing: `tomllib` for `colors.toml` + format-specific text rewriting
- Testing: `pytest`

## Repository Layout (initial)
- `omapal/`
- `omapal/README.md`
- `omapal/PLAN.md`
- `omapal/omapal.py`
- `omapal/mappings.py`
- `omapal/writers.py`
- `omapal/validators.py`
- `omapal/tests/`

## Canonical Data Model
- Source of truth: `colors.toml` in target theme.
- Canonical token set:
  - `background`, `foreground`, `accent`, `cursor`
  - `selection_background`, `selection_foreground`
  - `color0`..`color15`
  - optional semantic tokens like `active_border_color`

## CLI Design (MVP)
- `omapal show [--theme <name>]`
- `omapal set <token> <#hex> [--theme <name>]`
- `omapal sync [--theme <name>] [--dry-run]`
- `omapal diff [--theme <name>]`

## File Targets (MVP)
- `colors.toml`
- `alacritty.toml`
- `kitty.conf`
- `colors.css`
- `hyprland.conf`
- `btop.theme`
- `chromium.theme`

## Mapping Strategy
- Keep a central mapping table from canonical tokens to each target file/field.
- For each format, implement a focused updater (not blind replace-all).
- Preserve comments and non-color settings where possible.

## Safety Requirements
- Validate token names and hex format before writes.
- `sync` defaults to `--dry-run` behavior unless `--write` is passed.
- Backup changed files to `.palette-backup/<timestamp>/`.
- Atomic writes using temp files and rename.

## Apply/Reload Workflow
- On successful write:
  - default: run `omarchy-theme-set <theme-name>` for full refresh
  - optional fast path: `hyprctl reload` when only Hyprland-relevant files changed

## Milestones
1. Bootstrap CLI and theme path resolution.
2. Implement `show` and `set` against `colors.toml`.
3. Implement `sync --dry-run` for 3 files:
   - `alacritty.toml`, `kitty.conf`, `colors.css`
4. Extend sync to:
   - `hyprland.conf`, `btop.theme`, `chromium.theme`
5. Add `diff` and backups.
6. Add tests for parsing, mapping, and safe writes.

## MVP Acceptance Criteria
- Changing one token in `colors.toml` updates all supported target files via `sync`.
- `--dry-run` shows exact pending changes and touches no files.
- Invalid token/hex input exits with clear errors.
- Backup and atomic write behavior works for every modified file.
- Reapply command refreshes active theme correctly.

## Post-MVP
- Add `set-many --file palette.toml`.
- Add `doctor` command to detect out-of-sync files.
- Add import mode to derive `colors.toml` from existing theme files.
