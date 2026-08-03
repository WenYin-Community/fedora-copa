"""Copr backend tests"""

from types import SimpleNamespace

from copr.v3.exceptions import (
    CoprAuthException,
    CoprNoResultException,
    CoprRequestException,
)

from copa.copr_backend import CoprBackend


class _Proxy:
    """Configurable stand-in for a copr.v3 proxy object."""

    def __init__(self, exc=None, result=None):
        self._exc = exc
        self._result = result

    def search(self, *args, **kwargs):
        if self._exc:
            raise self._exc
        return self._result or []

    def get(self, *args, **kwargs):
        if self._exc:
            raise self._exc
        return self._result

    def get_list(self, *args, **kwargs):
        if self._exc:
            raise self._exc
        return self._result or []


class _Client:
    """Minimal copr.v3.Client stand-in."""

    def __init__(self, exc=None, result=None):
        self.project_proxy = _Proxy(exc=exc, result=result)
        self.package_proxy = _Proxy(exc=exc, result=result)
        self.build_proxy = _Proxy(exc=exc, result=result)


def make_backend(exc=None, result=None):
    """Build a CoprBackend with a mocked client (bypasses __init__ config load)."""
    backend = CoprBackend.__new__(CoprBackend)
    backend.client = _Client(exc=exc, result=result)
    return backend


def make_project(name="pkg", owner="user1"):
    return SimpleNamespace(
        name=name,
        ownername=owner,
        description="a description",
        instructions="some instructions",
        chroot_repos={"fedora-44-x86_64": 1},
    )


class TestSearchProjects:
    def test_success(self):
        backend = make_backend(result=[make_project()])
        projects = backend.search_projects("query")
        assert len(projects) == 1
        assert projects[0].name == "pkg"
        assert projects[0].owner == "user1"
        assert projects[0].chroots == ["fedora-44-x86_64"]

    def test_project_without_chroots(self):
        project = make_project()
        delattr(project, "chroot_repos")
        backend = make_backend(result=[project])
        projects = backend.search_projects("query")
        assert projects[0].chroots == []

    def test_not_found_is_silent(self, capsys):
        backend = make_backend(exc=CoprNoResultException("not found"))
        assert backend.search_projects("query") == []
        assert capsys.readouterr().err == ""

    def test_auth_error_is_silent(self, capsys):
        backend = make_backend(exc=CoprAuthException("forbidden"))
        assert backend.search_projects("query") == []
        assert capsys.readouterr().err == ""

    def test_api_error_warns_and_returns_empty(self, capsys):
        backend = make_backend(exc=CoprRequestException("connection failed"))
        assert backend.search_projects("query") == []
        assert "Copr API error" in capsys.readouterr().err


class TestGetProject:
    def test_network_error_returns_none_not_crash(self, capsys):
        backend = make_backend(exc=CoprRequestException("boom"))
        assert backend.get_project("user1", "pkg") is None
        assert "Copr API error" in capsys.readouterr().err

    def test_not_found_returns_none(self, capsys):
        backend = make_backend(exc=CoprNoResultException("nope"))
        assert backend.get_project("user1", "pkg") is None
        assert capsys.readouterr().err == ""


class TestCheckPackageExists:
    def test_found(self):
        backend = make_backend(result=make_project())
        assert backend.check_package_exists("user1", "pkg", "pkg") is True

    def test_not_found(self, capsys):
        backend = make_backend(exc=CoprNoResultException("nope"))
        assert backend.check_package_exists("user1", "pkg", "pkg") is False
        assert capsys.readouterr().err == ""

    def test_api_error_returns_false(self, capsys):
        backend = make_backend(exc=CoprRequestException("boom"))
        assert backend.check_package_exists("user1", "pkg", "pkg") is False
        assert "Copr API error" in capsys.readouterr().err


class TestListPackages:
    def test_returns_name_and_source_name(self):
        packages = [SimpleNamespace(name="ghostty")]
        backend = make_backend(result=packages)
        result = backend.list_packages("user1", "project")
        assert len(result) == 1
        assert result[0].name == "ghostty"
        assert result[0].source_name == "ghostty"
