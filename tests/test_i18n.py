"""Locale detection and translation catalog tests."""

import ast
import json
import string
from pathlib import Path
from types import SimpleNamespace

import pytest

from copa import utils
from copa.commands.admin import cmd_remove
from copa.commands.repo import _repo_list
from copa.config import Config
from copa.dnf_backend import DnfBackend, Package, Repo
from copa.i18n import current_locale, is_chinese, tr


class _RepoDnf:
    def repolist(self, enabled_only=True):
        return [
            Repo(
                id="copr:copr.fedorainfracloud.org:user:project",
                name="Copr repo",
                enabled=True,
            )
        ]


class _Obs:
    def installed_repo_ids(self):
        return set()


class _State:
    copr_repos = []
    obs_repos = []


class _RemoveDnf:
    def __init__(self):
        self.removed = []

    def search_installed(self, keyword):
        return [
            Package("vim-enhanced", "1", "1", "x86_64", "", "installed", "0:1-1"),
            Package("vim-common", "1", "1", "x86_64", "", "installed", "0:1-1"),
        ]

    def remove(self, package):
        self.removed.append(package)
        return True


def _catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "copa" / "locales" / "zh_CN.json"


def _source_keys() -> set[str]:
    keys: set[str] = set()
    root = Path(__file__).resolve().parent.parent / "copa"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


def test_english_by_default():
    assert current_locale() == "c"
    assert not is_chinese()
    assert tr("Searching: {query}").format(query="vim") == "Searching: vim"


def test_zh_cn_locale(monkeypatch):
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
    assert current_locale() == "zh_cn"
    assert is_chinese()
    assert tr("Searching: {query}") == "正在搜索：{query}"
    assert tr("enabled") == "已启用"
    assert tr("blocked") == "已阻止"


@pytest.mark.parametrize("locale_name", ["zh_TW.UTF-8", "en_US.UTF-8", "C", "POSIX"])
def test_non_zh_cn_uses_english(monkeypatch, locale_name):
    monkeypatch.setenv("LC_ALL", locale_name)
    assert not is_chinese()
    assert tr("Searching: {query}") == "Searching: {query}"


def test_lc_all_takes_precedence(monkeypatch):
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert not is_chinese()


def test_language_list_and_lang_fallback(monkeypatch):
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANGUAGE", "zh_CN:en")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert is_chinese()


def test_missing_translation_falls_back(monkeypatch):
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
    assert tr("Not in the catalog") == "Not in the catalog"


def test_catalog_covers_every_source_key():
    catalog = json.loads(_catalog_path().read_text(encoding="utf-8"))
    assert _source_keys() - set(catalog) == set()


def test_catalog_placeholders_match_english():
    catalog = json.loads(_catalog_path().read_text(encoding="utf-8"))
    parser = string.Formatter()
    for english, chinese in catalog.items():
        english_fields = {
            field for _, field, _, _ in parser.parse(english) if field
        }
        chinese_fields = {
            field for _, field, _, _ in parser.parse(chinese) if field
        }
        assert english_fields == chinese_fields, english


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("是", True), ("是的", True), ("否", False), ("不", False), ("y", True), ("n", False)],
)
def test_confirm_accepts_chinese_answers(monkeypatch, answer, expected):
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    assert utils.confirm("Continue?", default=not expected) is expected


def test_chinese_input_aliases():
    assert "搜索" in utils.SEARCH_ANSWERS
    assert "退出" in utils.CANCEL_ANSWERS
    assert "取消" in utils.CANCEL_ANSWERS


def test_remove_accepts_chinese_cancel(monkeypatch):
    dnf = _RemoveDnf()
    monkeypatch.setattr("copa.dnf_backend.DnfBackend", lambda **kw: dnf)
    monkeypatch.setattr("builtins.input", lambda prompt: "退出")
    args = SimpleNamespace(package="vim", assumeyes=False, config=Config())
    assert cmd_remove(args) == 0
    assert dnf.removed == []


def test_repo_list_json_keeps_english_enums(monkeypatch, capsys):
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
    assert _repo_list(_RepoDnf(), _Obs(), _State(), True) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["copr_repos"][0]["status"] == "enabled"
    assert data["copr_repos"][0]["source"] == "system"


def test_audit_json_issues_stay_english(monkeypatch, capsys):
    from copa.commands import admin

    class _AuditDnf:
        def get_fedora_version(self):
            return 44

        def get_chroot(self):
            return "fedora-44-x86_64"

        def is_fedora(self):
            return True

    class _MissingCopr:
        def get_project(self, owner, project):
            return None

    state = SimpleNamespace(
        copr_repos=[SimpleNamespace(owner="user", project="project")],
        obs_repos=[],
    )
    monkeypatch.setattr(admin, "_make_dnf", lambda args: _AuditDnf())
    monkeypatch.setattr("copa.copr_backend.CoprBackend", lambda: _MissingCopr())
    monkeypatch.setattr("copa.state.AppState.load", lambda: state)
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")

    args = SimpleNamespace(config=Config(), json=True)
    assert admin.cmd_audit(args) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["issues"] == [
        "Copr user/project: Project not found or Copr API error"
    ]
    assert data["copr_repos"][0]["status"] == "missing"


def test_dnf_parsing_env_stays_english_under_zh(monkeypatch):
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("copa.dnf_backend.subprocess.run", fake_run)
    backend = DnfBackend(binary="dnf5")
    backend.repolist()
    assert captured["env"]["LANG"] == "C"
    assert captured["env"]["LC_ALL"] == "C"
