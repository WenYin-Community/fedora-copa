"""Search logic - integrate search results from multiple backends"""

from dataclasses import dataclass

from copa.config import RiskConfig
from copa.copr_backend import CoprBackend, CoprProject
from copa.dnf_backend import DnfBackend
from copa.obs_backend import OBSBackend, OBSPackage, OBSRepo, extract_fedora_version

# Risk keywords, shared with the audit command.
# Words that always block a project regardless of configuration.
BLOCK_WORD_TESTING_ONLY = "testing only"
# Words whose blocking is controlled by RiskConfig.
BLOCK_WORDS = ("do not use", "mock only")
# Words that raise risk to medium when RiskConfig.warn_experimental is on.
MEDIUM_WORDS = ("testing", "experimental", "beta", "unstable")


@dataclass
class CoprSearchResult:
    """Copr search result"""
    project: CoprProject
    risk_level: str  # low, medium, high, blocked
    supports_chroot: bool
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
        risk: RiskConfig | None = None,
    ):
        self.dnf = dnf
        self.copr = copr
        self.obs = obs or OBSBackend()
        self.risk = risk or RiskConfig()

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
            version = extract_fedora_version(c)
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

        def matches_all_keywords(text: str) -> bool:
            return all(kw in text for kw in keywords)

        for project in projects:
            # Filter: project name or owner must contain all keywords
            project_name_lower = project.name.lower()
            owner_lower = project.owner.lower()

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

        # High-risk words, blocking controlled by RiskConfig
        if self.risk.block_do_not_use and "do not use" in (desc_lower + instructions_lower):
            return "blocked"
        if self.risk.block_mock_only and "mock only" in (desc_lower + instructions_lower):
            return "blocked"
        if BLOCK_WORD_TESTING_ONLY in (desc_lower + instructions_lower):
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

        # Medium-risk words (warn only, controlled by RiskConfig)
        if self.risk.warn_experimental and any(
            word in desc_lower for word in MEDIUM_WORDS
        ):
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
