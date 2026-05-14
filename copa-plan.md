# copa：DNF5 风格的 Fedora Copr 软件包助手实施方案

## 1. 项目定位

`copa` 是一个面向 Fedora / DNF5 生态的 Copr 软件包助手。

目标是提供类似 Arch 下 `paru` / `yay` 的搜索与安装体验，但命令格式尽量保持 DNF 风格，而不是 Pacman 风格。

一句话描述：

> `copa` 是一个 DNF5 风格的 Fedora Copr 包助手，支持搜索 Fedora 官方源、RPM Fusion、Terra 与 Copr 仓库，辅助用户选择 Copr 仓库并通过 `dnf5` 安装软件。

名称含义：

> `copa` = Copr Package Assistant

## 2. 背景与限制

当前 Fedora DNF5 环境下需要注意：

1. DNF5 的 Copr 插件目前没有 `search` 子命令。
2. 因此不能依赖 `dnf5 copr search <keyword>` 或 `dnf copr search <keyword>`。
3. Copr 的搜索能力应通过 Copr HTTP API / Web 搜索接口实现。
4. `copr-cli` 作为硬依赖，用于查询 Copr 项目内的包列表、包详情、构建信息。
5. 本地仓库管理仍通过 `dnf5 copr enable/list/disable/remove` 完成。
6. 最终软件安装通过 `dnf5 install` 完成。

也就是说，推荐架构是：

| 模块 | 实现方式 | 用途 |
|---|---|---|
| 官方源搜索 | `dnf5 search` / `dnf5 repoquery` | 搜索 Fedora 官方源与已启用仓库 |
| RPM Fusion 搜索 | `dnf5 repoquery` 限定 RPM Fusion repo | 搜索 RPM Fusion |
| Terra 搜索 | 检测 Terra 是否已启用后查询 | 搜索已启用的 Terra 仓库 |
| Copr 全局搜索 | Copr HTTP API / Web endpoint | 替代缺失的 `dnf5 copr search` |
| Copr 项目查询 | `copr-cli`，必要时配合 API | 查询项目包列表、包详情、构建状态 |
| Copr 仓库管理 | `dnf5 copr enable/list/disable/remove` | 启用、禁用、删除本地 Copr repo |
| 安装软件 | `dnf5 install` | 通过 DNF5 安装软件包 |
| 刷新缓存 | `dnf5 makecache --refresh` | 启用 Copr 后刷新元数据 |

## 3. 命令风格

命令名使用：

```text
copa
```

命令格式尽量兼容 DNF：

```text
copa [全局选项] <command> [command options] [arguments]
```

不主推 Pacman/Paru 风格的 `-S`、`-Ss`、`-Q` 等参数。

推荐主命令：

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
copa copr list
copa copr enable <owner/project> [chroot]
copa copr disable <owner/project>
copa copr remove <owner/project>
```

## 4. 搜索优先级

`copa install <package>` 的默认搜索顺序为：

1. Fedora 官方仓库
2. RPM Fusion
3. 第三方仓库 Terra，前提是用户已经添加并启用了 Terra repo
4. Copr
5. openSUSE Build Service (OBS)

Terra 是可选项：

- 如果用户已添加 Terra repo，则参与搜索。
- 如果用户未添加 Terra repo，则跳过。
- `copa` 默认不主动为用户添加 Terra repo。

OBS 作为补充来源：

- OBS 提供跨发行版的软件包构建服务，包含许多 Fedora 未收录的软件。
- OBS 搜索结果需要用户手动添加 repo 文件，不自动启用。
- OBS 包的版本可能与当前 Fedora 版本不完全匹配，需要版本 fallback 机制。

## 5. `copa install` 默认流程

以安装 `ghostty` 为例：

```text
copa install ghostty
```

完整流程：

1. 检测当前已启用仓库。
2. 搜索 Fedora 官方仓库。
3. 如果 Fedora 官方仓库没有结果，则搜索 RPM Fusion。
4. 如果 Terra 已启用，则搜索 Terra。
5. 如果前面都没有合适结果，或者用户选择继续搜索 Copr，则搜索 Copr 仓库。
6. 搜索 Copr 时，应先查询 Copr 仓库名并展示候选列表。
7. 询问用户要添加哪个 Copr 仓库。
8. 根据用户选择启用指定 Copr 仓库。
9. 执行 `dnf5 makecache --refresh`。
10. 执行 `dnf5 install <package>`。
11. 安装完成后询问用户是否保留此 Copr。
12. 如果用户不保留，则删除/移除对应 Copr repo。
13. 如果 Copr 也没有合适结果，或者用户选择继续搜索 OBS，则搜索 OBS 仓库。
14. 搜索 OBS 时，展示匹配的项目和包信息。
15. 提供 OBS repo 文件下载链接，由用户手动添加。
16. 如果 OBS 包版本与当前 Fedora 版本不匹配，提示用户风险并提供 fallback 版本。

## 6. 检测已启用仓库

运行时先检测当前系统已启用仓库：

```bash
dnf5 repolist --enabled
```

分类逻辑建议：

| 类型 | 判断方式 |
|---|---|
| Fedora 官方源 | repo id 包含 `fedora`、`updates`、`updates-testing` 等 |
| RPM Fusion | repo id 包含 `rpmfusion-free`、`rpmfusion-nonfree` |
| Terra | repo id 包含 `terra` |
| Copr | repo id 包含 `copr:` 或 `_copr:` |
| OBS | repo id 包含 `obs:` 或 `opensuse:` 或文件来自 `download.opensuse.org` |

## 7. Fedora 官方仓库搜索

优先搜索 Fedora 官方仓库：

```bash
dnf5 repoquery --repoid=fedora --repoid=updates <package>
```

如果系统启用了 `updates-testing`，可根据用户选项决定是否包含。

如果找到包，提示用户是否继续搜索下一个来源。默认行为是直接从当前来源安装，即用户按回车开始安装：

```text
Found in Fedora repositories:

<package>.x86_64  <version>  fedora/updates

Press Enter to install from Fedora, or type 's' to continue searching [Install/search]:
```

行为规则：

- 直接按回车：从 Fedora 官方仓库安装。
- 输入 `s` / `search`：继续搜索 RPM Fusion。
- 输入 `q` / `quit`：退出。

如果用户确认安装，执行：

```bash
sudo dnf5 install <package>
```

此时不进入后续 RPM Fusion / Terra / Copr 流程。

## 8. RPM Fusion 搜索

如果 Fedora 官方仓库没找到，搜索 RPM Fusion：

```bash
dnf5 repoquery \
  --repoid=rpmfusion-free \
  --repoid=rpmfusion-free-updates \
  --repoid=rpmfusion-nonfree \
  --repoid=rpmfusion-nonfree-updates \
  <package>
```

如果系统没有启用 RPM Fusion，则跳过，不主动添加。

找到后提示用户是否继续搜索。默认行为是直接从 RPM Fusion 安装，即用户按回车开始安装：

```text
Found in RPM Fusion:

<package>.x86_64  <version>  <rpmfusion-repo>

Press Enter to install from RPM Fusion, or type 's' to continue searching [Install/search]:
```

行为规则：

- 直接按回车：从 RPM Fusion 安装。
- 输入 `s` / `search`：继续搜索 Terra，若 Terra 未启用则继续 Copr。
- 输入 `q` / `quit`：退出。

## 9. Terra 搜索

如果检测到 Terra repo 已启用，则搜索 Terra：

```bash
dnf5 repoquery --repoid='terra*' <package>
```

实际实现中建议从 `dnf5 repolist --enabled` 的结果中找出所有包含 `terra` 的 repo id，然后逐个加入查询。

如果找到，提示用户是否继续搜索。默认行为是直接从 Terra 安装，即用户按回车开始安装：

```text
Found in Terra repositories:

<package>.x86_64  <version>  terra

Press Enter to install from Terra, or type 's' to continue searching Copr [Install/search]:
```

行为规则：

- 直接按回车：从 Terra 安装。
- 输入 `s` / `search`：继续搜索 Copr。
- 输入 `q` / `quit`：退出。

如果用户没有启用 Terra，则直接跳过 Terra，不提示添加。

## 10. Copr 搜索流程

如果 Fedora / RPM Fusion / Terra 都没有合适结果，或者用户主动使用 `--copr-only`，进入 Copr 搜索。

Copr 搜索必须先展示仓库候选列表，不允许自动启用第一个结果。

搜索来源建议：

1. Copr API 项目搜索。
2. Copr API 包名属性搜索。
3. Copr built package / NEVRA 搜索。
4. 使用 `copr-cli` 对候选项目做二次验证。

候选列表展示重点：

- Copr 仓库名，即 `owner/project`
- 描述
- 是否支持当前 Fedora chroot
- 最近构建状态
- 是否提供目标包
- 风险提示

示例：

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

用户必须明确选择仓库后才继续。

## 11. Copr API 与 `copr-cli` 的职责划分

`copr-cli` 是 `copa` 的硬依赖。Copr API 主要用于补足全局搜索能力，`copr-cli` 主要用于对已知项目进行可靠查询。

### Copr API

用于补足 DNF5 没有 Copr 搜索命令的问题。

推荐使用：

- 项目搜索：`/api_3/project/search?query=<keyword>`
- 项目详情：`/api_3/project/?ownername=<owner>&projectname=<project>`
- 包列表：`/api_3/package/list?ownername=<owner>&projectname=<project>`
- 包详情：`/api_3/package/?ownername=<owner>&projectname=<project>&packagename=<package>`
- 构建列表：`/api_3/build/list?ownername=<owner>&projectname=<project>&packagename=<package>`

### `copr-cli`

优先用于已知项目的查询：

```bash
copr-cli list <owner>
copr-cli list-packages <owner/project>
copr-cli list-package-names <owner/project>
copr-cli get-package <owner/project> <package>
copr-cli monitor <owner/project>
```

### `dnf5 copr`

只负责本地 Copr repo 管理：

```bash
dnf5 copr list
sudo dnf5 copr enable <owner/project> [chroot]
sudo dnf5 copr disable <owner/project>
sudo dnf5 copr remove <owner/project>
```

## 11.5 OBS 搜索流程

如果 Fedora / RPM Fusion / Terra / Copr 都没有合适结果，或者用户主动使用 `--obs-only`，进入 OBS 搜索。

### OBS 简介

openSUSE Build Service (OBS) 是一个跨发行版的软件包构建服务，提供多种 Linux 发行版的软件包，包括 Fedora。

- **API Base URL**: `https://api.opensuse.org`
- **CLI 工具**: `osc`（Python 编写，可通过 pip 或 dnf 安装）
- **匿名访问**: 只读操作不需要认证

### OBS 搜索实现

使用 OBS REST API 搜索包：

```bash
# 搜索项目
curl -H "Accept: application/xml; charset=utf-8" \
  "https://api.opensuse.org/search/project?match=contains(@name,'ghostty')"

# 搜索包
curl -H "Accept: application/xml; charset=utf-8" \
  "https://api.opensuse.org/search/package?match=@name='ghostty'"

# 查询 Fedora 版本的二进制包
curl -H "Accept: application/xml; charset=utf-8" \
  "https://api.opensuse.org/search/released/binary?match=name='ghostty'+and+repository='Fedora_43'"
```

### 候选列表展示

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

### 版本匹配与 Fallback 策略

**核心原则**: 优先使用与当前 Fedora 版本匹配的包，如果没有则 fallback 到上一个版本，并明确提示风险。

版本匹配逻辑：

1. 查询当前 Fedora 版本（如 `fedora-43`）的包
2. 如果没有，查询上一个版本（如 `fedora-42`）的包
3. 如果找到 fallback 版本，**必须**向用户提示风险

风险提示示例：

```text
⚠️  WARNING: Version mismatch detected!

Package: ghostty
Available for: Fedora 42 x86_64
Your system: Fedora 43 x86_64

This package was built for an older Fedora version. It may:
- Have unmet dependencies
- Not work correctly with your system libraries
- Cause system instability

Do you want to proceed anyway? [y/N]:
```

Fallback 版本限制：

- 最多 fallback 2 个版本（如 Fedora 43 → 42 → 41）
- 超过 2 个版本差距的包不推荐使用
- Rawhide 不参与 fallback，必须精确匹配

### OBS Repo 添加方式

OBS 仓库由 `copa` 自动下载并添加到 `/etc/yum.repos.d/`，然后询问用户是否安装：

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

实现流程：

```bash
# 1. 自动下载 repo 文件（不需要用户确认）
sudo curl -o /etc/yum.repos.d/obs_<project>.repo \
  "https://download.opensuse.org/repositories/<project>/Fedora_43/<project>.repo"

# 2. 询问用户是否继续（默认回车 = 安装）
# 用户按回车后执行：

# 3. 刷新缓存
sudo dnf5 makecache --refresh

# 4. 安装包
sudo dnf5 install <package>

# 5. 询问是否保留 OBS 仓库（默认禁用）
```

行为规则：

- 下载 repo 文件是自动的，不需要用户确认
- 下载完成后，展示将执行的命令并询问用户
- 直接按回车：开始安装
- 输入 `q` / `quit`：取消操作（repo 文件已下载，用户可手动清理或保留）
- 安装完成后，询问是否保留 OBS 仓库，默认禁用

### OBS 安装后保留策略

与 Copr 类似，安装完成后询问用户是否保留 OBS 仓库：

```text
Package installed successfully.

Keep OBS repository home:user1 enabled for future updates?

[1] Keep enabled
[2] Disable repo [default]
[3] Remove repo file
Select [1/2/3]:
```

默认策略：禁用 OBS 仓库（与 Copr 一致）

- 保持启用：OBS 仓库继续参与系统更新
- 禁用仓库：保留 repo 文件但禁用
- 删除 repo 文件：完全移除 OBS 仓库

### OBS 仓库文件命名

为避免冲突，OBS repo 文件命名为：

```text
/etc/yum.repos.d/obs_<project_name>.repo
```

其中 `<project_name>` 中的 `:` 替换为 `_`，例如：

- `home:user1` → `obs_home_user1.repo`
- `science` → `obs_science.repo`

### OBS 与 Copr 的区别

| 特性 | Copr | OBS |
|------|------|-----|
| 仓库管理 | `dnf5 copr enable/disable` | 下载 repo 文件 + `dnf config-manager` |
| 搜索 | Copr API | OBS API |
| 版本匹配 | chroot 机制 | repository 名称匹配 |
| 自动化程度 | 高（可自动启用） | 中（自动下载 repo） |
| 安装后处理 | `dnf5 copr disable` | `dnf config-manager --set-disabled` |
| 风险提示 | 风险评分 | 版本 mismatch 警告 |

## 12. 启用用户选择的 Copr

用户选择 Copr 后，例如：

```text
rivenirvana/ghostty
```

执行：

```bash
sudo dnf5 copr enable rivenirvana/ghostty fedora-43-x86_64
```

建议 `copa` 自己检测当前 chroot，并显式传入，而不是完全依赖 `dnf5 copr enable` 自动检测。

chroot 格式：

```text
fedora-<releasever>-<arch>
```

示例：

```text
fedora-43-x86_64
```

Rawhide 示例：

```text
fedora-rawhide-x86_64
```

## 13. makecache 与 install

启用 Copr 后，必须刷新缓存再安装。

注意：不要使用单个 `&`：

```bash
# 不推荐
dnf makecache & dnf install <package>
```

单个 `&` 会让前一个命令后台运行，可能导致安装时缓存尚未完成。

推荐顺序执行：

```bash
sudo dnf5 makecache --refresh
sudo dnf5 install <package>
```

或使用 `&&`：

```bash
sudo dnf5 makecache --refresh && sudo dnf5 install <package>
```

## 14. 安装完成后的 Copr 保留策略

安装完成后必须询问用户是否保留刚启用的 Copr 仓库。

推荐交互：

```text
Package installed successfully.

Keep Copr repository rivenirvana/ghostty enabled for future updates?

[1] Keep enabled
[2] Disable repo
[3] Remove repo file
Select [1/2/3]:
```

三个选项含义：

| 选项 | 行为 |
|---|---|
| Keep enabled | 保持 Copr 启用，未来可继续接收更新 |
| Disable repo | 禁用 Copr，但保留 repo 文件 |
| Remove repo file | 移除 Copr repo 文件 |

默认策略确定为：

```text
Default: disable repo after installation
```

原因：

- 比保持启用更安全，避免 Copr 后续参与系统升级。
- 比直接删除 repo 文件更温和，用户后续可以重新启用。
- 如果用户明确选择删除，再执行 remove repo/file。

安装完成后仍应询问用户，但直接按回车时使用默认行为：禁用 Copr。

## 15. 如果用户不保留 Copr

如果用户选择默认行为，应禁用 Copr：

```bash
sudo dnf5 copr disable <owner/project>
```

如果用户明确选择删除 repo 文件，则优先执行：

```bash
sudo dnf5 copr remove <owner/project>
```

这比直接删除文件更稳妥。

如果 `dnf5 copr remove` 失败，再 fallback 到删除 repo 文件。

Copr repo 文件通常位于：

```text
/etc/yum.repos.d/
```

文件名通常类似：

```text
_copr:copr.fedorainfracloud.org:rivenirvana:ghostty.repo
```

但实际实现中不要硬编码文件名，应扫描 `/etc/yum.repos.d/`，匹配：

- `copr.fedorainfracloud.org`
- owner
- project

然后删除对应文件。

## 16. 推荐命令选项

`install` 命令建议支持：

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

选项含义：

| 选项 | 行为 |
|---|---|
| 无参数 | 按 Fedora → RPM Fusion → Terra → Copr → OBS 顺序搜索 |
| `--official-only` | 只搜索 Fedora 官方源 |
| `--rpmfusion-only` | 只搜索 RPM Fusion |
| `--terra-only` | 只搜索 Terra，前提是 Terra 已启用 |
| `--copr-only` | 只搜索 Copr |
| `--copr owner/project` | 不搜索 Copr，直接使用指定 Copr |
| `--obs-only` | 只搜索 OBS |
| `--keep-copr` | 安装后保留 Copr |
| `--remove-copr-after-install` | 安装后删除 Copr repo |
| `--disable-copr-after-install` | 安装后禁用 Copr，但保留 repo 文件，默认行为 |
| `--no-terra` | 即使 Terra 已启用，也跳过 Terra |
| `--no-obs` | 跳过 OBS 搜索 |
| `--allow-obs-fallback` | 允许 OBS 版本 fallback（默认需要确认） |

## 17. 全局选项建议

尽量兼容 DNF 风格：

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

选项含义：

| 选项 | 含义 |
|---|---|
| `-y` / `--assumeyes` | 自动确认 |
| `--assumeno` | 默认否，只预览 |
| `--refresh` | 刷新 DNF/Copr 元数据 |
| `--releasever` | 指定 Fedora 版本 |
| `--arch` | 指定架构 |
| `--chroot` | 指定 Copr chroot |
| `--dry-run` | 只展示将执行的操作 |
| `-v` / `--verbose` | 显示详细信息 |

## 18. 推荐交互示例

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

## 19. 安全原则

`copa` 的核心安全原则：

1. 不自动启用第一个 Copr 搜索结果。
2. 必须先展示 Copr 仓库列表。
3. 必须由用户明确选择要启用的 Copr 仓库。
4. 启用 Copr 后必须刷新缓存再安装。
5. 安装完成后必须询问是否保留 Copr。
6. 如果用户不保留，应通过 `dnf5 copr remove` 或删除 repo 文件清理。
7. Terra 只在用户已启用时参与搜索，不主动添加。
8. Fedora 官方仓库优先级最高。
9. RPM Fusion 仅在已启用时参与搜索，不主动添加。
10. Copr 属于第三方社区仓库，必须提示用户风险。
11. OBS 仓库需要用户手动添加，不自动启用。
12. OBS 包版本与当前 Fedora 版本不匹配时，必须明确提示风险。
13. OBS 版本 fallback 最多支持 2 个版本差距。

## 20. 最终确定版流程摘要

`copa install <package>` 的最终行为：

```text
1. Search Fedora official repositories.
2. Search RPM Fusion repositories if enabled.
3. Search Terra repositories if enabled.
4. Search Copr repositories.
5. Show matching Copr repository names.
6. Ask the user which Copr repository to enable.
7. Enable the selected Copr repository.
8. Run dnf5 makecache --refresh.
9. Run dnf5 install <package>.
10. Ask whether to keep the Copr repository.
11. By default, disable the Copr repository after installation; if the user explicitly chooses removal, remove the Copr repo file or run dnf5 copr remove.
12. If no Copr results or user chooses to continue, search OBS repositories.
13. Show matching OBS packages with version compatibility info.
14. If OBS package version doesn't match current Fedora, warn user about fallback risk.
15. Provide OBS repo download URL for manual addition.
16. Copy install commands to clipboard if requested.
```

## 21. 仍需改进的问题

当前方案已经明确了 `copa` 的核心交互流程和关键决策，但在真正实现前，还需要补充以下设计细节。

### 21.1 DNF5 参数兼容性需要实测

文档中的 `dnf5 repoquery --repoid=...`、`dnf5 makecache --refresh` 等命令属于设计示例，实际实现时需要针对目标 Fedora 版本逐项验证。

需要确认：

1. DNF5 当前版本中限定 repo 的参数到底使用 `--repoid`、`--repo`、`--enablerepo`，还是其他形式。
2. `dnf5 repoquery` 是否支持一次传入多个 repo 过滤参数。
3. `dnf5 makecache` 是否可以只刷新新启用的 Copr repo。
4. `dnf5 copr enable` 在不同 Fedora 版本、Rawhide、非 x86_64 架构上的 chroot 自动检测行为。
5. `dnf5 copr remove` 是否总能正确删除对应 `/etc/yum.repos.d/` 文件。

改进建议：

- 在代码中封装一个 `DnfBackend`，不要在业务逻辑中散落硬编码命令。
- 启动时检测 `dnf5` 能力，必要时 fallback 到 `dnf`。
- 增加 `copa doctor` 命令，用于检查 `dnf5`、`dnf5-command(copr)`、`copr-cli`、网络、repo 状态。

### 21.2 需要实现安装时的 repo 来源限定

当前流程按 Fedora → RPM Fusion → Terra → Copr 的顺序搜索，但如果执行普通的：

```bash
sudo dnf5 install <package>
```

DNF 解析器仍可能从其他已启用仓库中选择版本更高的包，而不是用户刚刚确认的来源。

例如：

- 用户选择从 Fedora 官方源安装，但 Terra 里有更高版本。
- 用户选择从 Copr 安装，但另一个已启用 Copr 中有同名包。
- 用户选择 RPM Fusion，但其他第三方仓库提供了更高 EVR 的包。

改进建议：

1. 当用户选择某个来源后，安装时应尽量限定来源。
2. 对 Fedora / RPM Fusion / Terra，可在安装前显示将使用的 repo id。
3. 对 Copr，启用后应识别新 repo id，并在安装时尽量限定到该 repo。
4. 如果由于依赖解析必须使用其他 repo，应在安装前展示给用户确认。

已确认策略：

> 默认严格限定目标包来源，尊重用户选择的来源；允许 DNF 从基础系统仓库解析依赖，但如果目标包本身来自非用户选择仓库，应中止并提示。

### 21.3 Copr 仓库是否原本已存在需要记录

安装后询问是否保留 Copr 时，需要区分两种情况：

1. 这个 Copr 是 `copa` 本次新启用的。
2. 这个 Copr 在运行 `copa` 之前就已经存在。

如果用户原本已经启用了该 Copr，`copa` 不应该在安装后默认删除它。

改进建议：

- 启用 Copr 前记录当前已启用 Copr 列表。
- 新启用的 Copr 才进入安装后清理流程。
- 对已存在的 Copr，只询问是否保持现状，不默认删除。
- 在本地状态文件中记录 `enabled_by_copa`、启用时间、安装的包名、repo id。

建议状态文件位置：

```text
~/.local/share/copa/state.json
```

建议缓存位置：

```text
~/.cache/copa/
```

### 21.4 需要处理启用 Copr 后安装失败的回滚

如果流程执行到一半失败，例如：

1. Copr 启用成功。
2. `makecache` 失败。
3. `dnf5 install` 失败。
4. 用户按下 Ctrl+C 中断。

此时系统可能会遗留一个刚启用但未使用的 Copr repo。

改进建议：

- 使用事务式流程记录每一步状态。
- 如果 Copr 是本次新启用的，且安装失败，应询问是否立即移除。
- 在 `--assumeyes` 模式下，建议默认回滚新启用但未成功安装的 Copr。
- 捕获中断信号，尽量执行清理逻辑。

### 21.5 Copr 搜索结果需要评分与风险提示

仅展示 Copr 仓库名还不够，需要帮助用户判断哪个仓库更可信。

建议评分维度：

| 维度 | 说明 |
|---|---|
| 包名匹配 | 是否精确提供用户输入的包名 |
| 当前 chroot 支持 | 是否支持当前 Fedora 版本和架构 |
| 最近构建状态 | 最近构建是否成功 |
| 构建新鲜度 | 最近成功构建距离当前时间多久 |
| 项目描述质量 | 是否有清晰描述、主页、联系方式 |
| 风险词 | 是否出现 `testing`、`experimental`、`do not use`、`mock only` |
| additional repos | 是否依赖额外第三方仓库 |
| repo priority | 是否设置了较高优先级，可能影响系统包 |
| module_hotfixes | 是否启用了可能覆盖模块包的设置 |

推荐风险等级：

| 等级 | 含义 |
|---|---|
| low | 支持当前系统，构建成功，描述清晰 |
| medium | 描述较少、构建较旧或来源一般 |
| high | 不支持当前 chroot、构建失败、实验性描述、依赖额外 repo |
| blocked | 明确写有 `do not use`、`mock only`，默认不允许安装 |

### 21.6 需要区分源码包名与二进制包名

Copr 项目里的 package 通常是源码包维度，但用户输入的是要安装的二进制 RPM 包名。

例如：

- 源码包名可能是 `ghostty`。
- 二进制包可能包括 `ghostty`、`ghostty-terminfo`、`ghostty-shell-integration`。

也可能出现：

- 源码包名和二进制包名不同。
- 用户输入的是命令名而不是包名。
- Copr 项目名匹配，但实际并不提供目标二进制包。

改进建议：

1. 搜索阶段尽量使用 built package / NEVRA 搜索确认二进制包名。
2. 启用 Copr 后，在安装前使用 `dnf5 repoquery` 验证目标包确实来自所选 Copr。
3. 支持 `copa provides <command-or-path>`，类似 `dnf5 provides`。
4. 结果展示中明确显示源码包名与二进制包名。

### 21.7 makecache 不应无条件刷新所有仓库

`sudo dnf5 makecache --refresh` 会刷新全部已启用 repo，可能耗时较长。

改进建议：

- 启用 Copr 后识别新增 repo id。
- 如果 DNF5 支持，应只刷新新增 Copr repo。
- 如果不支持，才 fallback 到全局 `makecache --refresh`。
- 在 `--dry-run` 中显示预计刷新的 repo。

### 21.8 需要设计非交互模式

`copa` 默认是交互式工具，但脚本和自动化场景需要非交互模式。

建议支持：

```text
copa -y install --copr owner/project package
copa --assumeno install package
copa --json search package
copa --dry-run install package
```

非交互模式规则：

1. `-y` 不应自动选择 Copr 搜索结果中的第一项。
2. 如果没有通过 `--copr owner/project` 指定仓库，`-y install <package>` 在需要 Copr 选择时应失败并提示。
3. `--json` 输出机器可读结果，方便脚本处理。
4. `--dry-run` 只展示将执行的命令，不修改系统。

### 21.9 需要明确权限与 sudo 策略

`copa search`、`copa info`、`copa list --packages` 不需要 root，但需要本机已安装 `copr-cli`。

以下操作需要 root：

- 启用 Copr。
- 删除 Copr repo。
- 执行 `makecache`。
- 安装或移除软件包。

改进建议：

- 只有在确实需要修改系统时才调用 `sudo`。
- 不要整个程序一开始就要求 root。
- 避免使用 shell 拼接命令，优先使用参数数组调用子进程。
- 在执行前展示即将运行的特权命令。

### 21.10 需要处理 Fedora Atomic / Silverblue 场景

Fedora Silverblue、Kinoite、Sericea 等 Atomic 桌面默认不应直接使用 `dnf5 install` 修改系统。

改进建议：

- 启动时检测是否为 rpm-ostree 系统。
- 如果是 rpm-ostree 系统，提示用户 `copa` 当前不支持或切换到未来的 rpm-ostree backend。
- 后续可考虑支持：

```text
rpm-ostree install <package>
```

但 Copr repo 的启用、持久化和回滚策略需要单独设计。

### 21.11 需要设计配置文件

一些行为不应硬编码，建议提供用户配置文件。

建议配置路径：

```text
~/.config/copa/config.toml
```

可配置项：

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

### 21.12 需要增加审计能力

`copa audit` 应作为重要功能实现，而不仅是附加命令。

建议检查：

1. 当前启用的 Copr 列表。
2. 哪些 Copr 不支持当前 Fedora 版本。
3. 哪些 Copr 最近构建失败或长期无更新。
4. 哪些 Copr 描述中包含风险词。
5. 哪些 Copr 设置了较高 repo priority。
6. 哪些 Copr 安装过包，但当前 repo 已被删除。
7. 哪些 Copr repo 文件疑似残留。

### 21.13 需要完善测试计划

建议至少包含：

| 测试类型 | 内容 |
|---|---|
| 单元测试 | repo 分类、chroot 检测、风险评分、API 解析 |
| 命令测试 | mock `dnf5`、`copr-cli` 输出，测试命令构造 |
| 集成测试 | 在 Fedora container/toolbox 中测试搜索和安装流程 |
| 失败测试 | 网络失败、API 超时、makecache 失败、install 失败 |
| 回滚测试 | 安装失败后是否清理新启用 Copr |
| 非交互测试 | `--dry-run`、`--json`、`--assumeyes` 行为 |

### 21.14 需要明确 MVP 范围

建议 MVP 不要一次实现全部能力。

MVP 建议只包含：

1. `copa search <keyword>`
2. `copa install <package>`
3. 单包安装
4. Fedora / RPM Fusion / Terra 已启用 repo 搜索
5. Copr API 搜索仓库名
6. `copr-cli` 对候选 Copr 做二次验证
7. 用户手动选择 Copr
8. `dnf5 copr enable`
9. `dnf5 makecache --refresh`
10. `dnf5 install`
11. 安装后默认禁用 Copr，用户可选择保留或删除
12. `--dry-run`
13. JSON 状态文件

暂缓实现：

- JSON 输出
- 完整评分系统
- `copa audit`
- rpm-ostree backend，仅检测并提示
- 自动识别命令名 provides
- 多包安装
- 复杂 transaction 分析

## 22. 实施优先级建议

建议按以下阶段实现。

### 阶段 1：MVP

目标：实现完整可用的单包交互式安装流程。

包含：

- DNF5 命令检测。
- Fedora / RPM Fusion / Terra 搜索。
- Copr API 搜索。
- Copr 候选列表展示。
- 用户选择 Copr。
- 启用 Copr。
- makecache。
- install。
- 安装后默认禁用 Copr，并询问用户是否保留、禁用或删除。
- `--dry-run`。
- JSON 状态文件。
- `copr-cli` 硬依赖检测。

### 阶段 2：安全增强

包含：

- 风险评分。
- 风险词识别。
- 当前 chroot 支持检查。
- 安装失败自动回滚。
- 已存在 Copr 检测。
- repo 来源限定。

### 阶段 3：查询增强

包含：

- `copa info`
- `copa repoquery`
- `copa list --packages`
- `copa provides`
- `--json`
- 本地缓存。

### 阶段 4：维护与审计

包含：

- `copa audit`
- 状态数据库。
- 已安装 Copr 包追踪。
- 残留 repo 检测。
- 长期无更新 Copr 警告。

### 阶段 5：发行与打包

包含：

- RPM spec。
- Copr 自举仓库。
- man page。
- shell completion。
- README。
- 示例配置文件。

## 23. 当前方案的关键决策

以下问题已确认：

1. `copa install` 在 Fedora 官方源、RPM Fusion、Terra 每一步搜索到包时，都询问用户是否继续搜索；直接按回车默认从当前来源安装。
2. 安装后 Copr 默认策略是 `disable`，即禁用 repo 但保留 repo 文件。
3. 不允许 `-y` 自动接受 Copr 搜索结果；需要 Copr 选择时必须显式指定 `--copr owner/project` 或进入交互选择。
4. 默认严格限定目标包来源，避免 DNF 从非用户选择的仓库安装目标包。
5. Terra repo id 做成可配置模式。
6. `dnf5` 已软链接到 `dnf` 的系统中，仍优先按 `dnf5` 语义解析；执行命令时优先使用 `dnf5`，必要时 fallback 到 `dnf`。
7. 暂时不支持 Fedora Atomic / rpm-ostree 系统；只检测并提示。
8. MVP 先用 JSON 保存状态。
9. `copr-cli` 作为硬依赖。
10. MVP 先支持单包安装，暂不支持一次安装多个包。
