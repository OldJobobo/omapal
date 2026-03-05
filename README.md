# omapal

`omapal` is a local CLI for managing Omarchy theme palette colors from one source of truth (`colors.toml`) and syncing them to related theme files.

## Requirements

- Python 3.11+

## Quick Start

```bash
python omapal.py --help
```

Default behavior with no arguments is interactive mode. If `gum` is installed, menus and reports use `gum`.

```bash
python omapal.py
```

## Commands

- `omapal show [--theme <name>]`
- `omapal set <token> <#hex> [--theme <name>]`
- `omapal sync [--theme <name>] [--dry-run] [--write|-w] [--zed-template <path>] [--reload-mode auto|full|hypr] [--no-reload]`
- `omapal diff [--theme <name>] [--zed-template <path>]`

Examples:

```bash
python omapal.py sync
python omapal.py sync -w
python omapal.py diff --theme sparta
```

## Supported Sync Targets

- `alacritty.toml`
- `kitty.conf`
- `ghostty.conf`
- `colors.css`
- `aether.override.css`
- `gtk.css`
- `hyprland.conf`
- `hyprlock.conf`
- `btop.theme`
- `chromium.theme`
- `neovim.lua`
- `aether.zed.json`
- `vencord.theme.css`
- `wofi.css`
- `warp.yaml`
- `walker.css`
- `waybar.css`
- `mako.ini`
- `swayosd.css`

## Zed Template

`aether.zed.json` is rendered from a JSON template with placeholder tokens.

Template precedence:

1. `--zed-template <path>`
2. `OMAPAL_AETHER_ZED_TEMPLATE`
3. Bundled default: `templates/aether.zed.json`

## Development

Run tests:

```bash
pytest
```
