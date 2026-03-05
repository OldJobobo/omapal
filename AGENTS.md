# Repository Guidelines

## Project Structure & Module Organization
- Root-level Python modules:
  - `omapal.py`: CLI entrypoint and command dispatch (`show`, `set`, `sync`, `diff`).
  - `validators.py`: input and safety validation helpers.
  - `mappings.py`: canonical token definitions and target mapping specs.
  - `writers.py`: backup and atomic write primitives.
- Tests live in `tests/`:
  - `tests/test_cli.py` for command behavior.
  - `tests/test_validators.py` for token/color validation.
  - `tests/conftest.py` for test import path setup.
- Planning and project docs: `PLAN.md`, `INITINFO.md`, `DEVPLAN.md`, `README.md`.

## Build, Test, and Development Commands
- `python omapal.py --help`  
  Shows available commands and flags.
- `python omapal.py set background '#112233'`  
  Smoke-tests argument parsing and validation path.
- `pytest`  
  Runs the full test suite.
- Optional dev setup: `pip install -e '.[dev]'`  
  Installs the project and test dependencies from `pyproject.toml`.

## Coding Style & Naming Conventions
- Target runtime: Python 3.11+.
- Use 4-space indentation and keep code readable over clever.
- Naming:
  - modules/functions/variables: `snake_case`
  - classes/dataclasses: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- Keep command handlers in `omapal.py` thin; move reusable logic into modules.
- Prefer explicit errors with actionable messages (invalid token, invalid hex, unsafe path).

## Testing Guidelines
- Framework: `pytest`.
- Add/update tests with every functional change.
- Test files: `tests/test_<module_or_feature>.py`.
- Test names: `test_<expected_behavior>()`.
- Minimum expectation for new work:
  - one success-path test
  - one failure/validation test

## Commit & Pull Request Guidelines
- No established Git history is available in this directory yet; use Conventional Commits moving forward (e.g., `feat: add theme path resolver`, `fix: validate hex format`).
- Keep commits focused and atomic.
- PRs should include:
  - concise summary of what changed
  - why the change was needed
  - test evidence (`pytest` output)
  - any scope/safety notes (especially file-write behavior)

## Safety & Scope Rules
- Only read/write inside Omarchy theme directories:
  - `~/.config/omarchy/current/theme/*`
  - `~/.config/omarchy/themes/<theme-name>/*`
- Do not modify global configs outside theme directories.
