"""obs_backend module tests"""

import xml.etree.ElementTree as ET

from copa.obs_backend import OBSBackend, OBSRepo, _xpath_string_literal


def test_xpath_string_literal():
    assert _xpath_string_literal("ghostty") == "'ghostty'"
    assert _xpath_string_literal('a"b') == '\'a"b\''
    assert _xpath_string_literal("o'brien").replace(" ", "") == "concat('o',\"'\",'brien')"


def test_search_projects_match_escaped(monkeypatch):
    backend = OBSBackend()
    captured = {}
    monkeypatch.setattr(backend, "is_available", lambda: True)

    def fake_get(path, params=None):
        captured.update({"path": path, "params": params})
        return ET.fromstring("<collection />")

    monkeypatch.setattr(
        backend,
        "_get",
        fake_get,
    )
    backend.search_projects("o'brien")
    backend.close()
    assert captured["path"] == "/search/project"
    assert captured["params"]["match"].replace(" ", "") == (
        "contains(@name,concat('o',\"'\",'brien'))"
    )


def test_search_packages_match_escaped(monkeypatch):
    backend = OBSBackend()
    captured = {}
    monkeypatch.setattr(backend, "is_available", lambda: True)

    def fake_get(path, params=None):
        captured.update({"path": path, "params": params})
        return ET.fromstring("<collection />")

    monkeypatch.setattr(
        backend,
        "_get",
        fake_get,
    )
    backend.search_packages("a'b")
    backend.close()
    assert captured["path"] == "/search/package"
    assert captured["params"]["match"].replace(" ", "") == "contains(@name,concat('a',\"'\",'b'))"


def test_find_fedora_repos_rawhide(monkeypatch):
    """On rawhide (version 0) the newest Fedora repo counts as current"""
    backend = OBSBackend()
    repos = [
        OBSRepo("p", "Fedora_44", "u", "44", False, 0),
        OBSRepo("p", "Fedora_42", "u", "42", False, 0),
    ]
    monkeypatch.setattr(backend, "get_project_repos", lambda project: repos)

    found = backend.find_fedora_repos("p", 0)

    assert len(found) == 2
    assert found[0].is_current_version is True
    assert found[0].fedora_version == "44"
    assert found[1].is_current_version is False


def test_find_fedora_repos_current_version(monkeypatch):
    """Normal systems prefer the exact version and allow up to 2 fallbacks"""
    backend = OBSBackend()
    repos = [
        OBSRepo("p", "Fedora_44", "u", "44", False, 0),
        OBSRepo("p", "Fedora_42", "u", "42", False, 0),
        OBSRepo("p", "Fedora_41", "u", "41", False, 0),
    ]
    monkeypatch.setattr(backend, "get_project_repos", lambda project: repos)

    found = backend.find_fedora_repos("p", 44)

    assert len(found) == 2  # Fedora_41 (gap 3) is rejected
    assert found[0].is_current_version is True
    assert found[1].version_gap == 2
