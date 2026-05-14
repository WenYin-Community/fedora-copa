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

## Installation

### From source

```bash
git clone https://github.com/yourusername/copa.git
cd copa
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
copa search ghostty
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

### Manage Copr repos

```bash
copa copr list
copa copr enable owner/project
copa copr disable owner/project
copa copr remove owner/project
```

## Command Options

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

### Global options

| Option | Description |
|--------|-------------|
| `-V, --version` | Show version |
| `-v, --verbose` | Verbose output |

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

## Configuration File

Config file location: `~/.config/copa/config.toml`

```toml
[search]
enable_fedora = true
enable_rpmfusion = true
enable_terra_if_present = true
enable_copr = true

[install]
default_copr_post_action = "disable"

[backend]
prefer_dnf5 = true
fallback_to_dnf = true
```

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
