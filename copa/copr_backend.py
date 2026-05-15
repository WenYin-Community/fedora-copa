"""Copr backend - handles interaction with Copr API and copr-cli"""

from dataclasses import dataclass

import requests
from copr.v3 import Client
from copr.v3.exceptions import CoprNoResultException

from copa.utils import retry


@dataclass
class CoprProject:
    """Copr 项目信息"""
    owner: str
    name: str
    description: str
    chroots: list[str]
    instructions: str


@dataclass
class CoprPackage:
    """Copr 包信息"""
    name: str
    source_name: str
    latest_version: str | None
    latest_build_succeeded: bool


@dataclass
class CoprBuild:
    """Copr 构建信息"""
    id: int
    state: str
    chroot: str
    started_on: int | None
    ended_on: int | None


class CoprBackend:
    """Copr 后端封装"""

    def __init__(self, config_path: str | None = None):
        if config_path:
            # TODO: 从指定配置文件加载
            self.client = Client.create_from_config_file()
        else:
            self.client = Client.create_from_config_file()

    @retry(max_attempts=3, delay=1.0,
           exceptions=(requests.ConnectionError, requests.Timeout, OSError))
    def search_projects(self, query: str, limit: int = 20) -> list[CoprProject]:
        """Search Copr projects"""
        try:
            projects = self.client.project_proxy.search(query)
            result = []
            for project in projects[:limit]:
                chroots = (
                    list(project.chroot_repos.keys())
                    if hasattr(project, 'chroot_repos')
                    else []
                )
                result.append(CoprProject(
                    owner=project.ownername,
                    name=project.name,
                    description=project.description or "",
                    chroots=chroots,
                    instructions=project.instructions or "",
                ))
            return result
        except Exception:
            return []

    @retry(max_attempts=3, delay=1.0,
           exceptions=(requests.ConnectionError, requests.Timeout, OSError))
    def get_project(self, owner: str, name: str) -> CoprProject | None:
        """Get project details"""
        try:
            project = self.client.project_proxy.get(owner, name)
            chroots = (
                list(project.chroot_repos.keys())
                if hasattr(project, 'chroot_repos')
                else []
            )
            return CoprProject(
                owner=project.ownername,
                name=project.name,
                description=project.description or "",
                chroots=chroots,
                instructions=project.instructions or "",
            )
        except CoprNoResultException:
            return None

    def list_packages(self, owner: str, project: str) -> list[CoprPackage]:
        """List packages in project"""
        try:
            packages = self.client.package_proxy.get_list(owner, project)
            result = []
            for pkg in packages:
                result.append(CoprPackage(
                    name=pkg.name,
                    source_name=pkg.name,  # 通常是源码包名
                    latest_version=None,  # 需要额外查询
                    latest_build_succeeded=False,  # 需要额外查询
                ))
            return result
        except Exception:
            return []

    def get_builds(
        self,
        owner: str,
        project: str,
        package: str | None = None,
        limit: int = 10
    ) -> list[CoprBuild]:
        """Get build list"""
        try:
            kwargs: dict[str, str | int] = {"limit": limit}
            if package:
                kwargs["packagename"] = package
            builds = self.client.build_proxy.get_list(
                owner, project, **kwargs
            )
            result: list[CoprBuild] = []
            for build in builds:
                result.append(CoprBuild(
                    id=build.id,
                    state=build.state,
                    chroot=(
                        build.chroot
                        if hasattr(build, 'chroot')
                        else ""
                    ),
                    started_on=(
                        build.started_on
                        if hasattr(build, 'started_on')
                        else None
                    ),
                    ended_on=(
                        build.ended_on
                        if hasattr(build, 'ended_on')
                        else None
                    ),
                ))
            return result
        except Exception:
            return []

    def check_package_exists(
        self,
        owner: str,
        project: str,
        package_name: str
    ) -> bool:
        """Check if package exists in project"""
        try:
            self.client.package_proxy.get(owner, project, package_name)
            return True
        except CoprNoResultException:
            return False
        except Exception:
            return False
