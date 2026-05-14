"""OBS 后端 - 处理与 openSUSE Build Service 的交互"""

import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

OBS_API_BASE = "https://api.opensuse.org"
OBS_REPO_DIR = Path("/etc/yum.repos.d")


@dataclass
class OBSProject:
    """OBS 项目信息"""
    name: str
    title: str
    description: str


@dataclass
class OBSPackage:
    """OBS 包信息"""
    name: str
    project: str
    title: str
    description: str


@dataclass
class OBSBinary:
    """OBS 二进制包信息"""
    name: str
    project: str
    repository: str
    arch: str
    version: str
    release: str
    filename: str
    url: str


@dataclass
class OBSRepo:
    """OBS 仓库信息"""
    project: str
    repository: str
    repo_url: str
    fedora_version: str | None
    is_current_version: bool
    version_gap: int  # Gap with current version
    repo_file_name: str = ""  # 本地 repo 文件名


class OBSBackend:
    """OBS 后端封装"""

    def __init__(self, api_base: str = OBS_API_BASE):
        self.api_base = api_base
        self.client = httpx.Client(
            headers={"Accept": "application/xml; charset=utf-8"},
            timeout=30.0,
        )

    def _get(self, path: str, params: dict | None = None) -> ET.Element:
        """发送 GET 请求"""
        url = f"{self.api_base}{path}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return ET.fromstring(response.text)

    def search_projects(self, query: str, limit: int = 20) -> list[OBSProject]:
        """Search projects"""
        try:
            root = self._get("/search/project", {"match": f"contains(@name,'{query}')"})
            projects = []
            for project_elem in root.findall(".//project")[:limit]:
                name = project_elem.get("name", "")
                title = project_elem.findtext("title", "")
                description = project_elem.findtext("description", "")
                projects.append(OBSProject(
                    name=name,
                    title=title,
                    description=description,
                ))
            return projects
        except Exception:
            return []

    def search_packages(self, query: str, limit: int = 20) -> list[OBSPackage]:
        """Search packages - substring match"""
        try:
            # Use contains() for substring matching
            root = self._get("/search/package", {"match": f"contains(@name,'{query}')"})
            packages = []
            for pkg_elem in root.findall(".//package")[:limit]:
                name = pkg_elem.get("name", "")
                project = pkg_elem.get("project", "")
                title = pkg_elem.findtext("title", "")
                description = pkg_elem.findtext("description", "")
                packages.append(OBSPackage(
                    name=name,
                    project=project,
                    title=title,
                    description=description,
                ))
            return packages
        except Exception:
            return []

    def search_binaries(
        self,
        package_name: str,
        repository: str | None = None,
        limit: int = 20,
    ) -> list[OBSBinary]:
        """Search binary packages"""
        match_parts = [f"name='{package_name}'"]
        if repository:
            match_parts.append(f"repository='{repository}'")

        match = "+and+".join(match_parts)
        try:
            root = self._get("/search/released/binary", {"match": match})
            binaries = []
            for binary_elem in root.findall(".//binary")[:limit]:
                binaries.append(OBSBinary(
                    name=binary_elem.get("name", ""),
                    project=binary_elem.get("project", ""),
                    repository=binary_elem.get("repository", ""),
                    arch=binary_elem.get("arch", ""),
                    version=binary_elem.get("version", ""),
                    release=binary_elem.get("release", ""),
                    filename=binary_elem.get("filename", ""),
                    url=binary_elem.get("url", ""),
                ))
            return binaries
        except Exception:
            return []

    def get_project_repos(self, project: str) -> list[OBSRepo]:
        """Get project repo list"""
        try:
            root = self._get(f"/source/{project}/_meta")
            repos = []
            for repo_elem in root.findall(".//repository"):
                repo_name = repo_elem.get("name", "")
                # Try to extract Fedora version from repo name
                fedora_version = self._extract_fedora_version(repo_name)
                repo_url = f"https://download.opensuse.org/repositories/{project}/{repo_name}"
                repo_file_name = self._get_repo_file_name(project)

                repos.append(OBSRepo(
                    project=project,
                    repository=repo_name,
                    repo_url=repo_url,
                    fedora_version=fedora_version,
                    is_current_version=False,  # 需要外部判断
                    version_gap=0,  # 需要外部计算
                    repo_file_name=repo_file_name,
                ))
            return repos
        except Exception:
            return []

    def _extract_fedora_version(self, repo_name: str) -> str | None:
        """Extract Fedora version from repo name"""
        # 常见格式: Fedora_43, Fedora_43_x86_64, fedora-43-x86_64
        patterns = [
            r"[Ff]edora[_-](\d+)",
            r"[Ff]c(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, repo_name)
            if match:
                return match.group(1)
        return None

    def _get_repo_file_name(self, project: str) -> str:
        """生成 repo 文件名"""
        # home:user1 -> obs_home_user1.repo
        safe_name = project.replace(":", "_").replace("/", "_")
        return f"obs_{safe_name}.repo"

    def find_fedora_repos(
        self,
        project: str,
        current_fedora_version: int,
        max_fallback: int = 2,
    ) -> list[OBSRepo]:
        """Find Fedora repos with version fallback"""
        repos = self.get_project_repos(project)
        fedora_repos = []

        for repo in repos:
            if repo.fedora_version:
                try:
                    version = int(repo.fedora_version)
                    gap = current_fedora_version - version
                    if 0 <= gap <= max_fallback:
                        repo.is_current_version = (gap == 0)
                        repo.version_gap = gap
                        fedora_repos.append(repo)
                except ValueError:
                    continue

        # Sort by version gap, prioritize current version
        fedora_repos.sort(key=lambda r: r.version_gap)
        return fedora_repos

    def get_repo_file_url(self, project: str, repository: str) -> str:
        """Get repo file download link"""
        safe_name = project.replace(':', '_')
        return (
            f"https://download.opensuse.org/repositories/"
            f"{project}/{repository}/{safe_name}.repo"
        )

    def download_repo_file(self, project: str, repository: str) -> bool:
        """Download repo file to /etc/yum.repos.d/"""
        repo_file_name = self._get_repo_file_name(project)
        repo_file_path = OBS_REPO_DIR / repo_file_name
        repo_file_url = self.get_repo_file_url(project, repository)

        try:
            result = subprocess.run(
                [
                    "sudo", "curl", "-sSfL",
                    "-o", str(repo_file_path),
                    repo_file_url
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def disable_repo(self, project: str) -> bool:
        """Disable OBS repo"""
        repo_file_name = self._get_repo_file_name(project)
        repo_id = repo_file_name.replace(".repo", "")
        try:
            result = subprocess.run(
                [
                    "sudo", "dnf", "config-manager",
                    "--set-disabled", repo_id
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def remove_repo_file(self, project: str) -> bool:
        """Delete OBS repo file"""
        repo_file_name = self._get_repo_file_name(project)
        repo_file_path = OBS_REPO_DIR / repo_file_name

        try:
            result = subprocess.run(
                ["sudo", "rm", "-f", str(repo_file_path)],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def close(self) -> None:
        """关闭客户端"""
        self.client.close()

    def __enter__(self) -> "OBSBackend":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
