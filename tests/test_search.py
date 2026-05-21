"""search module tests"""

from copa.dnf_backend import Package
from copa.search import SearchEngine, Source


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


def test_search_all_skips_local_repos_by_default():
    dnf = FakeDnf()
    engine = SearchEngine(dnf=dnf, copr=FakeCopr(), obs=FakeObs())

    local_results, copr_results, obs_results = engine.search_all("vim", 44, no_obs=True)

    assert local_results == []
    assert copr_results == []
    assert obs_results == []
    assert dnf.search_calls == []


def test_search_all_includes_local_repos_when_requested():
    dnf = FakeDnf()
    engine = SearchEngine(dnf=dnf, copr=FakeCopr(), obs=FakeObs())

    local_results, _, _ = engine.search_all(
        "vim",
        44,
        include_local_repo=True,
        no_obs=True,
    )

    assert [result.source for result in local_results] == [
        Source.FEDORA,
        Source.RPMFUSION,
        Source.TERRA,
    ]
    assert dnf.search_calls == [
        ("vim", ["fedora"]),
        ("vim", ["rpmfusion-free"]),
        ("vim", ["terra"]),
    ]
