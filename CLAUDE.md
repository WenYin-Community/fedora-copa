# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`copa` is a Copr package assistant for the Fedora / DNF5 ecosystem, providing a search and install experience similar to `paru`/`yay` on Arch. Supports 5 package sources: Fedora official, RPM Fusion, Terra, Copr, openSUSE OBS.

## Commands

```bash
# Install dev dependencies
pip install --user -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_cli.py -v

# Run single test class/method
pytest tests/test_cli.py::TestFilterByKeywords::test_single_keyword_match -v

# Lint
ruff check .
mypy copa/

# Build RPM
make build          # Fedora 43 + 44
make build-srpm     # Source RPM
make test           # pytest tests/ -v
make lint           # ruff + mypy
make clean          # Clean build artifacts
```

## Architecture

### Modules

```
copa/
├── cli.py           # argparse CLI entry, all cmd_* functions, _resolve_package_name, filter functions
├── search.py        # SearchEngine - multi-backend aggregation, risk assessment, version fallback
├── dnf_backend.py   # DnfBackend - dnf5/dnf subprocess wrapper
├── copr_backend.py  # CoprBackend - python-copr (copr.v3) API wrapper with retry
├── obs_backend.py   # OBSBackend - openSUSE OBS XML API (httpx, sync) with retry
├── config.py        # Config dataclass, TOML config file read/write
├── state.py         # AppState dataclass, JSON state file tracking enabled repos
└── utils.py         # Utility functions (retry decorator, command detection, confirm prompt)
```

### Data Flow

1. User input → `cli.py` (argparse) → dispatch to `cmd_*` functions
2. `cmd_*` initializes backends: `DnfBackend`, `CoprBackend`, `OBSBackend`
3. `SearchEngine` aggregates multi-backend results (Copr + OBS searched in parallel via `ThreadPoolExecutor`)
4. Install flow: search → user selects → version fallback check → enable repo → resolve package name → confirm → `dnf install` → save state

### Key Design Decisions

- **Parallel search**: Copr and OBS searched concurrently via `ThreadPoolExecutor(max_workers=2)`
- **Version fallback**: Both Copr (chroot) and OBS (repo) support max 2 version fallback with explicit risk warning and user confirmation
- **Package name resolution**: `_resolve_package_name()` searches inside the enabled repo to find the actual RPM name (project name != package name). Falls back to project name if user input not found. Always lists results for user selection.
- **Repo stays enabled on failure/cancel**: User gets explicit disable/remove instructions, no silent auto-disable
- **Retry with backoff**: `@retry` decorator (3 attempts, exponential backoff), only retries on connection/timeout errors (not 4xx HTTP errors)
- **Risk assessment**: `_assess_copr_risk()` and `_assess_obs_risk()` based on keywords, version gap (gap=0: low, gap=1: medium, gap>=2: high, no match: blocked)
- **State tracking**: `~/.local/share/copa/state.json` records repos enabled by copa for cleanup
- **Config file**: `~/.config/copa/config.toml` controls search source toggles, install strategy
- **Backend isolation**: Three Backend classes each encapsulate external system interaction, no cross-dependency
- **Subprocess calls**: `DnfBackend` calls `dnf5`/`dnf` CLI via `subprocess.run`, not libdnf5 Python bindings
- **Sudo output**: sudo commands use `capture_output=False` so password prompt is visible
- **dnf5/dnf compatibility**: Project prioritizes dnf5. dnf is fallback via `get_dnf_binary()`. Key difference: dnf5 uses `--repo`, dnf uses `--repoid`. `DnfBackend._repo_flag` property handles this automatically. RHEL 10+ uses dnf by default but dnf5 can be installed.

### Install Flow Summary

**Default** (Copr + OBS): parallel search → select → version fallback check → enable repo → `makecache` → resolve package name → confirm → `dnf5 install` → save state → ask disable

**OBS authentication**: OBS API requires credentials in `~/.config/osc/oscrc` (user/pass for `api.opensuse.org`). Without credentials, OBS is skipped with a warning. API base: `https://api.opensuse.org`. Repo file download: `https://download.opensuse.org/repositories/{project}/{repository}/{project}.repo`. Repo ID inside file: section name (colons → underscores, e.g. `home:Foo` → `[home_Foo]`). `osc` is a required dependency (Fedora official repo).

**Local repos** (`--include-local-repo`): search Fedora + RPM Fusion + Terra → deduplicate → numbered list → user selects [1-N] or 's' to search Copr/OBS → `dnf5 install`

**Remove**: search installed packages (`dnf5 repoquery --info --installed *keyword*`) → deduplicate → list for user selection → confirm → `dnf5 remove` (purely local, no network, no repo management)

### Test Patterns

- `DnfBackend` tests use `unittest.mock.patch` to mock `subprocess.run`
- `AppState`/`Config` tests use `pytest.fixture` with `tmp_path` for temp files
- CLI filter functions (`_filter_by_keywords` etc.) use Mock objects directly
- 51 unit tests total

## Tech Stack

- Python 3.11+, `tomllib` (stdlib), `dataclasses`
- Dependencies: `copr` (python-copr), `httpx`
- Build: setuptools + wheel, RPM packaging via `rpm/copa.spec`
- Lint: ruff (line-length=100, target py311), mypy
- CI: GitHub Actions (`.github/workflows/ci.yml`, `build-rpm.yml`)

## Notes

- `cli.py` `cmd_*` functions are long (contain interactive logic), maintain ANSI color codes and interaction flow consistency when editing
- `OBSBackend` uses `httpx.Client` (sync), not async
- OBS API base: `https://api.opensuse.org` (requires auth from `~/.config/osc/oscrc`)
- Search supports multi-keyword AND logic and regex mode (`-x`), filter functions at bottom of `cli.py`
- Copr search via `copr.v3.Client` `project_proxy.search()`, substring match on project name/owner only (not description)
- Chroot detection: `VERSION_ID="?(\d+)"?` regex handles both quoted and unquoted VERSION_ID in os-release

### dnf5 / dnf Compatibility

Project prioritizes **dnf5** (default on Fedora 41+). dnf is supported as fallback for older systems.

**Key CLI differences** (must handle when adding new dnf commands):

| Feature | dnf5 | dnf |
|---------|------|-----|
| Repo filter flag | `--repo` | `--repoid` |
| Package info flag | `--info` | `--queryinfo` |
| `copr` subcommand | Built-in | Requires `dnf-plugins-core` |

`DnfBackend._repo_flag` property auto-selects the correct flag based on detected binary. When adding new methods that accept a `repo` parameter, always use `self._repo_flag` instead of hardcoding `--repo`.

`DnfBackend._run()` forces `LANG=C` and `LC_ALL=C` in the subprocess environment to ensure English field names in `repoquery --info` output (dnf5 localizes field names by default).

**Platform support**:
- Fedora 41+: dnf5 is default
- RHEL 10+ / CentOS Stream 10+: dnf by default, dnf5 can be installed manually
- Older systems: dnf fallback via `get_dnf_binary()` in `copa/utils.py`

## Code Style

- **All UI text must be English**: user-facing strings (print, prompts, error messages)
- **All code comments must be English**: inline comments, docstrings
- No Chinese in source code (`copa/`) or tests (`tests/`)
- CLAUDE.md and README_zh.md are documentation files, Chinese is acceptable there
