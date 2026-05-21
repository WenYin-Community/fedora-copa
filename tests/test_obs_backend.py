"""obs_backend module tests"""

import xml.etree.ElementTree as ET

from copa.obs_backend import OBSBackend, _xpath_string_literal


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
