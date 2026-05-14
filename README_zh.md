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
- **版本 fallback** - OBS 包版本不匹配时警告
- **安装后策略** - 默认保留仓库，用户可选择禁用/删除
- **风险评估** - 自动评估 Copr/OBS 包的风险等级
- **Shell 补全** - bash 和 zsh 补全脚本
- **Man page** - `man copa`

## 安装

### 从源码安装

```bash
git clone https://github.com/WenYin-Community/fedora-copa.git
cd fedora-copa
pip install --user .
```

### 依赖

- Python 3.11+
- `dnf5` 或 `dnf`
- `copr-cli`
- `python3-copr` (PyPI: `copr`)
- `httpx`

运行 `copa doctor` 检查依赖。

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
# 交互式安装（按优先级搜索所有来源）
copa install ghostty

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

OBS 搜索支持版本 fallback：

- 如果当前 Fedora 版本没有匹配的包，会尝试上一个版本
- 最多 fallback 2 个版本
- 版本不匹配时会明确提示风险

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
```

## 许可证

GPL-2.0-or-later

## 致谢

- [Fedora Copr](https://copr.fedorainfracloud.org/) - Fedora 社区构建服务
- [openSUSE Build Service](https://build.opensuse.org/) - 跨发行版构建服务
- [DNF5](https://github.com/rpm-software-management/dnf5) - 下一代包管理器
- [paru](https://github.com/Morganamilo/paru) - AUR 助手（搜索逻辑参考）
