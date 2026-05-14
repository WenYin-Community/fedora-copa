"""OBS 后端 - 处理与 openSUSE Build Service 的交互"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import httpx

OBS_API_BASE = "https://api.opensuse.org"


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
    fedora_version: Optional[str]
    is_current_version: bool
    version_gap: int  # 与当前版本的差距


class OBSBackend:
    """OBS 后端封装"""

    def __init__(self, api_base: str = OBS_API_BASE):
        self.api_base = api_base
        self.client = httpx.Client(
            headers={"Accept": "application/xml; charset=utf-8"},
            timeout=30.0,
        )

    def _get(self, path: str, params: Optional[dict] = None) -> ET.Element:
        """发送 GET 请求"""
        url = f"{self.api_base}{path}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return ET.fromstring(response.text)

    def search_projects(self, query: str, limit: int = 20) -> list[OBSProject]:
        """搜索项目"""
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
        """搜索包"""
        try:
            root = self._get("/search/package", {"match": f"@name='{query}'"})
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
        repository: Optional[str] = None,
        limit: int = 20,
    ) -> list[OBSBinary]:
        """搜索二进制包"""
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
        """获取项目的仓库列表"""
        try:
            root = self._get(f"/source/{project}/_meta")
            repos = []
            for repo_elem in root.findall(".//repository"):
                repo_name = repo_elem.get("name", "")
                # 尝试从仓库名中提取 Fedora 版本
                fedora_version = self._extract_fedora_version(repo_name)
                repo_url = f"https://download.opensuse.org/repositories/{project}/{repo_name}"

                repos.append(OBSRepo(
                    project=project,
                    repository=repo_name,
                    repo_url=repo_url,
                    fedora_version=fedora_version,
                    is_current_version=False,  # 需要外部判断
                    version_gap=0,  # 需要外部计算
                ))
            return repos
        except Exception:
            return []

    def _extract_fedora_version(self, repo_name: str) -> Optional[str]:
        """从仓库名中提取 Fedora 版本"""
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

    def find_fedora_repos(
        self,
        project: str,
        current_fedora_version: int,
        max_fallback: int = 2,
    ) -> list[OBSRepo]:
        """查找 Fedora 仓库，支持版本 fallback"""
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

        # 按版本差距排序，优先使用当前版本
        fedora_repos.sort(key=lambda r: r.version_gap)
        return fedora_repos

    def get_repo_file_url(self, project: str, repository: str) -> str:
        """获取 repo 文件下载链接"""
        return f"https://download.opensuse.org/repositories/{project}/{repository}/{project.replace(':', '_')}.repo"

    def close(self) -> None:
        """关闭客户端"""
        self.client.close()

    def __enter__(self) -> "OBSBackend":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
