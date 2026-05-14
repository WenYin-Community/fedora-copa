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

## 安装

### 从源码安装

```bash
git clone https://github.com/yourusername/copa.git
cd copa
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
copa search ghostty
copa search --official-only vim
copa search --copr-only firefox
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

### 管理 Copr 仓库

```bash
copa copr list
copa copr enable owner/project
copa copr disable owner/project
copa copr remove owner/project
```

## 命令选项

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

### 全局选项

| 选项 | 说明 |
|------|------|
| `-V, --version` | 显示版本 |
| `-v, --verbose` | 详细输出 |

## 安装后策略

安装完成后，`copa` 会询问是否保留 Copr/OBS 仓库：

```
Keep Copr repository owner/project enabled for future updates?

[1] Keep enabled
[2] Disable repo [default]
[3] Remove repo file
Select [1/2/3]:
```

默认行为：禁用仓库（保留 repo 文件）

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
