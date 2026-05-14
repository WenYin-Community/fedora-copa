"""DNF5 后端 - 处理与 DNF5 的交互"""

import re
import subprocess
from dataclasses import dataclass


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
        """Execute dnf command"""
        cmd = []
        if sudo:
            cmd.append("sudo")
        cmd.append(self._binary)
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True)

    def search(self, keyword: str, repo: str | None = None) -> list[Package]:
        """Search packages"""
        args = ["repoquery", "--queryinfo", keyword]
        if repo:
            args.extend(["--repo", repo])

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repoquery(result.stdout)

    def _parse_repoquery(self, output: str) -> list[Package]:
        """Parse repoquery output"""
        packages = []
        current = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    epoch = current.get("Epoch", "0")
                    version = current.get("Version", "")
                    release = current.get("Release", "")
                    evr = f"{epoch}:{version}-{release}"
                    packages.append(Package(
                        name=current.get("Name", ""),
                        version=version,
                        release=release,
                        arch=current.get("Architecture", ""),
                        summary=current.get("Summary", ""),
                        repo=current.get("Repo", ""),
                        evr=evr,
                    ))
                    current = {}
                continue

            if ":" in line:
                key, _, value = line.partition(":")
                current[key.strip()] = value.strip()

        # Handle last package
        if current:
            epoch = current.get("Epoch", "0")
            version = current.get("Version", "")
            release = current.get("Release", "")
            evr = f"{epoch}:{version}-{release}"
            packages.append(Package(
                name=current.get("Name", ""),
                version=version,
                release=release,
                arch=current.get("Architecture", ""),
                summary=current.get("Summary", ""),
                repo=current.get("Repo", ""),
                evr=evr,
            ))

        return packages

    def repolist(self, enabled_only: bool = True) -> list[Repo]:
        """List repos"""
        args = ["repolist"]
        if enabled_only:
            args.append("--enabled")

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repolist(result.stdout)

    def _parse_repolist(self, output: str) -> list[Repo]:
        """Parse repolist output"""
        repos = []
        lines = output.strip().split("\n")

        # 跳过标题行
        for line in lines[1:]:
            # 使用多个空格作为分隔符
            # 格式: repo_id<多个空格>repo_name
            parts = line.split(None, 1)
            if len(parts) >= 2:
                repo_id = parts[0].strip()
                repo_name = parts[1].strip()
                repos.append(Repo(id=repo_id, name=repo_name, enabled=True))
            elif len(parts) == 1:
                repo_id = parts[0].strip()
                repos.append(Repo(id=repo_id, name="", enabled=True))

        return repos

    def get_enabled_repos(self) -> dict[str, list[str]]:
        """Get enabled repos, categorized by type"""
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
            # Check more specific conditions first
            if repo_id_lower.startswith("copr:") or repo_id_lower.startswith("coprdep:"):
                categorized["copr"].append(repo.id)
            elif "rpmfusion" in repo_id_lower:
                categorized["rpmfusion"].append(repo.id)
            elif "terra" in repo_id_lower:
                categorized["terra"].append(repo.id)
            elif repo_id_lower.startswith("home_") or repo_id_lower.startswith("home:"):
                categorized["obs"].append(repo.id)
            elif "fedora" in repo_id_lower or "updates" in repo_id_lower:
                categorized["fedora"].append(repo.id)
            else:
                categorized["other"].append(repo.id)

        return categorized

    def search_in_repos(self, keyword: str, repo_ids: list[str]) -> list[Package]:
        """Search in specified repos"""
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

    def install(self, package: str, repo: str | None = None) -> bool:
        """Install package"""
        args = ["install", package]
        if repo:
            args.extend(["--repo", repo])

        result = self._run(args, sudo=True)
        return result.returncode == 0

    def makecache(self, repo: str | None = None) -> bool:
        """Refresh cache"""
        args = ["makecache"]
        if repo:
            args.extend(["--repo", repo])
        else:
            args.append("--refresh")

        result = self._run(args, sudo=True)
        return result.returncode == 0

    def copr_enable(self, owner_project: str, chroot: str | None = None) -> bool:
        """Enable Copr repo"""
        args = ["copr", "enable", owner_project]
        if chroot:
            args.append(chroot)

        result = self._run(args, sudo=True)
        return result.returncode == 0

    def copr_disable(self, owner_project: str) -> bool:
        """Disable Copr repo"""
        result = self._run(["copr", "disable", owner_project], sudo=True)
        return result.returncode == 0

    def copr_remove(self, owner_project: str) -> bool:
        """Remove Copr repo"""
        result = self._run(["copr", "remove", owner_project], sudo=True)
        return result.returncode == 0

    def copr_list(self) -> list[str]:
        """List enabled Copr repos"""
        result = self._run(["copr", "list"])
        if result.returncode != 0:
            return []

        # 解析输出，每行是一个 copr 仓库
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def get_chroot(self) -> str:
        """Get current chroot"""
        # Get version from /etc/os-release
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

        # Get architecture
        result = subprocess.run(["uname", "-m"], capture_output=True, text=True)
        arch = result.stdout.strip() if result.returncode == 0 else "x86_64"

        return f"fedora-{version}-{arch}"

    def get_fedora_version(self) -> int:
        """Get Fedora version number"""
        try:
            with open("/etc/os-release") as f:
                content = f.read()
            version_match = re.search(r'VERSION_ID="(\d+)"', content)
            if version_match:
                return int(version_match.group(1))
        except Exception:
            pass
        return 0
