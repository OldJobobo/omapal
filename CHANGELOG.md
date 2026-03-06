# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-03-06

### Added
- Automated version management tool (`versioning.py`) with `current`, `bump`, and `set` commands.
- Packaging entrypoint `omapal-version` and test coverage for versioning workflows.

### Changed
- Interactive mode UI now applies theme-driven color treatment to menus, prompts, preflight, palette view, and sync/diff reporting.
- `Show Palette` now uses a structured boxed layout with separate ANSI (`color0`-`color15`) and core-token sections.
- Palette rendering improved with readable swatches, token label abbreviations for long non-ANSI names, and clearer grouping.

## [0.1.0] - 2026-03-04

### Added
- Initial project scaffold.
- CLI command wiring (`show`, `set`, `sync`, `diff`).
- Validation utilities and test scaffolding.
