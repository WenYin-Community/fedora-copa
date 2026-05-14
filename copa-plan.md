# copa: DNF5-style Fedora Copr Package Assistant Implementation Plan

## 1. Project Positioning

`copa` is a Copr package assistant for the Fedora / DNF5 ecosystem.

The goal is to provide a search and install experience similar to `paru` / `yay` on Arch, but with DNF-style command format instead of Pacman style.

One-line description:

> `copa` is a DNF5-style Fedora Copr package assistant that supports searching Fedora official repos, RPM Fusion, Terra, and Copr repositories, helping users select Copr repos and install software via `dnf5`.

Name meaning:

> `copa` = Copr Package Assistant

## 2. Background and Constraints

Current Fedora DNF5 environment notes:

1. DNF5's Copr plugin does not have a `search` subcommand.
2. Therefore cannot rely on `dnf5 copr search <keyword>` or `dnf copr search <keyword>`.
3. Copr search capability should be implemented via Copr HTTP API / Web search endpoint.
4. `copr-cli` is a hard dependency for querying package lists, package details, and build info within Copr projects.
5. Local repo management still uses `dnf5 copr enable/list/disable/remove`.
6. Final software installation is done via `dnf5 install`.

Recommended architecture:

| Module | Implementation | Purpose |
|--------|---------------|---------|
| Official repo search | `dnf5 search` / `dnf5 repoquery` | Search Fedora official repos and enabled repos |
| RPM Fusion search | `dnf5 repoquery` with RPM Fusion repo filter | Search RPM Fusion |
| Terra search | Check if Terra is enabled then query | Search enabled Terra repos |
| Copr global search | Copr HTTP API / Web endpoint | Replace missing `dnf5 copr search` |
| Copr project query | `copr-cli`, with API if needed | Query project package list, details, build status |
| Copr repo management | `dnf5 copr enable/list/disable/remove` | Enable, disable, delete local Copr repos |
| Package install | `dnf5 install` | Install packages via DNF5 |
| Cache refresh | `dnf5 makecache --refresh` | Refresh metadata after enabling Copr |

## 3. Command Style

Command name:

```text
copa
```

Command format compatible with DNF:

```text
copa [global options] <command> [command options] [arguments]
```

Not promoting Pacman/Paru style `-S`, `-Ss`, `-Q` parameters.

Recommended main commands:

```text
copa search <keyword>
copa install <package>
copa info <package>
copa info <owner/project>
copa list
copa list --packages <owner/project>
copa repoquery <package>
copa remove <package>
copa upgrade
copa audit
copa repo list
copa repo enable copr:<owner/project> [chroot]
copa repo disable copr:<owner/project>
copa repo remove copr:<owner/project>
```

## 4. Search Priority

Default search order for `copa install <package>`:

1. Fedora official repos
2. RPM Fusion
3. Third-party repo Terra (if user has added and enabled Terra repo)
4. Copr
5. openSUSE Build Service (OBS)

Terra is optional:

- If user has added Terra repo, it participates in search.
- If user has not added Terra repo, it is skipped.
- `copa` does not proactively add Terra repo for users.

OBS as supplementary source:

- OBS provides cross-distro package build services with many packages not in Fedora.
- OBS search results require users to manually add repo files, not auto-enabled.
- OBS package versions may not match current Fedora version, requiring version fallback mechanism.

## 5. `copa install` Default Flow

Example installing `ghostty`:

```text
copa install ghostty
```

Complete flow:

1. Detect currently enabled repos.
2. Search Fedora official repos.
3. If Fedora official repos have no results, search RPM Fusion.
4. If Terra is enabled, search Terra.
5. If previous sources have no suitable results, or user chooses to continue searching Copr, search Copr repos.
6. When searching Copr, first query Copr repo names and show candidate list.
7. Ask user which Copr repo to add.
8. Enable selected Copr repo based on user choice.
9. Execute `dnf5 makecache --refresh`.
10. Execute `dnf5 install <package>`.
11. After installation, ask user whether to keep this Copr.
12. If user doesn't keep it, delete/remove the corresponding Copr repo.
13. If Copr also has no suitable results, or user chooses to continue searching OBS, search OBS repos.
14. When searching OBS, show matching projects and package info.
15. Provide OBS repo file download link for manual addition by user.
16. If OBS package version doesn't match current Fedora version, warn user about risk and provide fallback version.

## 6. Detect Enabled Repos

First detect currently enabled repos at runtime:

```bash
dnf5 repolist --enabled
```

Classification logic:

| Type | Detection Method |
|------|-----------------|
| Fedora official | repo id contains `fedora`, `updates`, `updates-testing`, etc. |
| RPM Fusion | repo id contains `rpmfusion-free`, `rpmfusion-nonfree` |
| Terra | repo id contains `terra` |
| Copr | repo id starts with `copr:` or `coprdep:` |
| OBS | repo id starts with `home_` or `home:` |

## 7. Fedora Official Repo Search

Prioritize searching Fedora official repos:

```bash
dnf5 repoquery --repoid=fedora --repoid=updates <package>
```

If system has `updates-testing` enabled, can optionally include based on user settings.

If package found, ask user whether to continue searching next source. Default behavior is to install from current source (user presses Enter to install):

```text
Found in Fedora repositories:

<package>.x86_64  <version>  fedora/updates

Press Enter to install from Fedora, or type 's' to continue searching [Install/search]:
```

Behavior rules:

- Press Enter directly: Install from Fedora official repos.
- Type `s` / `search`: Continue searching RPM Fusion.
- Type `q` / `quit`: Exit.

If user confirms installation, execute:

```bash
sudo dnf5 install <package>
```

At this point, do not enter subsequent RPM Fusion / Terra / Copr flow.

## 8. RPM Fusion Search

If Fedora official repos have no results, search RPM Fusion:

```bash
dnf5 repoquery \
  --repoid=rpmfusion-free \
  --repoid=rpmfusion-free-updates \
  --repoid=rpmfusion-nonfree \
  --repoid=rpmfusion-nonfree-updates \
  <package>
```

If system has not enabled RPM Fusion, skip it without proactively adding.

If found, ask user whether to continue searching. Default behavior is to install from RPM Fusion (user presses Enter to install):

```text
Found in RPM Fusion:

<package>.x86_64  <version>  <rpmfusion-repo>

Press Enter to install from RPM Fusion, or type 's' to continue searching [Install/search]:
```

Behavior rules:

- Press Enter directly: Install from RPM Fusion.
- Type `s` / `search`: Continue searching Terra, or Copr if Terra not enabled.
- Type `q` / `quit`: Exit.

## 9. Terra Search

If Terra repo is detected as enabled, search Terra:

```bash
dnf5 repoquery --repoid='terra*' <package>
```

In actual implementation, find all repo ids containing `terra` from `dnf5 repolist --enabled` results, then add each to query.

If found, ask user whether to continue searching. Default behavior is to install from Terra (user presses Enter to install):

```text
Found in Terra repositories:

<package>.x86_64  <version>  terra

Press Enter to install from Terra, or type 's' to continue searching Copr [Install/search]:
```

Behavior rules:

- Press Enter directly: Install from Terra.
- Type `s` / `search`: Continue searching Copr.
- Type `q` / `quit`: Exit.

If user hasn't enabled Terra, skip Terra directly without prompting to add.

## 10. Copr Search Flow

If Fedora / RPM Fusion / Terra have no suitable results, or user actively uses `--copr-only`, enter Copr search.

Copr search must first show repo candidate list, not allowing automatic enabling of first result.

Search sources:

1. Copr API project search.
2. Copr API package name attribute search.
3. Copr built package / NEVRA search.
4. Use `copr-cli` for secondary verification of candidate projects.

Candidate list display focus:

- Copr repo name, i.e., `owner/project`
- Description
- Whether it supports current Fedora chroot
- Recent build status
- Whether it provides target package
- Risk warning

Example:

```text
Copr repositories matching "ghostty":

[1] rivenirvana/ghostty
    Description: Fast, native, feature-rich terminal emulator
    Fedora 43 x86_64: yes
    Latest build: succeeded
    Risk: normal

[2] burhanverse/ghostty
    Description: Automated TIPS Build for Ghostty
    Fedora 42 x86_64: yes
    Latest build: succeeded
    Risk: current Fedora release not matched

Select a Copr repository to enable [1-2, q to cancel]:
```

User must explicitly select a repo before continuing.

## 11. Copr API and `copr-cli` Responsibility Division

`copr-cli` is a hard dependency of `copa`. Copr API is mainly used to supplement global search capability, while `copr-cli` is mainly used for reliable queries of known projects.

### Copr API

Used to supplement the lack of Copr search commands in DNF5.

Recommended usage:

- Project search: `/api_3/project/search?query=<keyword>`
- Project details: `/api_3/project/?ownername=<owner>&projectname=<project>`
- Package list: `/api_3/package/list?ownername=<owner>&projectname=<project>`
- Package details: `/api_3/package/?ownername=<owner>&projectname=<project>&packagename=<package>`
- Build list: `/api_3/build/list?ownername=<owner>&projectname=<project>&packagename=<package>`

### `copr-cli`

Prioritize for known project queries:

```bash
copr-cli list <owner>
copr-cli list-packages <owner/project>
copr-cli list-package-names <owner/project>
copr-cli get-package <owner/project> <package>
copr-cli monitor <owner/project>
```

### `dnf5 copr`

Only responsible for local Copr repo management:

```bash
dnf5 copr list
sudo dnf5 copr enable <owner/project> [chroot]
sudo dnf5 copr disable <owner/project>
sudo dnf5 copr remove <owner/project>
```

## 11.5 OBS Search Flow

If Fedora / RPM Fusion / Terra / Copr have no suitable results, or user actively uses `--obs-only`, enter OBS search.

### OBS Introduction

openSUSE Build Service (OBS) is a cross-distro package build service providing packages for multiple Linux distributions, including Fedora.

- **API Base URL**: `https://api.opensuse.org`
- **CLI tool**: `osc` (written in Python, installable via pip or dnf)
- **Anonymous access**: Read-only operations don't require authentication

### OBS Search Implementation

Use OBS REST API to search packages:

```bash
# Search projects
curl -H "Accept: application/xml; charset=utf-8" \
  "https://api.opensuse.org/search/project?match=contains(@name,'ghostty')"

# Search packages
curl -H "Accept: application/xml; charset=utf-8" \
  "https://api.opensuse.org/search/package?match=contains(@name,'ghostty')"

# Query Fedora version binary packages
curl -H "Accept: application/xml; charset=utf-8" \
  "https://api.opensuse.org/search/released/binary?match=name='ghostty'+and+repository='Fedora_43'"
```

### Candidate List Display

```text
OBS packages matching "ghostty":

[1] home:user1/ghostty
    Project: home:user1
    Description: Ghostty terminal emulator
    Fedora 43 x86_64: yes
    Version: 1.0.0
    Risk: normal

[2] science/ghostty
    Project: science
    Description: Scientific computing terminal
    Fedora 42 x86_64: yes (fallback)
    Version: 0.9.5
    Risk: version mismatch - Fedora 42 package on Fedora 43

Select an OBS package [1-2, q to cancel]:
```

### Version Matching and Fallback Strategy

**Core principle**: Prioritize packages matching current Fedora version. If not available, fallback to previous version with explicit risk warning.

Version matching logic:

1. Query packages for current Fedora version (e.g., `fedora-43`)
2. If not found, query previous version (e.g., `fedora-42`)
3. If fallback version found, **must** warn user about risk

Risk warning example:

```text
WARNING: Version mismatch detected!

Package: ghostty
Available for: Fedora 42 x86_64
Your system: Fedora 43 x86_64

This package was built for an older Fedora version. It may:
- Have unmet dependencies
- Not work correctly with your system libraries
- Cause system instability

Do you want to proceed anyway? [y/N]:
```

Fallback version limits:

- Maximum 2 version fallback (e.g., Fedora 43 → 42 → 41)
- Packages with more than 2 version gap not recommended
- Rawhide does not participate in fallback, must exact match

### OBS Repo Addition Method

OBS repos are automatically downloaded by `copa` and added to `/etc/yum.repos.d/`, then ask user whether to install:

```text
Found OBS package: ghostty
Project: home:user1
Repository: Fedora_43
Version: 1.0.0

Downloading repo file to /etc/yum.repos.d/obs_home_user1.repo...
✓ Repo file downloaded.

The following commands will be executed:

  sudo dnf5 makecache --refresh
  sudo dnf5 install ghostty

Press Enter to install, or type 'q' to cancel [Install/quit]:
```

Implementation flow:

```bash
# 1. Auto-download repo file (no user confirmation needed)
sudo curl -o /etc/yum.repos.d/obs_<project>.repo \
  "https://download.opensuse.org/repositories/<project>/Fedora_43/<project>.repo"

# 2. Ask user whether to continue (default Enter = install)
# After user presses Enter:

# 3. Refresh cache
sudo dnf5 makecache --refresh

# 4. Install package
sudo dnf5 install <package>

# 5. Ask whether to keep OBS repo (default disable)
```

Behavior rules:

- Downloading repo file is automatic, no user confirmation needed
- After download, show commands to be executed and ask user
- Press Enter directly: Start installation
- Type `q` / `quit`: Cancel operation (repo file already downloaded, user can manually clean up or keep)
- After installation, ask whether to keep OBS repo, default disable

### OBS Post-install Retention Strategy

Similar to Copr, ask user whether to keep OBS repo after installation:

```text
Package installed successfully.

Keep OBS repository home:user1 enabled for future updates?

[1] Keep enabled
[2] Disable repo [default]
[3] Remove repo file
Select [1/2/3]:
```

Default strategy: Disable OBS repo (consistent with Copr)

- Keep enabled: OBS repo continues to participate in system updates
- Disable repo: Keep repo file but disable
- Remove repo file: Completely remove OBS repo

### OBS Repo File Naming

To avoid conflicts, OBS repo files are named:

```text
/etc/yum.repos.d/obs_<project_name>.repo
```

Where `:` in `<project_name>` is replaced with `_`, for example:

- `home:user1` → `obs_home_user1.repo`
- `science` → `obs_science.repo`

### Differences Between OBS and Copr

| Feature | Copr | OBS |
|---------|------|-----|
| Repo management | `dnf5 copr enable/disable` | Download repo file + `dnf config-manager` |
| Search | Copr API | OBS API |
| Version matching | Chroot mechanism | Repository name matching |
| Automation level | High (auto-enable) | Medium (auto-download repo) |
| Post-install handling | `dnf5 copr disable` | `dnf config-manager --set-disabled` |
| Risk warning | Risk scoring | Version mismatch warning |

## 12. Enable User-Selected Copr

After user selects Copr, for example:

```text
rivenirvana/ghostty
```

Execute:

```bash
sudo dnf5 copr enable rivenirvana/ghostty fedora-43-x86_64
```

Recommend `copa` to detect current chroot itself and pass explicitly, rather than relying entirely on `dnf5 copr enable` auto-detection.

Chroot format:

```text
fedora-<releasever>-<arch>
```

Example:

```text
fedora-43-x86_64
```

Rawhide example:

```text
fedora-rawhide-x86_64
```

## 13. makecache and install

After enabling Copr, must refresh cache before installing.

Note: Don't use single `&`:

```bash
# Not recommended
dnf makecache & dnf install <package>
```

Single `&` will run the previous command in background, which may cause cache not ready when installing.

Recommended sequential execution:

```bash
sudo dnf5 makecache --refresh
sudo dnf5 install <package>
```

Or use `&&`:

```bash
sudo dnf5 makecache --refresh && sudo dnf5 install <package>
```

## 14. Copr Retention Strategy After Installation

After installation, must ask user whether to keep the just-enabled Copr repo.

Recommended interaction:

```text
Package installed successfully.

Keep Copr repository rivenirvana/ghostty enabled for future updates?

[1] Keep enabled
[2] Disable repo
[3] Remove repo file
Select [1/2/3]:
```

Three options meaning:

| Option | Behavior |
|--------|----------|
| Keep enabled | Keep Copr enabled, can continue receiving updates |
| Disable repo | Disable Copr, but keep repo file |
| Remove repo file | Remove Copr repo file |

Default strategy:

```text
Default: disable repo after installation
```

Reasons:

- Safer than keeping enabled, prevents Copr from participating in future system upgrades.
- Gentler than directly deleting repo file, user can re-enable later.
- If user explicitly chooses to delete, then execute remove repo/file.

After installation, still ask user, but when pressing Enter directly, use default behavior: disable Copr.

## 15. If User Doesn't Keep Copr

If user chooses default behavior, disable Copr:

```bash
sudo dnf5 copr disable <owner/project>
```

If user explicitly chooses to delete repo file, prioritize executing:

```bash
sudo dnf5 copr remove <owner/project>
```

This is more reliable than directly deleting files.

If `dnf5 copr remove` fails, then fallback to deleting repo file.

Copr repo files are typically located at:

```text
/etc/yum.repos.d/
```

Filenames typically like:

```text
_copr:copr.fedorainfracloud.org:rivenirvana:ghostty.repo
```

But in actual implementation, don't hardcode filenames. Scan `/etc/yum.repos.d/`, match:

- `copr.fedorainfracloud.org`
- owner
- project

Then delete corresponding files.

## 16. Recommended Command Options

`install` command should support:

```text
copa install <package>
copa install --official-only <package>
copa install --rpmfusion-only <package>
copa install --terra-only <package>
copa install --copr-only <package>
copa install --copr <owner/project> <package>
copa install --obs-only <package>
copa install --keep-copr <package>
copa install --remove-copr-after-install <package>
copa install --disable-copr-after-install <package>
copa install --no-terra <package>
copa install --no-obs <package>
copa install --allow-obs-fallback <package>
```

Option meanings:

| Option | Behavior |
|--------|----------|
| No args | Search in order: Fedora → RPM Fusion → Terra → Copr → OBS |
| `--official-only` | Search Fedora official repos only |
| `--rpmfusion-only` | Search RPM Fusion only |
| `--terra-only` | Search Terra only (if Terra enabled) |
| `--copr-only` | Search Copr only |
| `--copr owner/project` | Don't search Copr, use specified Copr directly |
| `--obs-only` | Search OBS only |
| `--keep-copr` | Keep Copr after installation |
| `--remove-copr-after-install` | Delete Copr repo after installation |
| `--disable-copr-after-install` | Disable Copr after installation but keep repo file (default) |
| `--no-terra` | Skip Terra even if enabled |
| `--no-obs` | Skip OBS search |
| `--allow-obs-fallback` | Allow OBS version fallback (default requires confirmation) |

## 17. Global Options Recommendations

Compatible with DNF style:

```text
copa -y install <package>
copa --assumeyes install <package>
copa --assumeno install <package>
copa --refresh search <keyword>
copa --releasever 43 search <keyword>
copa --arch x86_64 search <keyword>
copa --chroot fedora-43-x86_64 install <package>
copa --dry-run install <package>
copa -v search <keyword>
```

Option meanings:

| Option | Meaning |
|--------|---------|
| `-y` / `--assumeyes` | Auto confirm |
| `--assumeno` | Default no, preview only |
| `--refresh` | Refresh DNF/Copr metadata |
| `--releasever` | Specify Fedora version |
| `--arch` | Specify architecture |
| `--chroot` | Specify Copr chroot |
| `--dry-run` | Show operations without executing |
| `-v` / `--verbose` | Show detailed info |

## 18. Recommended Interaction Example

```text
$ copa install ghostty

Searching Fedora repositories...
  No package found.

Searching RPM Fusion repositories...
  No package found.

Checking Terra repository...
  Terra repo is enabled.
  No package found.

Searching Copr repositories...
  Found matching Copr repositories:

  1. rivenirvana/ghostty
     Description: Fast, native, feature-rich terminal emulator
     Chroot: fedora-43-x86_64 supported
     Latest build: succeeded
     Risk: normal

  2. burhanverse/ghostty
     Description: Automated TIPS Build for Ghostty
     Chroot: fedora-42-x86_64 supported
     Latest build: succeeded
     Risk: current Fedora release not matched

Select Copr repository to enable [1-2, q]: 1

Selected: rivenirvana/ghostty

The following commands will be executed:

  sudo dnf5 copr enable rivenirvana/ghostty fedora-43-x86_64
  sudo dnf5 makecache --refresh
  sudo dnf5 install ghostty

Continue? [y/N]: y

Enabling Copr repository...
Refreshing metadata...
Installing package...

Package installed successfully.

Keep Copr repository rivenirvana/ghostty enabled for updates?
  1. Keep enabled
  2. Disable only [default]
  3. Remove repo file

Select [1/2/3]: 

Disabling Copr repository...
Done.
```

## 19. Security Principles

Core security principles of `copa`:

1. Don't auto-enable first Copr search result.
2. Must first show Copr repo list.
3. User must explicitly select Copr repo to enable.
4. Must refresh cache after enabling Copr before installing.
5. Must ask whether to keep Copr after installation.
6. If user doesn't keep, should clean up via `dnf5 copr remove` or deleting repo file.
7. Terra only participates in search when user has enabled it, not proactively added.
8. Fedora official repos have highest priority.
9. RPM Fusion only participates in search when enabled, not proactively added.
10. Copr is third-party community repo, must warn user about risks.
11. OBS repos require manual addition by user, not auto-enabled.
12. When OBS package version doesn't match current Fedora version, must explicitly warn about risk.
13. OBS version fallback supports maximum 2 version gap.

## 20. Final Flow Summary

Final behavior of `copa install <package>`:

```text
1. Search Fedora official repositories.
2. Search RPM Fusion repositories if enabled.
3. Search Terra repositories if enabled.
4. Search Copr and OBS repositories simultaneously.
5. Show matching packages from Copr/OBS in unified list.
6. Ask user to select package by number.
7. If selected from Copr: Enable the Copr repository.
8. If selected from OBS: Download repo file to /etc/yum.repos.d/.
9. Run dnf5 makecache --refresh.
10. Run dnf5 install <package>.
11. Ask whether to keep the repo.
12. By default, disable the repo after installation.
```

## 21. Issues Still Needing Improvement

Current plan has defined core interaction flow and key decisions, but before actual implementation, the following design details need to be supplemented.

### 21.1 DNF5 Parameter Compatibility Needs Testing

Commands like `dnf5 repoquery --repoid=...` and `dnf5 makecache --refresh` in the document are design examples. During actual implementation, need to verify item by item for target Fedora version.

Need to confirm:

1. What parameter DNF5 current version uses to specify repo: `--repoid`, `--repo`, `--enablerepo`, or other forms.
2. Whether `dnf5 repoquery` supports passing multiple repo filter parameters at once.
3. Whether `dnf5 makecache` can refresh only newly enabled Copr repo.
4. `dnf5 copr enable` chroot auto-detection behavior on different Fedora versions, Rawhide, non-x86_64 architectures.
5. Whether `dnf5 copr remove` always correctly deletes corresponding `/etc/yum.repos.d/` files.

Improvement suggestions:

- Encapsulate a `DnfBackend` in code, don't scatter hardcoded commands in business logic.
- Detect `dnf5` capability at startup, fallback to `dnf` if necessary.
- Add `copa doctor` command for checking `dnf5`, `dnf5-command(copr)`, `copr-cli`, network, repo status.

### 21.2 Need to Implement Repo Source Limitation During Installation

Current flow searches in order Fedora → RPM Fusion → Terra → Copr, but if executing plain:

```bash
sudo dnf5 install <package>
```

DNF resolver may still select packages with higher versions from other enabled repos, rather than the source user just confirmed.

For example:

- User chooses to install from Fedora official, but Terra has higher version.
- User chooses to install from Copr, but another enabled Copr has same-name package.
- User chooses RPM Fusion, but other third-party repos provide higher EVR packages.

Improvement suggestions:

1. After user selects a source, installation should try to limit to that source.
2. For Fedora / RPM Fusion / Terra, can show repo id to be used before installation.
3. For Copr, after enabling, should identify new repo id and try to limit to that repo during installation.
4. If dependency resolution requires using other repos, should show user for confirmation before installation.

Confirmed strategy:

> Default strictly limit target package source, respect user-selected source; allow DNF to resolve dependencies from base system repos, but if target package itself comes from non-user-selected repo, should abort and prompt.

### 21.3 Need to Record Whether Copr Repo Originally Existed

When asking whether to keep Copr after installation, need to distinguish two situations:

1. This Copr was newly enabled by `copa` this time.
2. This Copr already existed before running `copa`.

If user had already enabled this Copr, `copa` shouldn't default to deleting it after installation.

Improvement suggestions:

- Record currently enabled Copr list before enabling Copr.
- Only newly enabled Copr enters post-install cleanup flow.
- For existing Copr, only ask whether to keep status quo, not default to delete.
- Record `enabled_by_copa`, enable time, installed package name, repo id in local state file.

Suggested state file location:

```text
~/.local/share/copa/state.json
```

Suggested cache location:

```text
~/.cache/copa/
```

### 21.4 Need to Handle Rollback After Copr Enable Installation Failure

If flow fails halfway, for example:

1. Copr enabled successfully.
2. `makecache` failed.
3. `dnf5 install` failed.
4. User pressed Ctrl+C to interrupt.

At this point, system may have a just-enabled but unused Copr repo remaining.

Improvement suggestions:

- Use transactional flow to record each step's status.
- If Copr was newly enabled this time and installation failed, should ask whether to immediately remove.
- In `--assumeyes` mode, recommend default rollback of newly enabled but not successfully installed Copr.
- Capture interrupt signal, try to execute cleanup logic.

### 21.5 Copr Search Results Need Scoring and Risk Warning

Just showing Copr repo names is not enough, need to help users judge which repo is more trustworthy.

Suggested scoring dimensions:

| Dimension | Description |
|-----------|-------------|
| Package name match | Whether it exactly provides the package name user input |
| Current chroot support | Whether it supports current Fedora version and architecture |
| Recent build status | Whether recent build succeeded |
| Build freshness | How long since last successful build |
| Project description quality | Whether it has clear description, homepage, contact info |
| Risk words | Whether `testing`, `experimental`, `do not use`, `mock only` appear |
| Additional repos | Whether it depends on extra third-party repos |
| Repo priority | Whether it sets high priority, may affect system packages |
| module_hotfixes | Whether it enables settings that may override module packages |

Recommended risk levels:

| Level | Meaning |
|-------|---------|
| low | Supports current system, build succeeded, clear description |
| medium | Less description, older build, or average source |
| high | Doesn't support current chroot, build failed, experimental description, depends on extra repos |
| blocked | Explicitly says `do not use`, `mock only`, default not allowed to install |

### 21.6 Need to Distinguish Source Package Name and Binary Package Name

Packages in Copr projects are usually source package dimensions, but user inputs binary RPM package names to install.

For example:

- Source package name might be `ghostty`.
- Binary packages might include `ghostty`, `ghostty-terminfo`, `ghostty-shell-integration`.

Also possible:

- Source package name and binary package name differ.
- User inputs command name instead of package name.
- Copr project name matches, but actually doesn't provide target binary package.

Improvement suggestions:

1. During search phase, try to use built package / NEVRA search to confirm binary package name.
2. After enabling Copr, use `dnf5 repoquery` before installation to verify target package actually comes from selected Copr.
3. Support `copa provides <command-or-path>`, similar to `dnf5 provides`.
4. Clearly show source package name and binary package name in results display.

### 21.7 makecache Should Not Unconditionally Refresh All Repos

`sudo dnf5 makecache --refresh` will refresh all enabled repos, which may take long time.

Improvement suggestions:

- After enabling Copr, identify newly added repo id.
- If DNF5 supports, should only refresh newly added Copr repo.
- If not supported, then fallback to global `makecache --refresh`.
- Show expected repos to refresh in `--dry-run`.

### 21.8 Need to Design Non-interactive Mode

`copa` is interactive tool by default, but scripts and automation scenarios need non-interactive mode.

Suggested support:

```text
copa -y install --copr owner/project package
copa --assumeno install package
copa --json search package
copa --dry-run install package
```

Non-interactive mode rules:

1. `-y` should not auto-select first item in Copr search results.
2. If not specified `--copr owner/project`, `-y install <package>` should fail with prompt when Copr selection needed.
3. `--json` outputs machine-readable results for script processing.
4. `--dry-run` only shows commands to execute, doesn't modify system.

### 21.9 Need to Clarify Permissions and sudo Strategy

`copa search`, `copa info`, `copa list --packages` don't need root, but need `copr-cli` installed locally.

The following operations need root:

- Enable Copr.
- Delete Copr repo.
- Execute `makecache`.
- Install or remove packages.

Improvement suggestions:

- Only call `sudo` when actually needing to modify system.
- Don't require root at program startup.
- Avoid shell command concatenation, prefer parameter array subprocess calls.
- Show privileged commands about to run before execution.

### 21.10 Need to Handle Fedora Atomic / Silverblue Scenarios

Fedora Silverblue, Kinoite, Sericea and other Atomic desktops shouldn't directly use `dnf5 install` to modify system by default.

Improvement suggestions:

- Detect whether it's rpm-ostree system at startup.
- If rpm-ostree system, inform user `copa` currently doesn't support or switch to future rpm-ostree backend.
- Can consider supporting later:

```text
rpm-ostree install <package>
```

But Copr repo enable, persistence, and rollback strategies need separate design.

### 21.11 Need to Design Configuration File

Some behaviors shouldn't be hardcoded, recommend providing user configuration file.

Suggested config path:

```text
~/.config/copa/config.toml
```

Configurable items:

```toml
[search]
enable_fedora = true
enable_rpmfusion = true
enable_terra_if_present = true
enable_copr = true
terra_repo_patterns = ["terra*"]

[install]
default_copr_post_action = "disable"
default_chroot_auto_detect = true
strict_selected_repo = true
single_package_only = true

[backend]
prefer_dnf5 = true
fallback_to_dnf = true
require_copr_cli = true

[ui]
language = "auto"
json = false

[risk]
block_mock_only = true
block_do_not_use = true
warn_experimental = true
```

### 21.12 Need to Add Audit Capability

`copa audit` should be implemented as an important feature, not just an add-on command.

Suggested checks:

1. Currently enabled Copr list.
2. Which Copr don't support current Fedora version.
3. Which Copr recently failed builds or haven't been updated for long time.
4. Which Copr descriptions contain risk words.
5. Which Copr set high repo priority.
6. Which Copr installed packages but current repo has been deleted.
7. Which Copr repo files appear to be residual.

### 21.13 Need to Improve Test Plan

Should at least include:

| Test Type | Content |
|-----------|---------|
| Unit tests | Repo classification, chroot detection, risk scoring, API parsing |
| Command tests | Mock `dnf5`, `copr-cli` output, test command construction |
| Integration tests | Test search and install flow in Fedora container/toolbox |
| Failure tests | Network failure, API timeout, makecache failure, install failure |
| Rollback tests | Whether cleans up newly enabled Copr after installation failure |
| Non-interactive tests | `--dry-run`, `--json`, `--assumeyes` behavior |

### 21.14 Need to Clarify MVP Scope

Recommend MVP not to implement all capabilities at once.

MVP should only include:

1. `copa search <keyword>`
2. `copa install <package>`
3. Single package installation
4. Fedora / RPM Fusion / Terra enabled repo search
5. Copr API search repo names
6. `copr-cli` secondary verification of candidate Copr
7. User manual selection of Copr
8. `dnf5 copr enable`
9. `dnf5 makecache --refresh`
10. `dnf5 install`
11. Default disable Copr after installation, user can choose to keep or delete
12. `--dry-run`
13. JSON state file

Deferred implementation:

- JSON output
- Complete scoring system
- `copa audit`
- rpm-ostree backend, only detect and prompt
- Auto-identify command name provides
- Multi-package installation
- Complex transaction analysis

## 22. Implementation Priority Recommendations

Recommended implementation in phases.

### Phase 1: MVP

Goal: Implement complete usable single-package interactive installation flow.

Includes:

- DNF5 command detection.
- Fedora / RPM Fusion / Terra search.
- Copr API search.
- Copr candidate list display.
- User selection of Copr.
- Enable Copr.
- makecache.
- install.
- Default disable Copr after installation, ask user whether to keep, disable, or delete.
- `--dry-run`.
- JSON state file.
- `copr-cli` hard dependency detection.

### Phase 2: Security Enhancement

Includes:

- Risk scoring.
- Risk word identification.
- Current chroot support check.
- Auto-rollback on installation failure.
- Existing Copr detection.
- Repo source limitation.

### Phase 3: Query Enhancement

Includes:

- `copa info`
- `copa repoquery`
- `copa list --packages`
- `copa provides`
- `--json`
- Local cache.

### Phase 4: Maintenance and Audit

Includes:

- `copa audit`
- State database.
- Installed Copr package tracking.
- Residual repo detection.
- Long-term no-update Copr warning.

### Phase 5: Release and Packaging

Includes:

- RPM spec.
- Copr bootstrap repo.
- man page.
- shell completion.
- README.
- Example config file.

## 23. Key Decisions of Current Plan

The following issues have been confirmed:

1. `copa install` asks user whether to continue searching at each step when searching Fedora official, RPM Fusion, Terra; pressing Enter directly defaults to installing from current source.
2. Default post-install Copr strategy is `disable`, i.e., disable repo but keep repo file.
3. `-y` not allowed to auto-accept Copr search results; when Copr selection needed, must explicitly specify `--copr owner/project` or enter interactive selection.
4. Default strictly limit target package source, avoid DNF installing target package from non-user-selected repo.
5. Terra repo id made configurable pattern.
6. `dnf5` has been soft-linked to `dnf` on system, still prioritize parsing by `dnf5` semantics; prioritize using `dnf5` when executing commands, fallback to `dnf` if necessary.
7. Temporarily not support Fedora Atomic / rpm-ostree systems; only detect and prompt.
8. MVP uses JSON to save state first.
9. `copr-cli` as hard dependency.
10. MVP supports single package installation first, not supporting installing multiple packages at once.

## 24. Current Implementation Status (2025-05-14)

### Completed Features

| Feature | Command/Option | Status |
|---------|---------------|--------|
| Environment check | `copa doctor` | ✅ |
| Multi-keyword search | `copa search ghostty terminal` | ✅ |
| Regex search | `copa search -x "^ghost"` | ✅ |
| Install flow | `copa install <pkg>` | ✅ |
| Package info query | `copa info <pkg>` | ✅ |
| Package list | `copa list --packages owner/project` | ✅ |
| Repo management | `copa repo list/enable/disable/remove` | ✅ |
| Repo audit | `copa audit` | ✅ |
| Copr search | Copr API integration | ✅ |
| OBS search | OBS REST API integration | ✅ |
| Version fallback | OBS package version mismatch warning | ✅ |
| Risk assessment | Risk word identification + chroot check | ✅ |
| Post-install strategy | Disable/keep/remove repo | ✅ |
| Dry-run mode | `--dry-run` | ✅ |
| State file | `~/.local/share/copa/state.json` | ✅ |
| RPM spec | `rpm/copa.spec` | ✅ |
| JSON output | `--json` global option | ✅ |
| repoquery | `copa repoquery --requires/--provides/--files` | ✅ |
| provides | `copa provides <file>` | ✅ |
| Config file | `~/.config/copa/config.toml` loaded | ✅ |
| Shell completion | `completions/copa.bash` + `completions/_copa` | ✅ |
| Man page | `man/copa.1` | ✅ |
| Ctrl+C handling | Signal handler | ✅ |
| Tests | 47 unit tests | ✅ |

### Incomplete Features

| Feature | Priority | Description |
|---------|----------|-------------|
| Sort functionality | Low | Sort by votes/popularity |
| Multi-package install | Low | Install multiple packages at once |

### Search Matching Logic

Inspired by paru implementation, using the following matching rules:

- **Matching method**: Substring containment (`contains`)
- **Regex mode**: `-x` flag, match package names only
- **Multiple keywords**: AND logic (all words must match simultaneously)
- **Search fields**: Package name, project name, Owner, description
- **Filtering**: Client-side secondary filtering for accuracy
