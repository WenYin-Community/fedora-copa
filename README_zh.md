# copa

[English](README.md)

DNF5 风格的 Fedora Copr 软件包助手。

`copa` = **C**opr **P**ackage **A**ssistant

## 简介

`copa` 是一个面向 Fedora / DNF5 生态的 Copr 软件包助手，提供类似 Arch 下 `paru` / `yay` 的搜索与安装体验，但命令格式保持 DNF 风格。

支持以下软件包来源：

1. **Fedora 官方仓库** - 优先搜索
2. **RPM Fusion** - 已启用时参与搜索
3. **Terra** - 已启用时参与搜索
4. **Copr** - Fedora 社区构建服务
5. **openSUSE OBS** - 跨发行版构建服务（支持版本 fallback）

## 特性

- **多关键词 AND 搜索** - `copa search ghostty terminal` 匹配同时包含两个词的包
- **正则搜索** - `copa search -x "^ghost"` 支持正则表达式匹配（仅包名）
- **JSON 输出** - `copa --json search ghostty` 机器可读格式
- **统一的第三方仓库管理** - `copa repo list/enable/disable/remove`
- **版本 fallback** - Copr 和 OBS 均支持 chroot/仓库版本降级（最多降 2 个版本），明确提示风险
- **并行搜索** - Copr 和 OBS 并行搜索，提升效率
- **包名解析** - 在启用的仓库内查找实际 RPM 包名
- **安装后策略** - 默认保留仓库，用户可选择禁用/删除
- **风险评估** - 自动评估 Copr/OBS 包的风险等级
- **安装失败处理** - 失败时仓库保持启用，提示禁用/移除命令
- **Shell 补全** - bash 和 zsh 补全脚本
- **Man page** - `man copa`

## 安装

### 从源码安装

```bash
git clone https://github.com/WenYin-Community/fedora-copa.git
cd fedora-copa
pip install --user .
```

### 从 Copr 安装

```bash
sudo dnf copr enable ruojiner/fedora-copa
sudo dnf install fedora-copa
```

### 从 RPM 安装

```bash
# 从 GitHub Releases 下载
dnf install fedora-copa-*.noarch.rpm
```

### 依赖

- Python 3.11+
- `dnf5` 或 `dnf`（Fedora 41+ 默认使用 dnf5；RHEL 10+ 默认使用 dnf，但可手动安装 dnf5）
- `copr-cli`
- `python3-copr` (PyPI: `copr`)
- `httpx`
- `osc`（用于 OBS 支持）

运行 `copa doctor` 检查依赖。

### OBS 认证（可选）

OBS（openSUSE Build Service）需要认证才能使用。启用 OBS 支持：

1. 在 [build.opensuse.org](https://build.opensuse.org) 注册账号
2. 安装 `osc`：`sudo dnf install osc`
3. 配置凭证 - 创建 `~/.config/osc/oscrc`：
   ```ini
   [general]
   apiurl = https://api.opensuse.org

   [https://api.opensuse.org]
   user = 你的用户名
   pass = 你的密码
   ```

未配置 OBS 凭证时，`copa install` 会跳过 OBS 搜索，仅搜索 Copr。

### dnf5 / dnf 兼容性

`copa` 优先使用 **dnf5**（Fedora 41+ 默认）。在仅有 `dnf` 的系统上（如 RHEL 10+ 未安装 dnf5），`copa` 自动回退到 `dnf`。

以下 CLI 差异影响本项目，由 `DnfBackend` 内部处理：

| 操作 | dnf5 | dnf |
|------|------|-----|
| 按仓库过滤 | `--repo <id>` | `--repoid <id>` |
| 包详情查询 | `repoquery --info` | `repoquery --queryinfo` |
| Copr 插件 | 内置（`dnf5 copr`） | 需要 `dnf-plugins-core`（`dnf copr`） |
| `repolist --enabled` | 支持 | 支持（输出格式可能略有不同） |
| `install / remove / makecache` | 支持 | 支持 |

`copa` 通过 `get_dnf_binary()` 自动检测二进制文件，并使用 `DnfBackend._repo_flag` 选择正确的 `--repo` / `--repoid` 参数。所有子进程调用强制 `LANG=C` 确保输出为英文。无需手动配置。

## 使用

### 检查环境

```bash
copa doctor
```

### 搜索软件包

```bash
# 单关键词
copa search ghostty

# 多关键词（AND 逻辑）
copa search ghostty terminal

# 正则搜索（仅匹配包名）
copa search -x "^ghost"
copa search --regex "vim|neovim"

# 搜索特定来源
copa search --official-only vim
copa search --copr-only firefox

# JSON 输出
copa --json search ghostty
```

### 安装软件包

```bash
# 默认只搜索 Copr + OBS
copa install ghostty

# 同时搜索 Fedora、RPM Fusion、Terra
copa install --include-local-repo ghostty

# 只从 Copr 安装
copa install --copr-only ghostty

# 指定 Copr 项目
copa install --copr rivenirvana/ghostty ghostty

# 只从 OBS 安装
copa install --obs-only ghostty

# 预览模式（不实际执行）
copa install --dry-run ghostty

# 自动确认（非交互模式）
copa -y install --copr owner/project ghostty
```

### 卸载软件包

```bash
# 卸载本地已安装的软件包（交互式选择）
copa remove spark

# 自动确认
copa -y remove spark
```

`copa remove` 搜索本地已安装的匹配包，列出列表让用户选择，然后调用 `dnf5 remove` 卸载。纯本地操作，不联网查询。

### 查看包信息

```bash
# 显示包信息
copa info ghostty

# 显示 Copr 项目信息
copa info owner/project

# JSON 输出
copa --json info ghostty
```

### 列出包

```bash
# 列出 copa 管理的第三方仓库
copa list

# 列出 Copr 项目中的包
copa list --packages owner/project

# JSON 输出
copa --json list
```

### 管理第三方仓库

```bash
# 列出所有第三方仓库（Copr + OBS）
copa repo list

# 启用仓库
copa repo enable copr:owner/project
copa repo enable obs:project

# 禁用仓库
copa repo disable copr:owner/project
copa repo disable obs:project

# 删除仓库
copa repo remove copr:owner/project
copa repo remove obs:project
```

### 审计仓库

```bash
# 检查第三方仓库健康状态
copa audit
```

### 查询包依赖

```bash
# 显示包依赖
copa repoquery ghostty --requires

# 显示包提供的内容
copa repoquery ghostty --provides

# 显示包文件
copa repoquery ghostty --files

# 显示包信息（默认）
copa repoquery ghostty

# JSON 输出
copa --json repoquery ghostty --requires
```

### 查找提供特定文件的包

```bash
# 查找提供特定文件的包
copa provides /usr/bin/vim

# 查找提供特定命令的包
copa provides ghostty

# JSON 输出
copa --json provides /usr/bin/vim
```

## 命令选项

### search 命令

| 选项 | 说明 |
|------|------|
| `keyword [keyword ...]` | 搜索关键词（AND 逻辑） |
| `--official-only` | 只搜索 Fedora 官方源 |
| `--rpmfusion-only` | 只搜索 RPM Fusion |
| `--copr-only` | 只搜索 Copr |
| `-x, --regex` | 使用正则搜索（仅包名） |

### install 命令

| 选项 | 说明 |
|------|------|
| `--include-local-repo` | 同时搜索 Fedora、RPM Fusion、Terra（默认只搜 Copr + OBS） |
| `--official-only` | 只搜索 Fedora 官方源 |
| `--rpmfusion-only` | 只搜索 RPM Fusion |
| `--copr-only` | 只搜索 Copr |
| `--copr OWNER/PROJECT` | 使用指定的 Copr 仓库 |
| `--obs-only` | 只搜索 OBS |
| `--no-obs` | 跳过 OBS 搜索 |
| `--allow-obs-fallback` | 允许 OBS 版本 fallback |
| `--keep-copr` | 安装后保留 Copr 仓库 |
| `--dry-run` | 只显示将执行的操作 |
| `-y, --assumeyes` | 自动确认 |

### remove 命令

| 选项 | 说明 |
|------|------|
| `package` | 要卸载的包名（子字符串匹配已安装包） |
| `-y, --assumeyes` | 自动确认 |

### repo 命令

| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有第三方仓库 |
| `enable REPO` | 启用仓库（格式：`copr:owner/project` 或 `obs:project`） |
| `disable REPO` | 禁用仓库 |
| `remove REPO` | 删除仓库 |

### repoquery 命令

| 选项 | 说明 |
|------|------|
| `package` | 要查询的包名 |
| `--requires` | 显示包依赖 |
| `--provides` | 显示包提供的内容 |
| `--files` | 显示包文件 |

### 全局选项

| 选项 | 说明 |
|------|------|
| `-V, --version` | 显示版本 |
| `--json` | JSON 格式输出 |
| `-h, --help` | 显示帮助 |

## 安装后策略

安装完成后，`copa` 默认保留仓库并提示用户：

```
Copr repo owner/project is kept enabled.
Note: This repo will participate in system updates.
If you don't want this, you can disable or remove it:
  copa repo disable copr:owner/project
  copa repo remove copr:owner/project

Disable repo now? [y/N]:
```

## 版本 Fallback

Copr 和 OBS 均支持版本降级，当当前 Fedora 版本不可用时自动回退：

- **Copr**：项目没有当前版本的 chroot 时，尝试旧版本（如 Fedora 44 上使用 Fedora 43 的 chroot）
- **OBS**：没有当前版本的仓库时，尝试旧版本仓库
- 最多降级 2 个版本
- 版本不匹配时会明确提示风险：

```
WARNING: Version fallback!
Project: owner/project
Current system: Fedora 44 (fedora-44-x86_64)
Fallback to: Fedora 43 (fedora-43-x86_64)
This package was built for an older Fedora version.
It may have dependency issues or not work correctly.

Continue anyway? [y/N]
```

风险等级基于版本差距：
- gap=0（精确匹配）：low
- gap=1（降 1 个版本）：medium
- gap=2（降 2 个版本）：high

## 安装流程

`copa install` 默认只搜索 Copr + OBS（并行）。加 `--include-local-repo` 可同时搜索 Fedora、RPM Fusion、Terra。

### 本地仓库安装（Fedora / RPM Fusion / Terra）— 需要 `--include-local-repo`

```
copa install --include-local-repo <package>
  │
  ├─ 1. 依次搜索 Fedora + RPM Fusion + Terra
  │     命令: dnf repoquery --info --repo <repo_id> *<package>*
  │     将所有结果合并到一个列表
  │
  ├─ 2. 按包名去重
  │
  ├─ 3. 显示编号列表
  │     [ 1] aftertheflood-sparks-bar-fonts-0:2.0-20.fc44 (Fedora)
  │     [ 2] lightspark-0:0.9.0-4.fc44 (RPM Fusion)
  │     [ 3] spark-0:0.8.2-1.fc44 (Terra)
  │
  ├─ 4. 用户选择 [1-N]，输入 's' 继续搜 Copr/OBS，输入 'q' 取消
  │     ├─ 数字 → 安装选中的包
  │     ├─ 's' → 继续搜索 Copr/OBS
  │     └─ 'q' → 退出
  │
  ├─ 5. -y 模式: 自动选择第一个结果
  │
  └─ 6. 安装: sudo dnf5 install <selected_name>
```

### Copr 安装流程

```
copa install <package>
  │
  ├─ 1. 并行搜索 Copr + OBS (ThreadPoolExecutor, max_workers=2)
  │
  ├─ 2. 统一显示列表
  │     [ 1] [Copr] owner/project
  │           Chroot: ✓ | Risk: low
  │     [ 2] [OBS]  project/name
  │           Version: ✓ | Risk: medium
  │
  ├─ 3. 用户选择项目（或 --copr owner/project 指定）
  │
  ├─ 4. 版本降级警告 (version_gap > 0)
  │     └─ "Continue anyway? [y/N]"
  │
  ├─ 5. 启用仓库: sudo dnf5 copr enable owner/project <chroot>
  │
  ├─ 6. 刷新缓存: sudo dnf5 makecache --refresh
  │
  ├─ 7. 在仓库内查找实际包名
  │     命令: dnf repoquery --info --repo copr:... *<package>*
  │     ├─ 先搜用户输入，再搜项目名
  │     └─ 始终列出列表让用户选择
  │
  ├─ 8. 确认: "Install {name}? [Y/n]"（-y 跳过）
  │
  ├─ 9. 安装: sudo dnf5 install {name}
  │     ├─ 成功 → 保存状态，询问 "Disable repo now? [y/N]"
  │     ├─ 失败 → return 1，仓库保持启用，提示禁用/移除命令
  │     └─ 取消 → return 0，仓库保持启用，提示禁用/移除命令
  │
  └─ 10. 安装后: dnf5 copr disable（用户选择时）
```

### OBS 安装流程

```
copa install <package>
  │
  ├─ 1. 并行搜索 Copr + OBS
  │
  ├─ 2. 用户选择 OBS 项目
  │
  ├─ 3. 版本降级警告（当前 Fedora 版本无仓库时）
  │     └─ "Continue anyway? [y/N]"
  │
  ├─ 4. 下载仓库文件到 /etc/yum.repos.d/
  │
  ├─ 5. 保存状态（安装前立即保存）
  │
  ├─ 6. 刷新缓存: sudo dnf5 makecache --refresh
  │
  ├─ 7. 在仓库内查找实际包名
  │     命令: dnf repoquery --info --repo <obs_repo> *<package>*
  │     └─ 始终列出列表让用户选择
  │
  ├─ 8. 确认: "Install {name}? [Y/n]"（-y 跳过）
  │
  ├─ 9. 安装: sudo dnf5 install {name}
  │     ├─ 成功 → 询问 "Disable repo now? [y/N]"
  │     ├─ 失败 → return 1，仓库保持启用，提示禁用/移除命令
  │     └─ 取消 → return 0，仓库保持启用，提示禁用/移除命令
  │
  └─ 10. 安装后: 删除仓库文件（用户选择时）
```

### 失败处理

安装失败时，Copr 和 OBS 仓库均保持启用状态。copa 会打印禁用/移除指引：

```
Installation failed
Copr repo owner/project is kept enabled.
You can disable or remove it:
  copa repo disable copr:owner/project
  copa repo remove copr:owner/project
```

## 卸载流程

```
copa remove <package>
  │
  ├─ 1. 搜索本地已安装包
  │     命令: dnf repoquery --info --installed *<package>*
  │     └─ 纯本地操作，不联网
  │
  ├─ 2. 未找到 → "Package '<package>' is not installed" → return 1
  │
  ├─ 3. 按包名去重
  │
  ├─ 4. 单个匹配:
  │     ├─ 显示: <name>-<evr> (<repo>)
  │     ├─ 确认: "Remove <name>? [y/N]"（-y 跳过）
  │     └─ sudo dnf5 remove <name>
  │
  ├─ 5. 多个匹配:
  │     ├─ 显示带序号列表（含 summary）
  │     ├─ 用户选择 [1-N, q 取消]
  │     ├─ 确认: "Remove <name>? [y/N]"（-y 跳过）
  │     └─ sudo dnf5 remove <name>
  │
  └─ 6. 完成（不管理仓库，纯本地操作）
```

要点：
- 纯本地操作，不联网查询
- 通过 `*keyword*` 通配符进行子字符串匹配
- 用户必须明确选择要卸载的包
- 卸载后不会自动禁用/删除仓库（需单独执行 `copa repo disable/remove`）

## 配置文件

配置文件位置：`~/.config/copa/config.toml`

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

## 状态文件

状态文件位置：`~/.local/share/copa/state.json`

记录由 `copa` 启用的 Copr/OBS 仓库，用于安装后清理。

## Shell 补全

### Bash

```bash
# 系统级
sudo cp completions/copa.bash /etc/bash_completion.d/

# 用户级
mkdir -p ~/.bash_completion.d
cp completions/copa.bash ~/.bash_completion.d/
```

### Zsh

```bash
# 系统级
sudo cp completions/_copa /usr/share/zsh/site-functions/

# 用户级
mkdir -p ~/.zsh/completions
cp completions/_copa ~/.zsh/completions/
```

## 开发

```bash
# 安装开发依赖
pip install --user -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check .
mypy copa/

# 构建 RPM
make build
```

## 许可证

GPL-2.0-or-later

## 致谢

- [Fedora Copr](https://copr.fedorainfracloud.org/) - Fedora 社区构建服务
- [openSUSE Build Service](https://build.opensuse.org/) - 跨发行版构建服务
- [DNF5](https://github.com/rpm-software-management/dnf5) - 下一代包管理器
- [paru](https://github.com/Morganamilo/paru) - AUR 助手（搜索逻辑参考）
