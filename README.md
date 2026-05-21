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
- **Regex search** - `copa search -x "^ghost"` for regex pattern matching (name only)
- **JSON output** - `copa --json search ghostty` for machine-readable output
- **Unified third-party repo management** - `copa repo list/enable/disable/remove`
- **Version fallback** - Copr and OBS both support chroot/repo version fallback (max 2 versions) with explicit risk warning
- **Parallel search** - Copr and OBS searched in parallel for faster results
- **Package name resolution** - searches inside the enabled repo to find the actual RPM name
- **Post-install strategy** - repo kept by default, user can disable/remove
- **Risk assessment** - automatic risk scoring for Copr/OBS packages
- **Install failure handling** - repo stays enabled on failure with disable/remove instructions
- **Shell completion** - bash and zsh completion scripts
- **Man page** - `man copa`

## Installation

### From source

```bash
git clone https://github.com/WenYin-Community/fedora-copa.git
cd fedora-copa
pip install --user .
```

### From Copr

```bash
sudo dnf copr enable ruojiner/fedora-copa
sudo dnf install fedora-copa
```

### From RPM

```bash
# Download from GitHub Releases
dnf install fedora-copa-*.noarch.rpm
```

### Dependencies

- Python 3.11+
- `dnf5` or `dnf` (dnf5 is default on Fedora 41+; RHEL 10+ uses dnf by default but dnf5 can be installed)
- `copr-cli`
- `python3-copr` (PyPI: `copr`)
- `httpx`
- `osc` (for OBS support)

Run `copa doctor` to check dependencies.

### OBS Authentication (optional)

OBS (openSUSE Build Service) requires authentication. To enable OBS support:

1. Register at [build.opensuse.org](https://build.opensuse.org)
2. Install `osc`: `sudo dnf install osc`
3. Configure credentials - create `~/.config/osc/oscrc`:
   ```ini
   [general]
   apiurl = https://api.opensuse.org

   [https://api.opensuse.org]
   user = your_username
   pass = your_password
   ```

Without OBS credentials, `copa install` will skip OBS search and only search Copr.

### dnf5 / dnf Compatibility

`copa` prioritizes **dnf5** (default on Fedora 41+). On systems with only `dnf` (e.g. RHEL 10+ where dnf5 is not installed), `copa` falls back to `dnf` automatically.

The following CLI differences affect this project and are handled internally by `DnfBackend`:

| Operation | dnf5 | dnf |
|-----------|------|-----|
| Filter by repo | `--repo <id>` | `--repoid <id>` |
| Package info | `repoquery --info` | `repoquery --queryinfo` |
| Copr plugin | Built-in (`dnf5 copr`) | Requires `dnf-plugins-core` (`dnf copr`) |
| `repolist --enabled` | Supported | Supported (output format may differ slightly) |
| `install / remove / makecache` | Supported | Supported |

`copa` auto-detects the binary via `get_dnf_binary()` and uses `DnfBackend._repo_flag` to select the correct `--repo` / `--repoid` flag. All subprocess calls force `LANG=C` to ensure consistent English output. No manual configuration needed.

## Usage

### Check environment

```bash
copa doctor
```

### Search packages

```bash
# Default: search Copr + OBS (when OBS is available)
copa search ghostty

# Multiple keywords (AND logic)
copa search ghostty terminal

# Also search Fedora, RPM Fusion, Terra
copa search --include-local-repo ghostty

# Regex search (match package names only)
copa search -x "^ghost"
copa search --regex "vim|neovim"

# Search specific sources
copa search --official-only vim
copa search --copr-only firefox

# JSON output
copa --json search ghostty
```

### Install packages

```bash
# Default: search Copr + OBS only
copa install ghostty

# Also search Fedora, RPM Fusion, Terra
copa install --include-local-repo ghostty

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

### Remove packages

```bash
# Remove a locally installed package (interactive selection)
copa remove spark

# Auto confirm
copa -y remove spark
```

`copa remove` searches installed packages matching the input, shows a list for selection, then calls `dnf5 remove`. Purely local operation, no network queries.

### Package info

```bash
# Show package info
copa info ghostty

# Show Copr project info
copa info owner/project

# JSON output
copa --json info ghostty
```

### List packages

```bash
# List third-party repos managed by copa
copa list

# List packages in Copr project
copa list --packages owner/project

# JSON output
copa --json list
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

### Query package dependencies

```bash
# Show package dependencies
copa repoquery ghostty --requires

# Show what package provides
copa repoquery ghostty --provides

# Show package files
copa repoquery ghostty --files

# Show package info (default)
copa repoquery ghostty

# JSON output
copa --json repoquery ghostty --requires
```

### Find packages providing a file

```bash
# Find packages providing a specific file
copa provides /usr/bin/vim

# Find packages providing a command
copa provides ghostty

# JSON output
copa --json provides /usr/bin/vim
```

## Command Options

### search command

| Option | Description |
|--------|-------------|
| `keyword [keyword ...]` | Search keywords (AND logic) |
| `--obs-only` | Search OBS only |
| `--no-obs` | Skip OBS search |
| `--include-local-repo` | Also search Fedora, RPM Fusion, Terra (default: Copr + OBS) |
| `--official-only` | Search Fedora official repos only |
| `--rpmfusion-only` | Search RPM Fusion only |
| `--copr-only` | Search Copr only |
| `-x, --regex` | Search using regex (name only) |

### install command

| Option | Description |
|--------|-------------|
| `--include-local-repo` | Also search Fedora, RPM Fusion, Terra (default: Copr + OBS only) |
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

### remove command

| Option | Description |
|--------|-------------|
| `package` | Package name to remove (substring match on installed packages) |
| `-y, --assumeyes` | Auto confirm |

### repo command

| Subcommand | Description |
|------------|-------------|
| `list` | List all third-party repos |
| `enable REPO` | Enable repo (format: `copr:owner/project` or `obs:project`) |
| `disable REPO` | Disable repo |
| `remove REPO` | Remove repo |

### repoquery command

| Option | Description |
|--------|-------------|
| `package` | Package name to query |
| `--requires` | Show package dependencies |
| `--provides` | Show what package provides |
| `--files` | Show package files |

### Global options

| Option | Description |
|--------|-------------|
| `-V, --version` | Show version |
| `--json` | Output in JSON format |
| `-h, --help` | Show help |

## Post-install Strategy

After installation, `copa` keeps the repo enabled by default and warns the user:

```
Copr repo owner/project is kept enabled.
Note: This repo will participate in system updates.
If you don't want this, you can disable or remove it:
  copa repo disable copr:owner/project
  copa repo remove copr:owner/project

Disable repo now? [y/N]:
```

## Version Fallback

Both Copr and OBS support version fallback when the current Fedora version is not available:

- **Copr**: If the project doesn't have a chroot for your Fedora version, tries older versions (e.g. Fedora 43 chroot on Fedora 44)
- **OBS**: If no repo for your Fedora version, tries older version repos
- Maximum 2 version fallback for both
- Explicit risk warning when version mismatch:

```
WARNING: Version fallback!
Project: owner/project
Current system: Fedora 44 (fedora-44-x86_64)
Fallback to: Fedora 43 (fedora-43-x86_64)
This package was built for an older Fedora version.
It may have dependency issues or not work correctly.

Continue anyway? [y/N]
```

Risk levels based on version gap:
- gap=0 (exact match): low
- gap=1 (one version back): medium
- gap=2 (two versions back): high

## Install Flow

`copa install` searches Copr + OBS by default (parallel). Add `--include-local-repo` to also search Fedora, RPM Fusion, Terra.

### Local Repo Install (Fedora / RPM Fusion / Terra) — requires `--include-local-repo`

```
copa install --include-local-repo <package>
  │
  ├─ 1. Search Fedora + RPM Fusion + Terra in sequence
  │     Command: dnf repoquery --info --repo <repo_id> *<package>*
  │     Collect all results into one list
  │
  ├─ 2. Deduplicate by package name
  │
  ├─ 3. Display numbered list
  │     [ 1] aftertheflood-sparks-bar-fonts-0:2.0-20.fc44 (Fedora)
  │     [ 2] lightspark-0:0.9.0-4.fc44 (RPM Fusion)
  │     [ 3] spark-0:0.8.2-1.fc44 (Terra)
  │
  ├─ 4. User selects [1-N], 's' to search Copr/OBS, 'q' to cancel
  │     ├─ Number → install selected package
  │     ├─ 's' → fall through to Copr/OBS search
  │     └─ 'q' → exit
  │
  ├─ 5. -y mode: auto-select first result
  │
  └─ 6. Install: sudo dnf5 install <selected_name>
```

### Copr Install Flow

```
copa install <package>
  │
  ├─ 1. Parallel search Copr + OBS (ThreadPoolExecutor, max_workers=2)
  │
  ├─ 2. Unified display list
  │     [ 1] [Copr] owner/project
  │           Chroot: ✓ | Risk: low
  │     [ 2] [OBS]  project/name
  │           Version: ✓ | Risk: medium
  │
  ├─ 3. User selects project (or --copr owner/project)
  │
  ├─ 4. Version fallback warning (version_gap > 0)
  │     └─ "Continue anyway? [y/N]"
  │
  ├─ 5. Enable repo: sudo dnf5 copr enable owner/project <chroot>
  │
  ├─ 6. Refresh cache: sudo dnf5 makecache --refresh
  │
  ├─ 7. Resolve package name in repo
  │     Command: dnf repoquery --info --repo copr:... *<package>*
  │     ├─ Try user input first, then project name
  │     └─ Always show list for user selection
  │
  ├─ 8. Confirm: "Install {name}? [Y/n]" (skipped with -y)
  │
  ├─ 9. Install: sudo dnf5 install {name}
  │     ├─ Success → save state, ask "Disable repo now? [y/N]"
  │     ├─ Failure → return 1, repo stays enabled, show instructions
  │     └─ Cancel → return 0, repo stays enabled, show instructions
  │
  └─ 10. Post-install: dnf5 copr disable (if user chooses)
```

### OBS Install Flow

```
copa install <package>
  │
  ├─ 1. Parallel search Copr + OBS
  │
  ├─ 2. User selects OBS project
  │
  ├─ 3. Version fallback warning (no repo for current Fedora)
  │     └─ "Continue anyway? [y/N]"
  │
  ├─ 4. Download repo file to /etc/yum.repos.d/
  │
  ├─ 5. Save state (immediately, before install)
  │
  ├─ 6. Refresh cache: sudo dnf5 makecache --refresh
  │
  ├─ 7. Resolve package name in repo
  │     Command: dnf repoquery --info --repo <obs_repo> *<package>*
  │     └─ Always show list for user selection
  │
  ├─ 8. Confirm: "Install {name}? [Y/n]" (skipped with -y)
  │
  ├─ 9. Install: sudo dnf5 install {name}
  │     ├─ Success → ask "Disable repo now? [y/N]"
  │     ├─ Failure → return 1, repo stays enabled, show instructions
  │     └─ Cancel → return 0, repo stays enabled, show instructions
  │
  └─ 10. Post-install: remove repo file (if user chooses)
```

### Failure Handling

On install failure, both Copr and OBS repos stay enabled. copa prints instructions:

```
Installation failed
Copr repo owner/project is kept enabled.
You can disable or remove it:
  copa repo disable copr:owner/project
  copa repo remove copr:owner/project
```

## Remove Flow

```
copa remove <package>
  │
  ├─ 1. Search installed packages
  │     Command: dnf repoquery --info --installed *<package>*
  │     └─ Purely local, no network
  │
  ├─ 2. Not found → "Package '<package>' is not installed" → return 1
  │
  ├─ 3. Deduplicate by name
  │
  ├─ 4. Single match:
  │     ├─ Show: <name>-<evr> (<repo>)
  │     ├─ Confirm: "Remove <name>? [y/N]" (skipped with -y)
  │     └─ sudo dnf5 remove <name>
  │
  ├─ 5. Multiple matches:
  │     ├─ Show numbered list with summary
  │     ├─ User selects [1-N, q to cancel]
  │     ├─ Confirm: "Remove <name>? [y/N]" (skipped with -y)
  │     └─ sudo dnf5 remove <name>
  │
  └─ 6. Done (no repo management, purely local)
```

Key points:
- Purely local operation, no network queries
- Substring matching via `*keyword*` glob pattern
- User must explicitly select which package to remove
- No automatic repo disable/remove after uninstall (use `copa repo disable/remove` separately)

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

## Shell Completion

### Bash

```bash
# System-wide
sudo cp completions/copa.bash /etc/bash_completion.d/

# User
mkdir -p ~/.bash_completion.d
cp completions/copa.bash ~/.bash_completion.d/
```

### Zsh

```bash
# System-wide
sudo cp completions/_copa /usr/share/zsh/site-functions/

# User
mkdir -p ~/.zsh/completions
cp completions/_copa ~/.zsh/completions/
```

## Development

```bash
# Install dev dependencies
pip install --user -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
mypy copa/

# Build RPM
make build
```

## License

GPL-2.0-or-later

## Acknowledgments

- [Fedora Copr](https://copr.fedorainfracloud.org/) - Fedora community build service
- [openSUSE Build Service](https://build.opensuse.org/) - Cross-distro build service
- [DNF5](https://github.com/rpm-software-management/dnf5) - Next-gen package manager
- [paru](https://github.com/Morganamilo/paru) - AUR helper (search logic inspiration)
