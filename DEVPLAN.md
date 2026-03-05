# omapal Dev Plan

## Objective
Build `omapal` into a safe, testable CLI that treats `colors.toml` as source-of-truth and synchronizes supported Omarchy theme files without touching non-theme paths.

## Current Baseline
- Scaffold exists (`omapal.py`, `validators.py`, `mappings.py`, `writers.py`, tests).
- CLI subcommands are wired but mostly stubbed.
- Basic validation tests are passing.

## Non-Negotiable Constraints
- Read/write only under:
  - `~/.config/omarchy/current/theme/*`
  - `~/.config/omarchy/themes/<theme-name>/*`
- No edits outside theme directories.
- Dry-run-first behavior for sync.
- Backup + atomic writes for every mutation.

## Architecture Plan
- `omapal.py`
  - CLI argument parsing and command dispatch.
- `validators.py`
  - token and color validation.
  - path safety validation.
- `mappings.py`
  - canonical token list.
  - per-target mapping specs.
- `writers.py`
  - backup creation.
  - atomic writes.
  - diff preview generation helpers.
- `tests/`
  - unit tests for validators/mappings/writers.
  - command behavior tests for show/set/sync/diff.

## Milestone Execution

### M1: Theme Resolution + Source Read/Write
Scope:
- Implement theme path resolver:
  - active theme default (`~/.config/omarchy/current/theme`)
  - named theme override (`~/.config/omarchy/themes/<theme-name>`)
- Implement `show` reading `colors.toml`.
- Implement `set` for canonical tokens in `colors.toml`.

Deliverables:
- `show` prints current token values.
- `set` updates value and preserves unrelated TOML content where possible.
- clear exit codes and error messages for missing files/invalid input.

Definition of done:
- `show`/`set` work against active and named themes.
- tests cover path resolution and token/color validation errors.

### M2: Sync Engine (Dry-Run First, 3 Files)
Scope:
- Implement mapping model for:
  - `alacritty.toml`
  - `kitty.conf`
  - `colors.css`
- Implement format-specific updaters (targeted replacements, no blind full-file replace).
- Implement `sync --dry-run` default behavior.

Deliverables:
- `sync` outputs per-file planned changes and counts.
- no file writes in dry-run mode.

Definition of done:
- dry-run accurately reports changes for all 3 targets.
- tests verify no writes occur in dry-run.

### M3: Sync Engine Extension (Remaining MVP Files)
Scope:
- Add updaters/mappings for:
  - `hyprland.conf`
  - `btop.theme`
  - `chromium.theme`

Deliverables:
- all MVP target files supported in sync pipeline.

Definition of done:
- one canonical token change propagates to all supported target files in plan output.

### M4: Safe Write Path + Backups
Scope:
- Implement `writers.atomic_write`.
- Implement timestamped backup dir: `.palette-backup/<timestamp>/`.
- Add `--write` mode to apply planned diffs.

Deliverables:
- `sync --write` writes only changed files.
- each changed file gets backup before write.

Definition of done:
- interrupted writes do not corrupt target files.
- backup folder contains original versions of changed files.

### M5: Diff + Reload Workflow
Scope:
- Implement `diff` command (show out-of-sync state by file/token).
- Integrate refresh command after successful write:
  - default `omarchy-theme-set <theme-name>`
  - optional fast path `hyprctl reload` when only Hyprland-relevant targets changed.

Deliverables:
- diff output readable and actionable.
- reload behavior configurable and deterministic.

Definition of done:
- `diff` is consistent with `sync --dry-run` planned changes.
- reload command invoked only after successful write operations.

### M6: Hardening + Test Coverage
Scope:
- edge cases:
  - missing target files
  - malformed `colors.toml`
  - unknown tokens in theme files
- improve messaging and non-zero exits.
- strengthen test matrix and fixtures.

Deliverables:
- robust failure modes with clear remediation hints.
- CI-ready local test command (`pytest`).

Definition of done:
- tests cover critical success/failure paths for every command.
- MVP acceptance criteria from `PLAN.md` fully satisfied.

## Testing Strategy
- Unit tests:
  - token/color/path validation.
  - mapping resolution and updater behavior.
  - backup + atomic write behavior.
- Command tests:
  - parse/dispatch/exit codes.
  - dry-run and write mode behavior.
- Fixture strategy:
  - temporary fake theme directory trees under pytest temp dirs.

## Implementation Order
1. M1 (`show`/`set` + resolver)
2. M2 (3-file dry-run sync)
3. M4 (safe writes + backups)
4. M3 (remaining target updaters)
5. M5 (`diff` + reload)
6. M6 (hardening + polish)

Reason for order:
- early end-to-end value arrives with safe read/set and dry-run sync.
- write path is added before broadening all target formats to avoid unsafe rollout.

## Risk Register
- Format drift in target files can break regex-based replacements.
  - Mitigation: constrained parsers + robust fallback errors.
- Accidentally writing outside theme paths.
  - Mitigation: strict path guard checks before any IO.
- Reload command side effects.
  - Mitigation: run only on successful `--write`; add `--no-reload` option.

## Operational Checklist per PR/Change Batch
- Run `pytest`.
- Smoke test commands with a temporary theme fixture.
- Confirm dry-run performs zero writes.
- Confirm write mode creates backups and atomic writes.

## Post-MVP Backlog
- `set-many --file palette.toml`
- `doctor` command for out-of-sync detection
- import mode (derive `colors.toml` from existing theme files)
