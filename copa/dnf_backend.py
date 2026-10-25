"""DNF5 backend - handles interaction with DNF5"""

import fnmatch
import re
import shutil
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

    def __init__(
        self,
        binary: str | None = None,
        prefer_dnf5: bool = True,
        fallback_to_dnf: bool = True,
        assumeyes: bool = False,
    ):
        if binary:
            self._binary = binary
        else:
            from copa.utils import get_dnf_binary
            self._binary = get_dnf_binary(
                prefer_dnf5=prefer_dnf5, fallback_to_dnf=fallback_to_dnf
            )
        self.binary = self._binary
        self._assume_yes = assumeyes
        # dnf5 uses --repo, dnf uses --repoid
        self._repo_flag = "--repo" if "dnf5" in self._binary else "--repoid"

    @staticmethod
    def _glob_escape(keyword: str) -> str:
        """Escape dnf glob metacharacters so the keyword matches literally."""
        out = []
        for ch in keyword:
            if ch in "*?[]":
                out.append(f"[{ch}]")
            else:
                out.append(ch)
        return "".join(out)

    def _run(
        self, args: list[str], sudo: bool = False, timeout: int | None = 60
    ) -> subprocess.CompletedProcess[str]:
        """Execute dnf command"""
        import os
        cmd: list[str] = []
        if sudo:
            cmd.append("sudo")
        cmd.append(self._binary)
        if self._assume_yes:
            cmd.append("-y")
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
        args = ["repoquery", "--info", f"*{self._glob_escape(keyword)}*"]
        if repo:
            args.extend([self._repo_flag, repo])

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repoquery(result.stdout)

    @staticmethod
    def _build_package(fields: dict[str, str]) -> Package:
        """Build Package from parsed repoquery fields."""
        epoch = fields.get("Epoch", "0")
        version = fields.get("Version", "")
        release = fields.get("Release", "")
        return Package(
            name=fields.get("Name", ""),
            version=version,
            release=release,
            arch=fields.get("Architecture") or fields.get("Arch", ""),
            summary=fields.get("Summary", ""),
            repo=(
                fields.get("Repository")
                or fields.get("From repository")
                or fields.get("Repo", "")
            ),
            evr=f"{epoch}:{version}-{release}",
        )

    def _parse_repoquery(self, output: str) -> list[Package]:
        """Parse repoquery output"""
        packages: list[Package] = []
        current: dict[str, str] = {}

        # Trailing newline ensures the last entry is flushed
        for line in (output + "\n").split("\n"):
            line = line.strip()
            if not line:
                if current:
                    packages.append(self._build_package(current))
                    current = {}
                continue

            if ":" in line:
                key, _, value = line.partition(":")
                current[key.strip()] = value.strip()

        return packages

    def repolist(self, enabled_only: bool = True) -> list[Repo]:
        """List repos"""
        args = ["repolist", "--enabled" if enabled_only else "--all"]

        result = self._run(args)
        if result.returncode != 0:
            return []

        return self._parse_repolist(result.stdout)

    def _parse_repolist(self, output: str) -> list[Repo]:
        """Parse repolist output"""
        repos = []
        lines = output.strip().split("\n")

        # Skip header line
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

    def get_enabled_repos(
        self, terra_patterns: list[str] | None = None
    ) -> dict[str, list[str]]:
        """Get enabled repos, categorized by type"""
        if terra_patterns is None:
            terra_patterns = ["terra*"]
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
            elif any(
                fnmatch.fnmatchcase(repo_id_lower, pattern.lower())
                for pattern in terra_patterns
            ):
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
        args.append(f"*{self._glob_escape(keyword)}*")

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
        args = ["repoquery", "--info", "--installed", f"*{self._glob_escape(keyword)}*"]
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

    def _query_lines(self, args: list[str]) -> list[str]:
        """Run a read-only repoquery and return non-empty output lines."""
        result = self._run(args)
        if result.returncode != 0:
            return []
        return [
            line.strip()
            for line in result.stdout.strip().split("\n")
            if line.strip()
        ]

    def query_requires(self, package: str) -> list[str]:
        """Query package dependencies"""
        return self._query_lines(["repoquery", "--requires", package])

    def query_provides(self, package: str) -> list[str]:
        """Query what a package provides"""
        return self._query_lines(["repoquery", "--provides", package])

    def query_files(self, package: str) -> list[str]:
        """Query package file list"""
        return self._query_lines(["repoquery", "--list", package])

    def query_info(self, package: str) -> str:
        """Query raw package info"""
        result = self._run(["repoquery", "--info", package])
        if result.returncode != 0:
            return ""
        return result.stdout

    def search_providers(self, file_path: str) -> list[str]:
        """Find packages providing a file path or command.

        Installed ownership is queried first (fast, from the rpmdb). Only when
        the file is not installed are available repos queried. A bare command
        name is resolved through PATH first.
        """
        candidates = [file_path]
        if "/" not in file_path:
            resolved = shutil.which(file_path)
            if resolved and resolved not in candidates:
                candidates.append(resolved)

        results: list[str] = []
        for candidate in candidates:
            installed = self._query_lines(
                ["repoquery", "--installed", "--file", candidate]
            )
            for line in installed:
                if line not in results:
                    results.append(line)
            if installed:
                continue

            for line in self._query_lines(["repoquery", "--file", candidate]):
                if line not in results:
                    results.append(line)
        return results

    def _os_release_identity(self) -> tuple[str, str]:
        """Read (distribution id, version) from /etc/os-release (cached)."""
        if not hasattr(self, '_cached_os_release'):
            distro_id = "fedora"
            version = "rawhide"
            try:
                with open("/etc/os-release") as f:
                    os_content = f.read()
                id_match = re.search(r'^ID="?([^"\n]+)"?', os_content, re.MULTILINE)
                if id_match:
                    distro_id = id_match.group(1).lower()
                version_match = re.search(
                    r'^VERSION_ID="?([^"\n]+)"?', os_content, re.MULTILINE
                )
                if version_match:
                    raw_version = version_match.group(1).strip()
                    numeric = re.search(r'(\d+)', raw_version)
                    version = numeric.group(1) if numeric else raw_version.lower()
            except OSError:
                pass
            self._cached_os_release = (distro_id, version)
        return self._cached_os_release

    def _os_release_version(self) -> str:
        """Read VERSION_ID from /etc/os-release (cached)."""
        return self._os_release_identity()[1]

    def get_distro_id(self) -> str:
        """Return the distribution id from /etc/os-release."""
        return self._os_release_identity()[0]

    def is_fedora(self) -> bool:
        """Return whether the host distribution is Fedora."""
        return self.get_distro_id() == "fedora"

    def get_chroot(self) -> str:
        """Get current chroot"""
        result = subprocess.run(["uname", "-m"], capture_output=True, text=True)
        arch = result.stdout.strip() if result.returncode == 0 else "x86_64"
        distro_id, version = self._os_release_identity()
        namespace = {
            "fedora": "fedora",
            "rhel": "rhel",
            "centos": "centos-stream",
        }.get(distro_id, distro_id)
        return f"{namespace}-{version}-{arch}"

    def get_fedora_version(self) -> int:
        """Get Fedora version number (0 for rawhide and non-Fedora hosts)."""
        if not self.is_fedora():
            return 0
        try:
            return int(self._os_release_version())
        except ValueError:
            return 0
