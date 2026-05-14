"""DNF5 后端 - 处理与 DNF5 的交互"""

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
        # TODO: 解析输出
        return []

    def repolist(self, enabled_only: bool = True) -> list[Repo]:
        """列出仓库"""
        args = ["repolist"]
        if enabled_only:
            args.append("--enabled")

        result = self._run(args)
        # TODO: 解析输出
        return []

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
        # TODO: 解析输出
        return []

    def get_chroot(self) -> str:
        """获取当前 chroot"""
        # 从 releasever 和 arch 构建
        result = self._run(["--version"])
        # TODO: 解析版本
        return "fedora-rawhide-x86_64"
