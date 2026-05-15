"""DNF5 backend - handles interaction with DNF5"""

import re
import subprocess
from dataclasses import dataclass


@dataclass
class Package:
    """Package information"""
    name: str
    version: str
    release: str
    arch: str
    summary: str
    repo: str
    evr: str  # epoch:version-release


@dataclass
class Repo:
    """Repository information"""
    id: str
    name: str
    enabled: bool


class DnfBackend:
    """DNF5 backend wrapper"""

    def __init__(self, binary: str | None = None):
        if binary:
            self._binary = binary
        else:
            from copa.utils import get_dnf_binary
            self._binary = get_dnf_binary()
        # dnf5 uses --repo, dnf uses --repoid
        self._repo_flag = "--repo" if "dnf5" in self._binary else "--repoid"

    def _run(
        self, args: list[str], sudo: bool = False, timeout: int | None = 60
    ) -> subprocess.CompletedProcess[str]:
        """Execute dnf command"""
        import os
        cmd: list[str] = []
        if sudo:
            cmd.append("sudo")
        cmd.append(self._binary)
        cmd.extend(args)
        # Force LANG=C for consistent English output (field names, etc.)
        env = {**os.environ, "LANG": "C", "LC_ALL": "C"}
        try:
            # sudo commands don't capture output so password prompt is visible
            if sudo:
                return subprocess.run(
                    cmd, text=True, capture_output=False, env=env, timeout=timeout
                )
            return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="Timed out")

    def search(
        self, keyword: str, repo: str | None = None
    ) -> list[Package]:
        """Search packages using substring match"""
        args = ["repoquery", "--info", f"*{keyword}*"]
        if repo:
            args.extend([self._repo_flag, repo])

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repoquery(result.stdout)

    def _parse_repoquery(self, output: str) -> list[Package]:
        """Parse repoquery output"""
        packages: list[Package] = []
        current: dict[str, str] = {}

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
            # Multiple spaces as separator
            # Format: repo_id<spaces>repo_name
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
        categorized: dict[str, list[str]] = {
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

        args = ["repoquery", "--info"]
        for repo_id in repo_ids:
            args.extend([self._repo_flag, repo_id])
        args.append(f"*{keyword}*")

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repoquery(result.stdout)

    def install(self, package: str, repo: str | None = None) -> bool:
        """Install package (no timeout for large downloads)"""
        args = ["install", package]
        if repo:
            args.extend([self._repo_flag, repo])

        result = self._run(args, sudo=True, timeout=None)
        return result.returncode == 0

    def remove(self, package: str) -> bool:
        """Remove installed package"""
        result = self._run(["remove", package], sudo=True)
        return result.returncode == 0

    def search_installed(self, keyword: str) -> list[Package]:
        """Search installed packages by keyword"""
        args = ["repoquery", "--info", "--installed", f"*{keyword}*"]
        result = self._run(args)
        if result.returncode != 0:
            return []
        return self._parse_repoquery(result.stdout)

    def makecache(self, repo: str | None = None) -> bool:
        """Refresh cache"""
        args = ["makecache"]
        if repo:
            args.extend([self._repo_flag, repo])
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

        # Parse output, each line is a copr repo
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def get_chroot(self) -> str:
        """Get current chroot"""
        # Get version from /etc/os-release
        try:
            with open("/etc/os-release") as f:
                content = f.read()
            version_match = re.search(r'VERSION_ID="?(\d+)"?', content)
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
            version_match = re.search(r'VERSION_ID="?(\d+)"?', content)
            if version_match:
                return int(version_match.group(1))
        except Exception:
            pass
        return 0
