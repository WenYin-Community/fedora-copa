"""search module tests"""

from copa.config import RiskConfig
from copa.copr_backend import CoprProject
from copa.dnf_backend import Package
from copa.obs_backend import OBSPackage, OBSRepo
from copa.search import SearchEngine


class FakeDnf:
    """Mock DNF backend"""

    def __init__(self):
        self.search_calls = []

    def get_enabled_repos(self):
        return {
            "fedora": ["fedora"],
            "rpmfusion": ["rpmfusion-free"],
            "terra": ["terra"],
        }

    def search_in_repos(self, keyword, repo_ids):
        self.search_calls.append((keyword, repo_ids))
        return [
            Package(
                name=keyword,
                version="1",
                release="1",
                arch="x86_64",
                summary="",
                repo=repo_ids[0],
                evr="0:1-1",
            )
        ]

    def get_chroot(self):
        return "fedora-44-x86_64"


class FakeCopr:
    """Mock Copr backend"""

    def search_projects(self, query):
        return []


class FakeObs:
    """Mock OBS backend"""

    def search_packages(self, query):
        return []


def make_engine(copr=None, obs=None, risk=None):
    """Build a SearchEngine with the shared fakes."""
    return SearchEngine(
        dnf=FakeDnf(), copr=copr or FakeCopr(), obs=obs or FakeObs(), risk=risk
    )


class FakeCoprProjects:
    """Copr backend returning a fixed project list."""

    def __init__(self, projects):
        self._projects = projects

    def search_projects(self, query):
        return self._projects


class FakeObsPackages:
    """OBS backend returning a fixed package list."""

    def __init__(self, packages, repos=None):
        self._packages = packages
        self._repos = repos

    def search_packages(self, query):
        return self._packages

    def find_fedora_repos(self, project, current_fedora_version, max_fallback=2):
        return self._repos or []


class TestFindBestCoprChroot:
    """_find_best_copr_chroot version fallback logic"""

    def test_exact_match(self):
        best, gap = make_engine()._find_best_copr_chroot(
            ["fedora-44-x86_64", "fedora-43-x86_64"], "fedora-44-x86_64", 44)
        assert best == "fedora-44-x86_64"
        assert gap == 0

    def test_fallback_one(self):
        best, gap = make_engine()._find_best_copr_chroot(
            ["fedora-43-x86_64"], "fedora-44-x86_64", 44)
        assert best == "fedora-43-x86_64"
        assert gap == 1

    def test_fallback_two(self):
        best, gap = make_engine()._find_best_copr_chroot(
            ["fedora-42-x86_64"], "fedora-44-x86_64", 44)
        assert best == "fedora-42-x86_64"
        assert gap == 2

    def test_fallback_three_rejected(self):
        best, gap = make_engine()._find_best_copr_chroot(
            ["fedora-41-x86_64"], "fedora-44-x86_64", 44)
        assert best is None
        assert gap == -1

    def test_no_fedora_chroot_returns_none(self):
        best, gap = make_engine()._find_best_copr_chroot(
            ["epel-9-x86_64"], "fedora-44-x86_64", 44)
        assert best is None
        assert gap == -1

    def test_prefers_smallest_gap(self):
        best, gap = make_engine()._find_best_copr_chroot(
            ["fedora-42-x86_64", "fedora-43-x86_64"], "fedora-44-x86_64", 44)
        assert best == "fedora-43-x86_64"
        assert gap == 1


class TestAssessCoprRisk:
    """_assess_copr_risk risk levels"""

    def _project(self, description="", instructions=""):
        return CoprProject("o", "n", description, [], instructions)

    def test_blocked_do_not_use(self):
        p = self._project(description="Do not use in production")
        assert make_engine()._assess_copr_risk(p, True, 0) == "blocked"

    def test_blocked_instructions(self):
        p = self._project(instructions="mock only")
        assert make_engine()._assess_copr_risk(p, True, 0) == "blocked"

    def test_blocked_no_chroot(self):
        p = self._project()
        assert make_engine()._assess_copr_risk(p, False, -1) == "blocked"

    def test_high_gap_two(self):
        p = self._project()
        assert make_engine()._assess_copr_risk(p, False, 2) == "high"

    def test_medium_gap_one(self):
        p = self._project()
        assert make_engine()._assess_copr_risk(p, False, 1) == "medium"

    def test_medium_testing_word(self):
        p = self._project(description="Testing build for nightly")
        assert make_engine()._assess_copr_risk(p, True, 0) == "medium"

    def test_experimental_warns_not_blocks(self):
        p = self._project(description="Experimental package, use at your own risk")
        assert make_engine()._assess_copr_risk(p, True, 0) == "medium"

    def test_block_do_not_use_disabled_by_config(self):
        p = self._project(description="Do not use in production")
        engine = make_engine(risk=RiskConfig(block_do_not_use=False))
        assert engine._assess_copr_risk(p, True, 0) == "low"

    def test_block_mock_only_disabled_by_config(self):
        p = self._project(instructions="mock only")
        engine = make_engine(risk=RiskConfig(block_mock_only=False))
        assert engine._assess_copr_risk(p, True, 0) == "low"

    def test_warn_experimental_disabled(self):
        p = self._project(description="Experimental package")
        engine = make_engine(risk=RiskConfig(warn_experimental=False))
        assert engine._assess_copr_risk(p, True, 0) == "low"

    def test_low(self):
        p = self._project(description="Stable production package")
        assert make_engine()._assess_copr_risk(p, True, 0) == "low"


class TestAssessObsRisk:
    """_assess_obs_risk risk levels"""

    def _repo(self, gap):
        return OBSRepo("p", "r", "u", "43", False, gap)

    def test_current_version_low(self):
        assert make_engine()._assess_obs_risk(True, None) == "low"

    def test_gap_one_medium(self):
        assert make_engine()._assess_obs_risk(False, self._repo(1)) == "medium"

    def test_gap_two_high(self):
        assert make_engine()._assess_obs_risk(False, self._repo(2)) == "high"

    def test_no_repo_high(self):
        assert make_engine()._assess_obs_risk(False, None) == "high"


class TestSearchCopr:
    """search_copr filtering"""

    def test_matches_name_or_owner(self):
        projects = [
            CoprProject("user1", "ghostty", "Terminal", ["fedora-44-x86_64"], ""),
            CoprProject("ghostty", "helper", "Tool", ["fedora-44-x86_64"], ""),
            CoprProject("user2", "htop", "Viewer", ["fedora-44-x86_64"], ""),
        ]
        engine = make_engine(copr=FakeCoprProjects(projects))
        results = engine.search_copr("ghostty", "fedora-44-x86_64", 44)
        assert len(results) == 2
        pairs = {(r.project.owner, r.project.name) for r in results}
        assert ("user1", "ghostty") in pairs
        assert ("ghostty", "helper") in pairs
        assert all(r.supports_chroot for r in results)
        assert all(r.risk_level == "low" for r in results)

    def test_multi_keyword_and_on_same_field(self):
        projects = [
            CoprProject("u", "ghostty-terminal", "T", ["fedora-44-x86_64"], ""),
            CoprProject("u", "ghostty", "T", ["fedora-44-x86_64"], ""),
        ]
        engine = make_engine(copr=FakeCoprProjects(projects))
        results = engine.search_copr("ghostty terminal", "fedora-44-x86_64", 44)
        assert len(results) == 1
        assert results[0].project.name == "ghostty-terminal"

    def test_version_fallback_flagged(self):
        projects = [
            CoprProject("u", "pkg", "P", ["fedora-43-x86_64"], ""),
        ]
        engine = make_engine(copr=FakeCoprProjects(projects))
        results = engine.search_copr("pkg", "fedora-44-x86_64", 44)
        assert len(results) == 1
        assert results[0].best_chroot == "fedora-43-x86_64"
        assert results[0].version_gap == 1
        assert results[0].risk_level == "medium"
        assert results[0].supports_chroot is False


class TestSearchObs:
    """search_obs filtering"""

    def test_matches_package_name(self):
        packages = [
            OBSPackage("ghostty", "home:user1", "T", "D"),
            OBSPackage("htop", "home:user2", "T", "D"),
        ]
        repos = [OBSRepo("home:user1", "Fedora_44", "u", "44", True, 0)]
        engine = make_engine(obs=FakeObsPackages(packages, repos))
        results = engine.search_obs("ghostty", 44)
        assert len(results) == 1
        assert results[0].package.project == "home:user1"
        assert results[0].has_current_version is True
        assert results[0].risk_level == "low"

    def test_fallback_flagged(self):
        packages = [OBSPackage("ghostty", "home:user1", "T", "D")]
        repos = [OBSRepo("home:user1", "Fedora_43", "u", "43", False, 1)]
        engine = make_engine(obs=FakeObsPackages(packages, repos))
        results = engine.search_obs("ghostty", 44)
        assert len(results) == 1
        assert results[0].has_current_version is False
        assert results[0].risk_level == "medium"

    def test_skipped_when_no_fedora_repo(self):
        packages = [OBSPackage("ghostty", "home:user1", "T", "D")]
        engine = make_engine(obs=FakeObsPackages(packages, repos=[]))
        results = engine.search_obs("ghostty", 44)
        assert results == []
