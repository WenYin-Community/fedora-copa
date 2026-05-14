# copa

[中文文档](README_zh.md)

DNF5-style Fedora Copr Package Assistant.

`copa` = **C**opr **P**ackage **A**ssistant

## Introduction

`copa` is a Copr package assistant for the Fedora / DNF5 ecosystem, providing a search and install experience similar to `paru` / `yay` on Arch, but with DNF-style command format.

Supported package sources:

1. **Fedora official repos** - highest priority
2. **RPM Fusion** - searched when enabled
3. **Terra** - searched when enabled
4. **Copr** - Fedora community build service
5. **openSUSE OBS** - cross-distro build service (with version fallback)

## Features

- **Multi-keyword AND search** - `copa search ghostty terminal` matches packages containing both words
- **Unified third-party repo management** - `copa repo list/enable/disable/remove`
- **Version fallback** - OBS packages from older Fedora versions with risk warning
- **Post-install strategy** - disable/remove repo after installation
- **Risk assessment** - automatic risk scoring for Copr/OBS packages

## Installation

### From source

```bash
git clone https://github.com/WenYin-Community/fedora-copa.git
cd fedora-copa
pip install --user .
```

### Dependencies

- Python 3.11+
- `dnf5` or `dnf`
- `copr-cli`
- `python3-copr` (PyPI: `copr`)
- `httpx`

Run `copa doctor` to check dependencies.

## Usage

### Check environment

```bash
copa doctor
```

### Search packages

```bash
# Single keyword
copa search ghostty

# Multiple keywords (AND logic)
copa search ghostty terminal

# Search specific sources
copa search --official-only vim
copa search --copr-only firefox
```

### Install packages

```bash
# Interactive install (search all sources by priority)
copa install ghostty

# Install from Copr only
copa install --copr-only ghostty

# Specify Copr project
copa install --copr rivenirvana/ghostty ghostty

# Install from OBS only
copa install --obs-only ghostty

# Preview mode (no execution)
copa install --dry-run ghostty

# Auto confirm (non-interactive)
copa -y install --copr owner/project ghostty
```

### Package info

```bash
# Show package info
copa info ghostty

# Show Copr project info
copa info owner/project
```

### List packages

```bash
# List third-party repos managed by copa
copa list

# List packages in Copr project
copa list --packages owner/project
```

### Manage third-party repos

```bash
# List all third-party repos (Copr + OBS)
copa repo list

# Enable repo
copa repo enable copr:owner/project
copa repo enable obs:project

# Disable repo
copa repo disable copr:owner/project
copa repo disable obs:project

# Remove repo
copa repo remove copr:owner/project
copa repo remove obs:project
```

### Audit repos

```bash
# Check health of third-party repos
copa audit
```

## Command Options

### search command

| Option | Description |
|--------|-------------|
| `keyword [keyword ...]` | Search keywords (AND logic) |
| `--official-only` | Search Fedora official repos only |
| `--rpmfusion-only` | Search RPM Fusion only |
| `--copr-only` | Search Copr only |

### install command

| Option | Description |
|--------|-------------|
| `--official-only` | Search Fedora official repos only |
| `--rpmfusion-only` | Search RPM Fusion only |
| `--copr-only` | Search Copr only |
| `--copr OWNER/PROJECT` | Use specified Copr repo |
| `--obs-only` | Search OBS only |
| `--no-obs` | Skip OBS search |
| `--allow-obs-fallback` | Allow OBS version fallback |
| `--keep-copr` | Keep Copr repo after install |
| `--dry-run` | Show operations without executing |
| `-y, --assumeyes` | Auto confirm |

### repo command

| Subcommand | Description |
|------------|-------------|
| `list` | List all third-party repos |
| `enable REPO` | Enable repo (format: `copr:owner/project` or `obs:project`) |
| `disable REPO` | Disable repo |
| `remove REPO` | Remove repo |

### Global options

| Option | Description |
|--------|-------------|
| `-V, --version` | Show version |
| `-h, --help` | Show help |

## Post-install Strategy

After installation, `copa` asks whether to keep the Copr/OBS repo:

```
Keep Copr repo owner/project enabled for future updates?

[1] Keep enabled
[2] Disable repo [default]
[3] Remove repo file
Select [1/2/3]:
```

Default behavior: disable repo (keep repo file)

## Version Fallback

OBS search supports version fallback:

- If current Fedora version has no matching package, tries previous version
- Maximum 2 version fallback
- Explicit risk warning when version mismatch

## State File

State file location: `~/.local/share/copa/state.json`

Records Copr/OBS repos enabled by `copa` for post-install cleanup.

## Development

```bash
# Install dev dependencies
pip install --user -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
mypy copa/
```

## License

GPL-2.0-or-later

## Acknowledgments

- [Fedora Copr](https://copr.fedorainfracloud.org/) - Fedora community build service
- [openSUSE Build Service](https://build.opensuse.org/) - Cross-distro build service
- [DNF5](https://github.com/rpm-software-management/dnf5) - Next-gen package manager
- [paru](https://github.com/Morganamilo/paru) - AUR helper (search logic inspiration)
