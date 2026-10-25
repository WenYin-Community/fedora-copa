"""Regression tests for logic fixes found during code review."""

import re
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from copa import utils
from copa.cli import create_parser
from copa.commands.install import _install_from_copr, _install_from_copr_spec
from copa.commands.search import _regex_seeds
from copa.config import Config, RiskConfig
from copa.copr_backend import CoprBackend, CoprProject
from copa.dnf_backend import DnfBackend
from copa.obs_backend import OBSBackend
from copa.search import SearchEngine
from copa.state import AppState


class _Dnf:
    """Minimal DnfBackend stand-in."""

    binary = "dnf5"

    def __init__(self):
        self.calls = []

    def get_chroot(self):
        return "fedora-44-x86_64"


class _Copr:
    def __init__(self, project):
        self._project = project

    def get_project(self, owner, project):
        return self._project


class _Engine:
    def __init__(self, chroot="fedora-44-x86_64", gap=0, risk="low"):
        self._chroot = chroot
        self._gap = gap
        self._risk = risk

    def _find_best_copr_chroot(self, chroots, chroot, version):
        return self._chroot, self._gap

    def _assess_copr_risk(self, project, supports_chroot, gap):
        return self._risk


class _MultiTermCopr:
    def __init__(self):
        self.queries = []

    def search_projects(self, query):
        self.queries.append(query)
        if query in ("ghostty", "scottames"):
            return [
                CoprProject(
                    "scottames", "ghostty", "", ["fedora-44-x86_64"], ""
                )
            ]
        return []


def test_repoquery_reads_repository_field():
    pkg = DnfBackend._build_package({
        "Name": "ghostty",
        "Version": "1",
        "Release": "1",
        "Architecture": "x86_64",
        "Repository": "fedora",
        "Summary": "",
    })
    assert pkg.repo == "fedora"
    assert pkg.arch == "x86_64"


def test_installed_repoquery_reads_from_repository_field():
    pkg = DnfBackend._build_package({
        "Name": "bash",
        "Version": "1",
        "Release": "1",
        "Architecture": "x86_64",
        "From repository": "fedora",
        "Summary": "",
    })
    assert pkg.repo == "fedora"


def test_search_providers_deduplicates_and_resolves_commands(monkeypatch):
    backend = DnfBackend(binary="dnf5")
    monkeypatch.setattr("copa.dnf_backend.shutil.which", lambda cmd: "/usr/bin/vim")
    backend._query_lines = MagicMock(side_effect=[
        ["vim-enhanced-2:9.2-1.fc44.x86_64"],
        ["vim-enhanced-2:9.2-1.fc44.x86_64"],
    ])
    assert backend.search_providers("vim") == [
        "vim-enhanced-2:9.2-1.fc44.x86_64"
    ]
    queried = [call.args[0] for call in backend._query_lines.call_args_list]
    assert ["repoquery", "--installed", "--file", "vim"] in queried
    assert ["repoquery", "--installed", "--file", "/usr/bin/vim"] in queried


def test_repolist_all_flag():
    backend = DnfBackend(binary="dnf5")
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout="")
        backend.repolist(enabled_only=False)
    assert run.call_args.args[0] == ["dnf5", "repolist", "--all"]


def test_assumeyes_is_passed_to_dnf():
    backend = DnfBackend(binary="dnf5", assumeyes=True)
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        backend.install("htop")
    run.assert_called_once_with(
        ["sudo", "dnf5", "-y", "install", "htop"],
        text=True,
        capture_output=False,
        env=ANY,
        timeout=None,
    )


def test_config_non_table_section_is_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("search = 1\n")
    config = Config.load(path)
    assert config.search.enable_fedora is True


def test_config_wrong_value_type_is_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[search]\nenable_fedora = 'no'\n")
    config = Config.load(path)
    assert config.search.enable_fedora is True


def test_state_tracks_disabled_repos():
    state = AppState()
    state.add_copr_repo("user", "project", "copr:user/project", "fedora-44-x86_64")
    state.add_obs_repo("home:user", "Fedora_44", "home:user.repo", "44")

    assert state.set_copr_enabled("user", "project", False) is True
    assert state.set_obs_enabled("home:user", False) is True
    assert state.copr_repos[0].enabled_by_copa is False
    assert state.obs_repos[0].enabled_by_copa is False


def test_copr_fallback_requires_matching_architecture():
    engine = SearchEngine(
        dnf=None, copr=None, obs=None, risk=RiskConfig()  # type: ignore[arg-type]
    )
    best, gap = engine._find_best_copr_chroot(
        ["fedora-43-aarch64", "fedora-43-x86_64"],
        "fedora-44-x86_64",
        44,
    )
    assert best == "fedora-43-x86_64"
    assert gap == 1

    best, gap = engine._find_best_copr_chroot(
        ["fedora-43-aarch64"], "fedora-44-x86_64", 44
    )
    assert best is None
    assert gap == -1


def test_copr_multi_term_search_merges_and_matches_cross_field():
    copr = _MultiTermCopr()
    engine = SearchEngine(
        dnf=None, copr=copr, obs=None, risk=RiskConfig()  # type: ignore[arg-type]
    )
    results = engine.search_copr(
        "ghostty scottames", "fedora-44-x86_64", 44
    )
    assert copr.queries == ["ghostty", "scottames"]
    assert len(results) == 1
    assert results[0].project.owner == "scottames"


def test_regex_seeds_extract_literals():
    assert _regex_seeds([re.compile("^ghost")]) == ["ghost"]
    assert _regex_seeds([re.compile("vim|neovim")]) == ["vim", "neovim"]
    assert _regex_seeds([re.compile(".*")]) == []


def test_blocked_copr_project_is_not_installed():
    args = SimpleNamespace(assumeyes=True, keep_copr=False, config=Config())
    dnf = _Dnf()
    selected = SimpleNamespace(
        project=SimpleNamespace(owner="user", name="project"),
        risk_level="blocked",
        version_gap=-1,
        best_chroot=None,
    )
    assert _install_from_copr(
        args, dnf, None, None, "pkg", selected, "fedora-44-x86_64"
    ) == 1


def test_explicit_copr_project_bypasses_search(monkeypatch):
    project = SimpleNamespace(
        owner="user", name="project", chroots=["fedora-44-x86_64"]
    )
    called = {}

    def fake_install(*args, **kwargs):
        called["installed"] = True
        return 0

    monkeypatch.setattr(
        "copa.commands.install._install_from_copr", fake_install
    )
    args = SimpleNamespace(copr="user/project")
    rc = _install_from_copr_spec(
        args, _Dnf(), _Copr(project), _Engine(), None, "pkg", 44
    )
    assert rc == 0
    assert called["installed"] is True


def test_obs_disable_uses_dnf5_setopt(monkeypatch):
    backend = OBSBackend()
    monkeypatch.setattr("copa.utils.get_dnf_binary", lambda **kw: "dnf5")
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        assert backend.disable_repo("home:user1") is True
    run.assert_called_once_with(
        ["sudo", "dnf5", "config-manager", "setopt", "home_user1.enabled=0"]
    )
    backend.close()


def test_obs_rejects_path_like_project_names():
    backend = OBSBackend()
    with patch("subprocess.run") as run:
        assert backend.download_repo_file("../evil", "repo") is False
        assert backend.remove_repo_file("../evil") is False
    run.assert_not_called()
    backend.close()


def test_obs_search_packages_by_project(monkeypatch):
    import xml.etree.ElementTree as ET

    backend = OBSBackend()
    captured = {}
    monkeypatch.setattr(backend, "is_available", lambda: True)

    def fake_get(path, params=None):
        captured.update({"path": path, "params": params})
        return ET.fromstring("<collection />")

    monkeypatch.setattr(backend, "_get", fake_get)
    backend.search_packages_by_project("home")
    backend.close()
    assert captured["path"] == "/search/package"
    assert captured["params"]["match"] == "contains(@project,'home')"


def test_obs_installed_repo_ids_reads_obs_files(tmp_path, monkeypatch):
    (tmp_path / "custom.repo").write_text(
        "[devel_tools]\n"
        "name=OBS tools\n"
        "baseurl=https://download.opensuse.org/repositories/devel:/tools/Fedora_44/\n"
    )
    (tmp_path / "fedora.repo").write_text(
        "[fedora]\nbaseurl=https://example.invalid/fedora\n"
    )
    monkeypatch.setattr("copa.obs_backend.OBS_REPO_DIR", tmp_path)
    backend = OBSBackend()
    assert backend.installed_repo_ids() == {"devel_tools"}
    backend.close()


def test_copr_get_builds_uses_pagination():
    backend = CoprBackend.__new__(CoprBackend)
    proxy = MagicMock()
    proxy.get_list.return_value = []
    backend.client = SimpleNamespace(build_proxy=proxy)

    assert backend.get_builds("user", "project", limit=1) == []
    proxy.get_list.assert_called_once_with(
        "user", "project", pagination={"limit": 1}
    )


def test_copr_search_times_out(capsys):
    import time

    backend = CoprBackend.__new__(CoprBackend)
    proxy = MagicMock()
    proxy.search.side_effect = lambda query: time.sleep(0.2) or []
    backend.client = SimpleNamespace(project_proxy=proxy)

    assert backend.search_projects("broad", timeout=0.01) == []
    assert "timed out" in capsys.readouterr().err


def test_read_input_returns_none_on_eof(monkeypatch):
    def raise_eof(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert utils.read_input("prompt") is None


def test_global_json_survives_subparser_defaults():
    args = create_parser().parse_args(["--json", "audit"])
    assert args.json is True

    args = create_parser().parse_args(["--json", "info", "vim"])
    assert args.json is True


def test_search_json_flag_after_subcommand():
    args = create_parser().parse_args(["search", "--json", "vim"])
    assert args.json is True


def test_argparse_source_flags_are_mutually_exclusive():
    parser = create_parser()
    try:
        parser.parse_args(["search", "--official-only", "--copr-only", "vim"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("conflicting source flags were accepted")


def test_repoquery_flags_are_mutually_exclusive():
    parser = create_parser()
    try:
        parser.parse_args(["repoquery", "vim", "--requires", "--files"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("conflicting repoquery flags were accepted")
