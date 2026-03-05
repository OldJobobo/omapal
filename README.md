# omapal

`omapal` is a local CLI for managing Omarchy theme palette colors from one source of truth (`colors.toml`) and syncing them to related theme files.

## Status

Project scaffold is initialized. Core sync logic is not implemented yet.

## Requirements

- Python 3.11+

## Quick Start

```bash
python omapal.py --help
```

## Planned Commands

- `omapal show [--theme <name>]`
- `omapal set <token> <#hex> [--theme <name>]`
- `omapal sync [--theme <name>] [--dry-run] [--write]`
- `omapal diff [--theme <name>]`

## Development

Run tests:

```bash
pytest
```
