"""Search logic - integrate search results from multiple backends"""

from dataclasses import dataclass
from enum import Enum

from copa.copr_backend import CoprBackend, CoprProject
from copa.dnf_backend import DnfBackend, Package
from copa.obs_backend import OBSBackend, OBSPackage, OBSRepo


class Source(Enum):
    """Package source"""
    FEDORA = "fedora"
    RPMFUSION = "rpmfusion"
    TERRA = "terra"
    COPR = "copr"
    OBS = "obs"


@dataclass
class SearchResult:
    """Search result"""
    package: Package
    source: Source
    repo: str


@dataclass
class CoprSearchResult:
    """Copr search result"""
    project: CoprProject
    risk_level: str  # low, medium, high, blocked
    supports_chroot: bool
    has_package: bool
    best_chroot: str | None = None  # Best matching chroot (with fallback)
    version_gap: int = 0  # Version gap, 0 = exact match


@dataclass
class OBSSearchResult:
    """OBS search result"""
    package: OBSPackage
    repos: list[OBSRepo]
    has_current_version: bool
    best_repo: OBSRepo | None
    risk_level: str  # low, medium, high


class SearchEngine:
    """Search engine"""

    def __init__(
        self,
        dnf: DnfBackend,
        copr: CoprBackend,
        obs: OBSBackend | None = None,
    ):
        self.dnf = dnf
        self.copr = copr
        self.obs = obs or OBSBackend()

    def _search_dnf_group(self, keyword: str, group: str, source: Source) -> list[SearchResult]:
        repo_ids = self.dnf.get_enabled_repos().get(group, [])
        return [
            SearchResult(package=package, source=source, repo=package.repo)
            for package in self.dnf.search_in_repos(keyword, repo_ids)
        ]

    def search_fedora(self, keyword: str) -> list[SearchResult]:
        """Search Fedora official repos"""
        return self._search_dnf_group(keyword, "fedora", Source.FEDORA)

    def search_rpmfusion(self, keyword: str) -> list[SearchResult]:
        """Search RPM Fusion"""
        return self._search_dnf_group(keyword, "rpmfusion", Source.RPMFUSION)

    def search_terra(self, keyword: str) -> list[SearchResult]:
        """Search Terra repos"""
        return self._search_dnf_group(keyword, "terra", Source.TERRA)

    def _find_best_copr_chroot(
        self,
        chroots: list[str],
        current_chroot: str,
        current_fedora_version: int,
        max_fallback: int = 2,
    ) -> tuple[str | None, int]:
        """Find best matching chroot from list, with version fallback

        Returns:
            (best_chroot, version_gap) - returns (None, -1) if not found
        """
        # Exact match
        if current_chroot in chroots:
            return current_chroot, 0

        # Try fallback match
        best = None
        best_gap = -1
        for c in chroots:
            version = self.obs._extract_fedora_version(c)
            if not version:
                continue
            try:
                v = int(version)
                gap = current_fedora_version - v
                if 0 < gap <= max_fallback and (best is None or gap < best_gap):
                    best = c
                    best_gap = gap
            except ValueError:
                continue

        return best, best_gap

    def search_copr(
        self,
        keyword: str,
        chroot: str,
        current_fedora_version: int = 0,
        max_fallback: int = 2,
    ) -> list[CoprSearchResult]:
        """Search Copr repos - substring match on project name or owner"""
        projects = self.copr.search_projects(keyword)
        results = []
        # Support multi-keyword AND logic
        keywords = keyword.lower().split()

        for project in projects:
            # Filter: project name or owner must contain all keywords
            project_name_lower = project.name.lower()
            owner_lower = project.owner.lower()

            def matches_all_keywords(text: str) -> bool:
                return all(kw in text for kw in keywords)

            name_match = matches_all_keywords(project_name_lower)
            owner_match = matches_all_keywords(owner_lower)

            if not name_match and not owner_match:
                continue

            # Find best chroot (with fallback)
            best_chroot, version_gap = self._find_best_copr_chroot(
                project.chroots, chroot, current_fedora_version, max_fallback,
            )
            supports_chroot = version_gap == 0
            risk_level = self._assess_copr_risk(project, supports_chroot, version_gap)

            results.append(CoprSearchResult(
                project=project,
                risk_level=risk_level,
                supports_chroot=supports_chroot,
                has_package=name_match,
                best_chroot=best_chroot,
                version_gap=version_gap,
            ))

        return results

    def _assess_copr_risk(
        self,
        project: CoprProject,
        supports_chroot: bool,
        version_gap: int = 0,
    ) -> str:
        """Assess Copr risk level"""
        desc_lower = project.description.lower()
        instructions_lower = project.instructions.lower()

        # High-risk words
        high_risk_words = ["do not use", "mock only", "testing only", "experimental"]
        for word in high_risk_words:
            if word in desc_lower or word in instructions_lower:
                return "blocked"

        # No usable chroot at all
        if version_gap < 0:
            return "blocked"

        # Fallback 2 versions
        if version_gap >= 2:
            return "high"

        # Fallback 1 version
        if version_gap == 1:
            return "medium"

        # Medium-risk words
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
        """Search OBS repos - substring match on package name or project name"""
        packages = self.obs.search_packages(keyword)
        results = []
        keyword_lower = keyword.lower()

        for package in packages:
            # Filter: package name or project name must contain keyword
            name_match = keyword_lower in package.name.lower()
            project_match = keyword_lower in package.project.lower()

            if not name_match and not project_match:
                continue

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
        best_repo: OBSRepo | None,
    ) -> str:
        """Assess OBS risk level"""
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
        include_local_repo: bool = False,
        max_obs_fallback: int = 2,
    ) -> tuple[list[SearchResult], list[CoprSearchResult], list[OBSSearchResult]]:
        """Search all sources"""
        fedora_results = []
        rpmfusion_results = []
        terra_results = []
        copr_results = []
        obs_results = []

        if obs_only:
            obs_results = self.search_obs(keyword, current_fedora_version, max_obs_fallback)
            return [], [], obs_results

        search_local = include_local_repo or official_only or rpmfusion_only
        if search_local and not copr_only and not rpmfusion_only:
            fedora_results = self.search_fedora(keyword)
        if search_local and not official_only and not copr_only:
            rpmfusion_results = self.search_rpmfusion(keyword)
        if include_local_repo and not official_only and not rpmfusion_only and not copr_only:
            terra_results = self.search_terra(keyword)

        if not official_only and not rpmfusion_only:
            chroot = self.dnf.get_chroot()
            copr_results = self.search_copr(keyword, chroot, current_fedora_version)

        if not no_obs and not official_only and not rpmfusion_only and not copr_only:
            obs_results = self.search_obs(keyword, current_fedora_version, max_obs_fallback)

        all_results = fedora_results + rpmfusion_results + terra_results
        return all_results, copr_results, obs_results
