"""搜索逻辑 - 整合多个后端的搜索结果"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from copa.copr_backend import CoprBackend, CoprProject
from copa.dnf_backend import DnfBackend, Package
from copa.obs_backend import OBSBackend, OBSPackage, OBSRepo


class Source(Enum):
    """包来源"""
    FEDORA = "fedora"
    RPMFUSION = "rpmfusion"
    TERRA = "terra"
    COPR = "copr"
    OBS = "obs"


@dataclass
class SearchResult:
    """搜索结果"""
    package: Package
    source: Source
    repo: str


@dataclass
class CoprSearchResult:
    """Copr 搜索结果"""
    project: CoprProject
    risk_level: str  # low, medium, high, blocked
    supports_chroot: bool
    has_package: bool


@dataclass
class OBSSearchResult:
    """OBS 搜索结果"""
    package: OBSPackage
    repos: list[OBSRepo]
    has_current_version: bool
    best_repo: Optional[OBSRepo]
    risk_level: str  # low, medium, high


class SearchEngine:
    """搜索引擎"""

    def __init__(
        self,
        dnf: DnfBackend,
        copr: CoprBackend,
        obs: Optional[OBSBackend] = None,
    ):
        self.dnf = dnf
        self.copr = copr
        self.obs = obs or OBSBackend()

    def search_fedora(self, keyword: str) -> list[SearchResult]:
        """搜索 Fedora 官方源"""
        # TODO: 实现
        return []

    def search_rpmfusion(self, keyword: str) -> list[SearchResult]:
        """搜索 RPM Fusion"""
        # TODO: 实现
        return []

    def search_terra(self, keyword: str) -> list[SearchResult]:
        """搜索 Terra 仓库"""
        # TODO: 实现
        return []

    def search_copr(self, keyword: str, chroot: str) -> list[CoprSearchResult]:
        """搜索 Copr 仓库"""
        projects = self.copr.search_projects(keyword)
        results = []

        for project in projects:
            supports_chroot = chroot in project.chroots
            risk_level = self._assess_copr_risk(project, supports_chroot)

            results.append(CoprSearchResult(
                project=project,
                risk_level=risk_level,
                supports_chroot=supports_chroot,
                has_package=False,  # 需要进一步验证
            ))

        return results

    def _assess_copr_risk(self, project: CoprProject, supports_chroot: bool) -> str:
        """评估 Copr 风险等级"""
        desc_lower = project.description.lower()
        instructions_lower = project.instructions.lower()

        # 高风险词
        high_risk_words = ["do not use", "mock only", "testing only", "experimental"]
        for word in high_risk_words:
            if word in desc_lower or word in instructions_lower:
                return "blocked"

        # 检查是否支持当前 chroot
        if not supports_chroot:
            return "high"

        # 中等风险词
        medium_risk_words = ["testing", "experimental", "beta", "unstable"]
        for word in medium_risk_words:
            if word in desc_lower:
                return "medium"

        return "low"

    def search_obs(
        self,
        keyword: str,
        current_fedora_version: int,
        max_fallback: int = 2,
    ) -> list[OBSSearchResult]:
        """搜索 OBS 仓库"""
        packages = self.obs.search_packages(keyword)
        results = []

        for package in packages:
            repos = self.obs.find_fedora_repos(
                package.project,
                current_fedora_version,
                max_fallback,
            )

            if not repos:
                continue

            has_current_version = any(r.is_current_version for r in repos)
            best_repo = repos[0] if repos else None
            risk_level = self._assess_obs_risk(has_current_version, best_repo)

            results.append(OBSSearchResult(
                package=package,
                repos=repos,
                has_current_version=has_current_version,
                best_repo=best_repo,
                risk_level=risk_level,
            ))

        return results

    def _assess_obs_risk(
        self,
        has_current_version: bool,
        best_repo: Optional[OBSRepo],
    ) -> str:
        """评估 OBS 风险等级"""
        if has_current_version:
            return "low"

        if best_repo and best_repo.version_gap == 1:
            return "medium"

        if best_repo and best_repo.version_gap == 2:
            return "high"

        return "high"

    def search_all(
        self,
        keyword: str,
        current_fedora_version: int,
        official_only: bool = False,
        rpmfusion_only: bool = False,
        copr_only: bool = False,
        obs_only: bool = False,
        no_obs: bool = False,
        max_obs_fallback: int = 2,
    ) -> tuple[list[SearchResult], list[CoprSearchResult], list[OBSSearchResult]]:
        """搜索所有来源"""
        fedora_results = []
        rpmfusion_results = []
        terra_results = []
        copr_results = []
        obs_results = []

        if obs_only:
            obs_results = self.search_obs(keyword, current_fedora_version, max_obs_fallback)
            return [], [], obs_results

        if not copr_only:
            fedora_results = self.search_fedora(keyword)
            if not official_only:
                rpmfusion_results = self.search_rpmfusion(keyword)
                terra_results = self.search_terra(keyword)

        if not official_only and not rpmfusion_only:
            chroot = self.dnf.get_chroot()
            copr_results = self.search_copr(keyword, chroot)

        if not no_obs and not official_only and not rpmfusion_only and not copr_only:
            obs_results = self.search_obs(keyword, current_fedora_version, max_obs_fallback)

        all_results = fedora_results + rpmfusion_results + terra_results
        return all_results, copr_results, obs_results
