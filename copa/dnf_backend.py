"""DNF5 后端 - 处理与 DNF5 的交互"""

import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class Package:
    """软件包信息"""
    name: str
    version: str
    release: str
    arch: str
    summary: str
    repo: str
    evr: str  # epoch:version-release


@dataclass
class Repo:
    """仓库信息"""
    id: str
    name: str
    enabled: bool


class DnfBackend:
    """DNF5 后端封装"""

    def __init__(self, use_dnf5: bool = True):
        self.use_dnf5 = use_dnf5
        self._binary = "dnf5" if use_dnf5 else "dnf"

    def _run(self, args: list[str], sudo: bool = False) -> subprocess.CompletedProcess:
        """执行 dnf 命令"""
        cmd = []
        if sudo:
            cmd.append("sudo")
        cmd.append(self._binary)
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True)

    def search(self, keyword: str, repo: Optional[str] = None) -> list[Package]:
        """搜索软件包"""
        args = ["repoquery", "--queryinfo", keyword]
        if repo:
            args.extend(["--repo", repo])

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repoquery(result.stdout)

    def _parse_repoquery(self, output: str) -> list[Package]:
        """解析 repoquery 输出"""
        packages = []
        current = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    packages.append(Package(
                        name=current.get("Name", ""),
                        version=current.get("Version", ""),
                        release=current.get("Release", ""),
                        arch=current.get("Architecture", ""),
                        summary=current.get("Summary", ""),
                        repo=current.get("Repo", ""),
                        evr=current.get("Epoch", "0") + ":" + current.get("Version", "") + "-" + current.get("Release", ""),
                    ))
                    current = {}
                continue

            if ":" in line:
                key, _, value = line.partition(":")
                current[key.strip()] = value.strip()

        # 处理最后一个包
        if current:
            packages.append(Package(
                name=current.get("Name", ""),
                version=current.get("Version", ""),
                release=current.get("Release", ""),
                arch=current.get("Architecture", ""),
                summary=current.get("Summary", ""),
                repo=current.get("Repo", ""),
                evr=current.get("Epoch", "0") + ":" + current.get("Version", "") + "-" + current.get("Release", ""),
            ))

        return packages

    def repolist(self, enabled_only: bool = True) -> list[Repo]:
        """列出仓库"""
        args = ["repolist"]
        if enabled_only:
            args.append("--enabled")

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repolist(result.stdout)

    def _parse_repolist(self, output: str) -> list[Repo]:
        """解析 repolist 输出"""
        repos = []
        lines = output.strip().split("\n")

        # 跳过标题行
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                repo_id = parts[0]
                repo_name = " ".join(parts[1:])
                # 判断是否启用（通常 repolist --enabled 只显示启用的）
                repos.append(Repo(id=repo_id, name=repo_name, enabled=True))

        return repos

    def get_enabled_repos(self) -> dict[str, list[str]]:
        """获取已启用仓库，按类型分类"""
        repos = self.repolist(enabled_only=True)
        categorized = {
            "fedora": [],
            "rpmfusion": [],
            "terra": [],
            "copr": [],
            "obs": [],
            "other": [],
        }

        for repo in repos:
            repo_id_lower = repo.id.lower()
            if "fedora" in repo_id_lower or "updates" in repo_id_lower:
                categorized["fedora"].append(repo.id)
            elif "rpmfusion" in repo_id_lower:
                categorized["rpmfusion"].append(repo.id)
            elif "terra" in repo_id_lower:
                categorized["terra"].append(repo.id)
            elif "copr" in repo_id_lower:
                categorized["copr"].append(repo.id)
            elif "obs" in repo_id_lower or "opensuse" in repo_id_lower:
                categorized["obs"].append(repo.id)
            else:
                categorized["other"].append(repo.id)

        return categorized

    def search_in_repos(self, keyword: str, repo_ids: list[str]) -> list[Package]:
        """在指定仓库中搜索"""
        if not repo_ids:
            return []

        args = ["repoquery", "--queryinfo"]
        for repo_id in repo_ids:
            args.extend(["--repo", repo_id])
        args.append(keyword)

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repoquery(result.stdout)

    def install(self, package: str, repo: Optional[str] = None) -> bool:
        """安装软件包"""
        args = ["install", package]
        if repo:
            args.extend(["--repo", repo])

        result = self._run(args, sudo=True)
        return result.returncode == 0

    def makecache(self, repo: Optional[str] = None) -> bool:
        """刷新缓存"""
        args = ["makecache"]
        if repo:
            args.extend(["--repo", repo])
        else:
            args.append("--refresh")

        result = self._run(args, sudo=True)
        return result.returncode == 0

    def copr_enable(self, owner_project: str, chroot: Optional[str] = None) -> bool:
        """启用 Copr 仓库"""
        args = ["copr", "enable", owner_project]
        if chroot:
            args.append(chroot)

        result = self._run(args, sudo=True)
        return result.returncode == 0

    def copr_disable(self, owner_project: str) -> bool:
        """禁用 Copr 仓库"""
        result = self._run(["copr", "disable", owner_project], sudo=True)
        return result.returncode == 0

    def copr_remove(self, owner_project: str) -> bool:
        """移除 Copr 仓库"""
        result = self._run(["copr", "remove", owner_project], sudo=True)
        return result.returncode == 0

    def copr_list(self) -> list[str]:
        """列出已启用的 Copr 仓库"""
        result = self._run(["copr", "list"])
        if result.returncode != 0:
            return []

        # 解析输出，每行是一个 copr 仓库
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def get_chroot(self) -> str:
        """获取当前 chroot"""
        # 从 /etc/os-release 获取版本
        try:
            with open("/etc/os-release") as f:
                content = f.read()
            version_match = re.search(r'VERSION_ID="(\d+)"', content)
            if version_match:
                version = version_match.group(1)
            else:
                version = "rawhide"
        except Exception:
            version = "rawhide"

        # 获取架构
        result = subprocess.run(["uname", "-m"], capture_output=True, text=True)
        arch = result.stdout.strip() if result.returncode == 0 else "x86_64"

        return f"fedora-{version}-{arch}"

    def get_fedora_version(self) -> int:
        """获取 Fedora 版本号"""
        try:
            with open("/etc/os-release") as f:
                content = f.read()
            version_match = re.search(r'VERSION_ID="(\d+)"', content)
            if version_match:
                return int(version_match.group(1))
        except Exception:
            pass
        return 0
