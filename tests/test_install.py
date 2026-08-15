"""Install flow tests for _install_from_copr / _install_from_obs"""

from types import SimpleNamespace

from copa.cli import _install_from_copr, _install_from_obs
from copa.config import Config
from copa.dnf_backend import Package


class MockDnf:
    """DnfBackend stand-in recording calls."""

    def __init__(self, install_ok=True, enable_ok=True, search_results=None):
        self.install_ok = install_ok
        self.enable_ok = enable_ok
        self.search_results = search_results
        self.calls = []
        self.binary = "dnf5"

    def get_fedora_version(self):
        return 44

    def copr_enable(self, owner_project, chroot=None):
        self.calls.append(("copr_enable", owner_project, chroot))
        return self.enable_ok

    def makecache(self, repo=None):
        self.calls.append(("makecache", repo))
        return True

    def search(self, package, repo=None):
        self.calls.append(("search", package, repo))
        if self.search_results is not None:
            return self.search_results
        return [Package(name=package, version="1", release="1", arch="x86_64",
                        summary="", repo=repo or "", evr="0:1-1")]

    def install(self, package, repo=None):
        self.calls.append(("install", package, repo))
        return self.install_ok

    def copr_remove(self, owner_project):
        self.calls.append(("copr_remove", owner_project))
        return True

    def copr_disable(self, owner_project):
        self.calls.append(("copr_disable", owner_project))
        return True


class MockObs:
    """OBSBackend stand-in recording calls."""

    def __init__(self, download_ok=True):
        self.download_ok = download_ok
        self.calls = []

    def download_repo_file(self, project, repository):
        self.calls.append(("download_repo_file", project, repository))
        return self.download_ok

    def _get_repo_file_name(self, project):
        return f"{project}.repo"

    def disable_repo(self, project):
        self.calls.append(("disable_repo", project))
        return True


class MockState:
    """AppState stand-in recording calls."""

    def __init__(self):
        self.calls = []

    def add_copr_repo(self, **kwargs):
        self.calls.append(("add_copr_repo", kwargs))

    def add_obs_repo(self, **kwargs):
        self.calls.append(("add_obs_repo", kwargs))

    def save(self):
        self.calls.append(("save",))

    def remove_copr_repo(self, owner, project):
        self.calls.append(("remove_copr_repo", owner, project))

    def remove_obs_repo(self, project):
        self.calls.append(("remove_obs_repo", project))


def make_args(**overrides):
    base = dict(
        dry_run=False,
        assumeyes=True,
        keep_copr=True,
        allow_obs_fallback=True,
        config=Config(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def make_copr_selected(version_gap=0, best_chroot=None, owner="user1", name="ghostty"):
    project = SimpleNamespace(owner=owner, name=name, description="", chroots=[], instructions="")
    return SimpleNamespace(
        project=project,
        best_chroot=best_chroot,
        version_gap=version_gap,
        risk_level="low",
        supports_chroot=True,
    )


def make_obs_selected(repo_fedora="44", has_current=True, best_repo=True):
    repo = (
        SimpleNamespace(repository="Fedora_44", fedora_version=repo_fedora)
        if best_repo
        else None
    )
    return SimpleNamespace(
        has_current_version=has_current,
        best_repo=repo,
        package=SimpleNamespace(name="ghostty", project="home:user1"),
    )


class TestInstallFromCopr:
    def test_success(self):
        dnf = MockDnf()
        state = MockState()
        args = make_args(keep_copr=True)
        rc = _install_from_copr(args, dnf, state, None, "ghostty",
                                make_copr_selected(), "fedora-44-x86_64")
        assert rc == 0
        assert ("copr_enable", "user1/ghostty", "fedora-44-x86_64") in dnf.calls
        assert ("search", "ghostty", "copr:copr.fedorainfracloud.org:user1:ghostty") in dnf.calls
        assert ("install", "ghostty", None) in dnf.calls
        assert any(c[0] == "add_copr_repo" for c in state.calls)
        assert ("save",) in state.calls

    def test_enable_failure_aborts(self):
        dnf = MockDnf(enable_ok=False)
        state = MockState()
        args = make_args()
        rc = _install_from_copr(args, dnf, state, None, "ghostty",
                                make_copr_selected(), "fedora-44-x86_64")
        assert rc == 1
        assert not any(c[0] == "install" for c in dnf.calls)

    def test_no_matching_package_aborts(self):
        dnf = MockDnf(search_results=[])
        state = MockState()
        args = make_args()
        rc = _install_from_copr(args, dnf, state, None, "ghostty",
                                make_copr_selected(), "fedora-44-x86_64")
        assert rc == 1
        assert not any(c[0] == "install" for c in dnf.calls)

    def test_install_failure_returns_one(self):
        dnf = MockDnf(install_ok=False)
        state = MockState()
        args = make_args()
        rc = _install_from_copr(args, dnf, state, None, "ghostty",
                                make_copr_selected(), "fedora-44-x86_64")
        assert rc == 1
        assert not any(c[0] == "add_copr_repo" for c in state.calls)

    def test_version_fallback_uses_fallback_chroot(self):
        dnf = MockDnf()
        state = MockState()
        args = make_args(keep_copr=True)
        rc = _install_from_copr(args, dnf, state, None, "ghostty",
                                make_copr_selected(version_gap=1, best_chroot="fedora-43-x86_64"),
                                "fedora-44-x86_64")
        assert rc == 0
        assert ("copr_enable", "user1/ghostty", "fedora-43-x86_64") in dnf.calls

    def test_post_action_remove(self):
        cfg = Config()
        cfg.install.default_copr_post_action = "remove"
        dnf = MockDnf()
        state = MockState()
        args = make_args(config=cfg, keep_copr=False)
        rc = _install_from_copr(args, dnf, state, None, "ghostty",
                                make_copr_selected(), "fedora-44-x86_64")
        assert rc == 0
        assert ("copr_remove", "user1/ghostty") in dnf.calls
        assert ("remove_copr_repo", "user1", "ghostty") in state.calls


class TestInstallFromObs:
    def test_success(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a: "n")
        dnf = MockDnf()
        obs = MockObs()
        state = MockState()
        args = make_args()
        rc = _install_from_obs(args, dnf, obs, state, "ghostty",
                               make_obs_selected(), 44)
        assert rc == 0
        assert ("download_repo_file", "home:user1", "Fedora_44") in obs.calls
        assert any(c[0] == "add_obs_repo" for c in state.calls)
        assert ("save",) in state.calls

    def test_download_failure_aborts(self):
        dnf = MockDnf()
        obs = MockObs(download_ok=False)
        state = MockState()
        args = make_args()
        rc = _install_from_obs(args, dnf, obs, state, "ghostty",
                               make_obs_selected(), 44)
        assert rc == 1
        assert not any(c[0] == "install" for c in dnf.calls)

    def test_no_best_repo_is_noop(self):
        dnf = MockDnf()
        obs = MockObs()
        state = MockState()
        args = make_args()
        rc = _install_from_obs(args, dnf, obs, state, "ghostty",
                               make_obs_selected(best_repo=False), 44)
        assert rc == 0
        assert not obs.calls

    def test_version_fallback_declined(self, monkeypatch):
        monkeypatch.setattr("copa.utils.confirm", lambda *a, **kw: False)
        dnf = MockDnf()
        obs = MockObs()
        state = MockState()
        args = make_args(allow_obs_fallback=False)
        rc = _install_from_obs(args, dnf, obs, state, "ghostty",
                               make_obs_selected(repo_fedora="43", has_current=False), 44)
        assert rc == 0
        assert not obs.calls
