# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概述

`copa` 是 Fedora / DNF5 生态的 Copr 包助手，提供类似 Arch 上 `paru`/`yay` 的搜索安装体验。支持 5 种包源：Fedora 官方、RPM Fusion、Terra、Copr、openSUSE OBS。

## 常用命令

```bash
# 安装开发依赖（editable）
pip install --user -e ".[dev]"

# 测试
make test            # 等价 pytest tests/ -v
pytest tests/test_cli.py -v                          # 单个测试文件
pytest tests/test_cli.py::TestFilterByKeywords -v    # 单个测试类

# 检查
make lint            # ruff check . + mypy copa/
ruff check .         # 只跑 ruff（line-length=100, target py311）

# 构建
make build           # 构建 Fedora 43 + 44 RPM（本机需 rpm-build）
make build-srpm      # 构建 SRPM —— 会从 GitHub Releases 下载源码包，需先有同名 tag 且 Release 已生成
make clean           # 清理 build/ dist/ *.egg-info/ __pycache__
```

**发布流程（CI 驱动，勿手动）**：推送 `v*` tag → `ci.yml` 自动 lint+test → 构建 RPM/SRPM → 创建 GitHub Release → 触发 Copr 构建。见下方「发布与 CI」。

## 架构

```
copa/
├── cli.py           # argparse 入口 + 所有 cmd_* 函数 + _resolve_package_name + 过滤器函数
├── search.py        # SearchEngine：多后端聚合、风险评估、版本回退
├── dnf_backend.py   # DnfBackend：dnf5/dnf 子进程封装（不依赖 libdnf5 Python 绑定）
├── copr_backend.py  # CoprBackend：python-copr (copr.v3) API 封装 + 重试
├── obs_backend.py   # OBSBackend：openSUSE OBS XML API（httpx 同步）+ 重试
├── config.py        # Config dataclass、TOML 配置读写
├── state.py         # AppState dataclass、JSON 状态文件（记录 copa 启用的 repo）
└── utils.py         # get_dnf_binary()、confirm 提示、check_command_exists
```

### 数据流

1. 用户输入 → `cli.py`（argparse）→ 分发到 `cmd_*` 函数
2. `cmd_*` 初始化后端：`DnfBackend`、`CoprBackend`、`OBSBackend`
3. `SearchEngine` 聚合多后端结果
4. 安装流：搜索 → 选择 → 版本回退检查 → 启用 repo → 解析包名 → 确认 → `dnf install` → 保存状态

### 关键设计决策

- **并行搜索只发生在 `cmd_install`**：`cli.py:659` 用 `ThreadPoolExecutor(max_workers=2)` 同时搜索 Copr 和 OBS，各取前 10 条合并展示。`SearchEngine.search_all()` 本身是顺序执行，不要误以为并行在 search.py。
- **版本回退**：Copr（按 chroot）和 OBS（按 repo）最多回退 2 个版本，需显式风险警告 + 用户确认。
- **包名解析**：`_resolve_package_name()`（cli.py）在已启用的 repo 内搜索实际 RPM 名（project 名 ≠ 包名），找不到则回退 project 名，总会列出结果供选择。
- **失败/取消时保持 repo 启用**：不静默自动禁用，给用户显式 disable/remove 指令。
- **网络错误处理**：python-copr 库内部已对连接错误自动重试（`connection_attempts=3`）；`CoprBackend` 对 404/403 静默处理，对网络/其他 API 错误打印 stderr 警告后返回空结果（不静默、不崩溃）。OBS 各方法对网络错误返回空结果。
- **风险评估**：`_assess_copr_risk()` / `_assess_obs_risk()`（search.py）基于关键词与版本差距（gap=0 低、gap=1 中、gap>=2 高、无匹配则阻止）。
- **状态追踪**：`~/.local/share/copa/state.json` 记录 copa 启用的 repo 便于清理。
- **配置**：`~/.config/copa/config.toml` 控制搜索源开关、安装策略、默认 post-action。
- **后端隔离**：三个 Backend 类各自封装外部系统交互，无相互依赖。
- **子进程调用**：`DnfBackend` 调 `dnf5`/`dnf` CLI（`subprocess.run`），不用 libdnf5 Python 绑定。sudo 命令用 `capture_output=False` 让密码提示可见。
- **dnf5/dnf 兼容**：优先 dnf5（Fedora 41+ 默认），dnf 为旧系统回退（`get_dnf_binary()`）。关键差异：dnf5 用 `--repo`，dnf 用 `--repoid`，`DnfBackend._repo_flag` 自动选择。新增接受 `repo` 参数的方法必须用 `self._repo_flag`。
- **`DnfBackend._run()`** 强制 `LANG=C`/`LC_ALL=C`，保证 `repoquery --info` 输出英文字段名（dnf5 默认本地化字段名）。

### 后端凭据

- **Copr**：`CoprBackend` 用 `copr.v3.Client.create_from_config_file()`（读 `~/.config/copr`）。搜索公开项目不需要有效凭据。
- **OBS**：需要 `~/.config/osc/oscrc`（api.opensuse.org 的 user/pass），无凭据则跳过并警告。`osc` 是运行时依赖（Fedora 官方源）。repo 文件下载地址：`https://download.opensuse.org/repositories/{project}/{repository}/{project}.repo`，repo ID 是文件内 section 名（冒号转下划线，如 `home:Foo` → `[home_Foo]`）。

## 安装流摘要

**默认**（Copr + OBS）：并行搜索 → 选择 → 版本回退检查 → 启用 repo → `makecache` → 解析包名 → 确认 → `dnf5 install` → 保存状态 → 询问是否禁用。

**本地 repo**（`--include-local-repo`）：搜 Fedora + RPM Fusion + Terra → 去重 → 编号列表 → 用户选 [1-N] 或 's' 继续搜 Copr/OBS → `dnf5 install`。

**移除**：搜已装包（`dnf5 repoquery --info --installed *keyword*`）→ 去重 → 列表选择 → 确认 → `dnf5 remove`（纯本地，无网络、无 repo 管理）。

## 发布与 CI

`.github/workflows/` 含两个 workflow：`ci.yml`（完整发布链路）与 `build-rpm.yml`（旧版冗余，仅 test/build-rpm/build-srpm，无发布；tag 推送会触发重复构建，可删除但需先确认无依赖）。`ci.yml` 包含 6 个 job：

1. `lint`（ruff + mypy，Python 3.11）
2. `test`（pytest，Python 3.11/3.12/3.13）
3. `build-rpm`（Fedora 43/44 容器内 `rpmbuild -bb`，noarch）
4. `build-srpm`（Fedora 44 容器内 `rpmbuild -bs`）
5. `create-release`（仅 tag 推送时）：下载 RPM/SRPM 产物 → 生成源码 tarball → 建 GitHub Release 并附产物
6. `publish-copr`（依赖 create-release，仅 tag 推送时）：用 `secrets.COPR_LOGIN`/`COPR_TOKEN` 写 `~/.config/copr` → `copr-cli build-package ruojiner/fedora-copa`

工作流内通过 `grep '__version__' copa/__init__.py` 取版本号来命名 tarball。

## 版本号：三处必须同步

发布版本号分散在三个文件，改版本时必须同时更新：

- `copa/__init__.py` 的 `__version__`（CI 以此为准生成 tarball 名）
- `rpm/copa.spec` 的 `Version:`（Makefile 从 spec 读取）
- `pyproject.toml` 的 `version`

**`make build-srpm` 的隐含先决条件**：Makefile 会 `curl` 下载 `https://github.com/.../releases/download/v{VERSION}/fedora-copa-{VERSION}.tar.gz`。本地构建 SRPM 前必须已推送同名 tag 且该 Release 存在，否则下载失败。

## 测试模式

109 个测试分布在 8 个文件。核心逻辑覆盖点：

- `DnfBackend` 测试用 `unittest.mock.patch` mock `subprocess.run`
- `AppState`/`Config` 测试用 `pytest.fixture` + `tmp_path` 建临时文件
- CLI 过滤器函数（`_filter_by_keywords` 等）直接传 Mock 对象
- `search.py` 覆盖版本回退（`_find_best_copr_chroot`）与风险分级（`_assess_copr_risk`/`_assess_obs_risk`）
- `_install_from_copr`/`_install_from_obs` 用 mock Dnf/OBS/State 覆盖安装事务流，`monkeypatch` 掉 `input`/`confirm` 跳过交互
- `CoprBackend` 用注入的 MockClient 覆盖 API 异常处理（404/403 静默、网络错误打印警告）

## 代码风格

- **所有 UI 文本与代码注释必须英文**：print、提示、错误消息、docstring、行内注释均不得出现中文
- **`copa/` 和 `tests/` 源码内禁止中文**；CLAUDE.md、README_zh.md 是文档文件，中文可接受
- `cli.py` 的 `cmd_*` 函数很长（含交互逻辑），改动时保持 ANSI 颜色码与交互流程一致
- `OBSBackend` 用同步 `httpx.Client`（懒初始化），不用 async
- 搜索支持多关键词 AND 逻辑与正则模式（`-x`），过滤器函数在 `cli.py` 底部
- Copr 搜索用 `copr.v3.Client.project_proxy.search()`，只对 project 名/owner 子串匹配（不含描述）
- chroot 探测：`VERSION_ID="?(\d+)"?` 正则同时处理 os-release 中带引号与不带引号的 VERSION_ID
