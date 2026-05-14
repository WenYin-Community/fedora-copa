# API 调研笔记

## DNF5 Python API

### 安装

```bash
sudo dnf install python3-libdnf5
```

### 导入

```python
import libdnf5
import libdnf5.base
import libdnf5.repo
import libdnf5.rpm
```

### 基础用法

```python
# 初始化
base = libdnf5.base.Base()
base.load_config()
base.setup()

# 加载仓库
repo_sack = base.get_repo_sack()
repo_sack.create_repos_from_system_configuration()
repo_sack.load_repos()
```

### 搜索包

```python
query = libdnf5.rpm.PackageQuery(base)
query.filter_name(["bash"])  # 精确匹配
query.filter_name(["python3-*"], libdnf5.common.QueryCmp_GLOB)  # glob 模式

for pkg in query:
    print(f"{pkg.get_nevra()} - {pkg.get_summary()}")
```

### 列出仓库

```python
repo_query = libdnf5.repo.RepoQuery(base)
repo_query.filter_enabled(True)

for repo in repo_query:
    print(f"ID: {repo.get_id()}")
    print(f"Name: {repo.get_config().name.get_value()}")
```

### 安装包

```python
goal = libdnf5.base.Goal(base)
goal.add_install("htop")

transaction = goal.resolve()

if transaction.get_problems() != libdnf5.base.GoalProblem_NO_PROBLEM:
    print("依赖解析失败")
else:
    transaction.download()
    result = transaction.run()
```

### 注意事项

- 安装/卸载需要 root 权限
- `Base` 对象不是线程安全的
- API 仍在发展中，不同版本可能有差异

---

## Copr API

### Base URL

```
https://copr.fedorainfracloud.org/api_3/
```

### 认证

- 只读端点（搜索、查询）**不需要认证**
- 写操作需要 API Token，存放在 `~/.config/copr`

### Python 客户端

```bash
# PyPI
pip install copr

# Fedora
dnf install python3-copr
```

```python
from copr.v3 import Client

client = Client.create_from_config_file()

# 搜索项目
projects = client.project_proxy.search("ghostty")

# 获取包列表
packages = client.package_proxy.get_list("owner", "project")

# 获取构建列表
builds = client.build_proxy.get_list("owner", "project", packagename="pkg")
```

### HTTP API 端点

| 功能 | 端点 | 方法 |
|------|------|------|
| 搜索项目 | `/api_3/project/search?query=<keyword>` | GET |
| 项目详情 | `/api_3/project/?ownername=<owner>&projectname=<project>` | GET |
| 包列表 | `/api_3/package/list?ownername=<owner>&projectname=<project>` | GET |
| 构建列表 | `/api_3/build/list?ownername=<owner>&projectname=<project>&packagename=<package>` | GET |

### 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 端点默认 | 返回条目数 |
| `offset` | int | `0` | 跳过条目数 |
| `order` | str | `id` | 排序字段 |
| `order_type` | str | `ASC` | 排序方向 |

### 响应格式

```json
{
  "items": [...],
  "meta": {
    "limit": 10,
    "offset": 0,
    "order": "id",
    "order_type": "DESC"
  }
}
```

---

## 混合使用策略

| 操作 | 推荐方式 |
|------|----------|
| 搜索包（repoquery） | `libdnf5` Python API |
| 列出仓库 | `libdnf5` Python API |
| 安装包 | `subprocess` + `sudo dnf5` |
| Copr 搜索 | `python-copr` 客户端 |
| Copr 项目查询 | `python-copr` 客户端 |
| Copr enable/disable | `subprocess` + `sudo dnf5 copr` |
| makecache | `subprocess` + `sudo dnf5` |
| OBS 搜索 | OBS REST API (`httpx`) |
| OBS repo 添加 | 用户手动执行命令 |

---

## openSUSE Build Service (OBS) API

### Base URL

```
https://api.opensuse.org
```

### 认证

- 只读操作**不需要认证**
- 写操作需要 HTTP Basic Auth

### API 文档

- OpenAPI 规范: https://api.opensuse.org/apidocs/
- 格式: XML，需要设置 `Accept: application/xml; charset=utf-8`

### 主要端点

| 功能 | 端点 | 方法 |
|------|------|------|
| 搜索项目 | `/search/project?match=<xpath>` | GET |
| 搜索包 | `/search/package?match=<xpath>` | GET |
| 搜索二进制 | `/search/released/binary?match=<xpath>` | GET |
| 项目元数据 | `/source/<project>/_meta` | GET |
| 包元数据 | `/source/<project>/<package>/_meta` | GET |

### XPath 查询语法

```bash
# 按名称搜索项目
match=contains(@name,'ghostty')

# 按名称搜索包
match=@name='ghostty'

# 组合查询
match=name='ghostty'+and+repository='Fedora_43'

# 支持的函数
boolean, contains, not, starts_with, ends_with
```

### Python 调用示例

```python
import httpx
import xml.etree.ElementTree as ET

client = httpx.Client(
    headers={"Accept": "application/xml; charset=utf-8"},
    timeout=30.0,
)

# 搜索包
response = client.get(
    "https://api.opensuse.org/search/package",
    params={"match": "@name='ghostty'"}
)
root = ET.fromstring(response.text)

for pkg in root.findall(".//package"):
    print(f"Name: {pkg.get('name')}")
    print(f"Project: {pkg.get('project')}")
```

### 获取 Fedora 仓库

```python
# 获取项目仓库列表
response = client.get(f"https://api.opensuse.org/source/{project}/_meta")
root = ET.fromstring(response.text)

for repo in root.findall(".//repository"):
    repo_name = repo.get("name")
    # 从仓库名提取 Fedora 版本
    # 格式: Fedora_43, Fedora_43_x86_64, fedora-43-x86_64
```

### Repo 文件 URL

```
https://download.opensuse.org/repositories/<project>/<repository>/<project>.repo
```

### CLI 工具 osc

```bash
# Fedora 安装
sudo dnf config-manager --add-repo https://download.opensuse.org/repositories/openSUSE:/Tools/Fedora_43/openSUSE:Tools.repo
sudo dnf install osc

# 常用命令
osc ls                              # 列出项目
osc ls <project>                    # 列出项目中的包
osc results                         # 查看构建结果
osc repourls                        # 获取 repo URL
```

### 版本 Fallback 策略

1. 查询当前 Fedora 版本（如 `fedora-43`）的包
2. 如果没有，查询上一个版本（如 `fedora-42`）的包
3. 最多 fallback 2 个版本
4. 必须向用户提示版本 mismatch 风险

---

## 参考资源

- DNF5 Python 文档: https://dnf5.readthedocs.io/en/stable/api/python/python.html
- Copr API Swagger: https://copr.fedorainfracloud.org/api_3/docs/
- python-copr 文档: https://python-copr.readthedocs.io/en/latest/
- Copr GitHub: https://github.com/fedora-copr/copr
- OBS API 文档: https://api.opensuse.org/apidocs/
- osc 文档: https://www.open-build-service.org/help/manuals/obs-user-guide/cha-obs-osc
- osc GitHub: https://github.com/openSUSE/osc
