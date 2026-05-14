"""Copr 后端 - 处理与 Copr API 和 copr-cli 的交互"""

from dataclasses import dataclass
from typing import Optional

from copr.v3 import Client
from copr.v3.exceptions import CoprNoResultException


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
    latest_version: Optional[str]
    latest_build_succeeded: bool


@dataclass
class CoprBuild:
    """Copr 构建信息"""
    id: int
    state: str
    chroot: str
    started_on: Optional[int]
    ended_on: Optional[int]


class CoprBackend:
    """Copr 后端封装"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            # TODO: 从指定配置文件加载
            self.client = Client.create_from_config_file()
        else:
            self.client = Client.create_from_config_file()

    def search_projects(self, query: str, limit: int = 20) -> list[CoprProject]:
        """搜索 Copr 项目"""
        try:
            projects = self.client.project_proxy.search(query)
            result = []
            for project in projects[:limit]:
                result.append(CoprProject(
                    owner=project.ownername,
                    name=project.name,
                    description=project.description or "",
                    chroots=list(project.chroot_repos.keys()) if hasattr(project, 'chroot_repos') else [],
                    instructions=project.instructions or "",
                ))
            return result
        except Exception:
            return []

    def get_project(self, owner: str, name: str) -> Optional[CoprProject]:
        """获取项目详情"""
        try:
            project = self.client.project_proxy.get(owner, name)
            return CoprProject(
                owner=project.ownername,
                name=project.name,
                description=project.description or "",
                chroots=list(project.chroot_repos.keys()) if hasattr(project, 'chroot_repos') else [],
                instructions=project.instructions or "",
            )
        except CoprNoResultException:
            return None

    def list_packages(self, owner: str, project: str) -> list[CoprPackage]:
        """列出项目中的包"""
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
        package: Optional[str] = None,
        limit: int = 10
    ) -> list[CoprBuild]:
        """获取构建列表"""
        try:
            kwargs = {"limit": limit}
            if package:
                kwargs["packagename"] = package
            builds = self.client.build_proxy.get_list(owner, project, **kwargs)
            result = []
            for build in builds:
                result.append(CoprBuild(
                    id=build.id,
                    state=build.state,
                    chroot=build.chroot if hasattr(build, 'chroot') else "",
                    started_on=build.started_on if hasattr(build, 'started_on') else None,
                    ended_on=build.ended_on if hasattr(build, 'ended_on') else None,
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
        """检查包是否存在于项目中"""
        try:
            self.client.package_proxy.get(owner, project, package_name)
            return True
        except CoprNoResultException:
            return False
        except Exception:
            return False
