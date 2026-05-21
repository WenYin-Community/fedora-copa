"""cli module tests"""

from copa.cli import (
    _filter_by_keywords,
    _filter_by_regex,
    _filter_copr_by_keywords,
    _filter_copr_by_regex,
    _obs_project_exists_in_system,
    _parse_owner_project,
    cmd_search,
    create_parser,
)


class MockPackage:
    """Mock package object"""
    def __init__(self, name, evr="1.0-1.fc43", arch="x86_64", repo="fedora", summary=""):
        self.name = name
        self.evr = evr
        self.arch = arch
        self.repo = repo
        self.summary = summary


class MockCoprProject:
    """Mock Copr project"""
    def __init__(self, owner, name, description=""):
        self.owner = owner
        self.name = name
        self.description = description


class MockCoprResult:
    """Mock Copr search result"""
    def __init__(self, owner, name, description="", supports_chroot=True, risk_level="low"):
        self.project = MockCoprProject(owner, name, description)
        self.supports_chroot = supports_chroot
        self.risk_level = risk_level


class TestSearchParser:
    """Test search arguments"""

    def test_include_local_repo_flag(self):
        args = create_parser().parse_args(["search", "--include-local-repo", "vim"])
        assert args.include_local_repo is True

    def test_obs_flags(self):
        args = create_parser().parse_args(["search", "--obs-only", "--no-obs", "vim"])
        assert args.obs_only is True
        assert args.no_obs is True


class TestCmdSearch:
    """Test search command repo selection"""

    def test_default_skips_local_repos(self, monkeypatch):
        dnf = MockDnfBackend()
        monkeypatch.setattr("copa.dnf_backend.DnfBackend", lambda: dnf)
        monkeypatch.setattr("copa.copr_backend.CoprBackend", lambda: object())
        monkeypatch.setattr("copa.search.SearchEngine", MockSearchEngine)
        args = create_parser().parse_args(["search", "--json", "vim"])

        assert cmd_search(args) == 0
        assert dnf.search_calls == []
        assert MockSearchEngine.last.obs_calls == [("vim", 44)]

    def test_include_local_repo_searches_enabled_repos(self, monkeypatch):
        dnf = MockDnfBackend()
        monkeypatch.setattr("copa.dnf_backend.DnfBackend", lambda: dnf)
        monkeypatch.setattr("copa.copr_backend.CoprBackend", lambda: object())
        monkeypatch.setattr("copa.search.SearchEngine", MockSearchEngine)
        args = create_parser().parse_args(["search", "--json", "--include-local-repo", "vim"])

        assert cmd_search(args) == 0
        assert dnf.search_calls == [
            ("vim", ["fedora"]),
            ("vim", ["rpmfusion-free"]),
            ("vim", ["terra"]),
        ]
        assert MockSearchEngine.last.obs_calls == [("vim", 44)]

    def test_no_obs_skips_obs_search(self, monkeypatch):
        dnf = MockDnfBackend()
        monkeypatch.setattr("copa.dnf_backend.DnfBackend", lambda: dnf)
        monkeypatch.setattr("copa.copr_backend.CoprBackend", lambda: object())
        monkeypatch.setattr("copa.search.SearchEngine", MockSearchEngine)
        args = create_parser().parse_args(["search", "--json", "--no-obs", "vim"])

        assert cmd_search(args) == 0
        assert MockSearchEngine.last.obs_calls == []


class MockDnfBackend:
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
        return []

    def get_chroot(self):
        return "fedora-44-x86_64"

    def get_fedora_version(self):
        return 44


class MockSearchEngine:
    """Mock search engine"""

    last = None

    def __init__(self, dnf, copr):
        self.obs = MockObs()
        self.obs_calls = []
        MockSearchEngine.last = self

    def search_copr(self, keyword, chroot, fedora_version):
        return []

    def search_obs(self, keyword, fedora_version):
        self.obs_calls.append((keyword, fedora_version))
        return []


class MockObs:
    """Mock OBS backend"""

    def is_available(self):
        return True


class TestFilterByKeywords:
    """Test _filter_by_keywords function"""

    def test_single_keyword_match(self):
        """Single keyword match"""
        packages = [
            MockPackage("vim-enhanced", summary="Vim text editor"),
            MockPackage("neovim", summary="Vim-fork text editor"),
            MockPackage("htop", summary="Interactive process viewer"),
        ]
        result = _filter_by_keywords(packages, ["vim"])
        assert len(result) == 2
        assert result[0].name == "vim-enhanced"
        assert result[1].name == "neovim"

    def test_multiple_keywords_and(self):
        """Multiple keywords AND logic"""
        packages = [
            MockPackage("vim-enhanced", summary="Vim text editor"),
            MockPackage("neovim", summary="Vim-fork text editor"),
            MockPackage("vim-python", summary="Python support for vim"),
        ]
        result = _filter_by_keywords(packages, ["vim", "python"])
        assert len(result) == 1
        assert result[0].name == "vim-python"

    def test_no_match(self):
        """No match"""
        packages = [
            MockPackage("htop", summary="Interactive process viewer"),
            MockPackage("git", summary="Version control system"),
        ]
        result = _filter_by_keywords(packages, ["vim"])
        assert len(result) == 0

    def test_case_insensitive(self):
        """Case insensitive"""
        packages = [
            MockPackage("VIM-enhanced", summary="Vim text editor"),
            MockPackage("vim-python", summary="Python support for VIM"),
        ]
        result = _filter_by_keywords(packages, ["vim"])
        assert len(result) == 2

    def test_match_desc_false(self):
        """Does not match description"""
        packages = [
            MockPackage("vim-enhanced", summary="Text editor"),
            MockPackage("nano", summary="Vim-like editor"),
        ]
        result = _filter_by_keywords(packages, ["vim"], match_desc=False)
        assert len(result) == 1
        assert result[0].name == "vim-enhanced"


class TestFilterByRegex:
    """Test _filter_by_regex function"""

    def test_basic_regex(self):
        """Basic regex match"""
        import re
        packages = [
            MockPackage("vim-enhanced"),
            MockPackage("neovim"),
            MockPackage("htop"),
        ]
        patterns = [re.compile("^vim")]
        result = _filter_by_regex(packages, patterns)
        assert len(result) == 1
        assert result[0].name == "vim-enhanced"

    def test_complex_regex(self):
        """Complex regex match"""
        import re
        packages = [
            MockPackage("python3.11"),
            MockPackage("python3.12"),
            MockPackage("python2.7"),
        ]
        patterns = [re.compile(r"python3\.\d+")]
        result = _filter_by_regex(packages, patterns)
        assert len(result) == 2

    def test_multiple_patterns_and(self):
        """Multiple regex AND logic"""
        import re
        packages = [
            MockPackage("python3-devel"),
            MockPackage("python3-libs"),
            MockPackage("python2-devel"),
        ]
        patterns = [re.compile("python3"), re.compile("devel")]
        result = _filter_by_regex(packages, patterns)
        assert len(result) == 1
        assert result[0].name == "python3-devel"

    def test_no_match(self):
        """No match"""
        import re
        packages = [
            MockPackage("vim"),
            MockPackage("htop"),
        ]
        patterns = [re.compile("^python")]
        result = _filter_by_regex(packages, patterns)
        assert len(result) == 0


class TestFilterCoprByKeywords:
    """Test _filter_copr_by_keywords function"""

    def test_single_keyword(self):
        """Single keyword match"""
        results = [
            MockCoprResult("user1", "ghostty", "Terminal emulator"),
            MockCoprResult("user2", "ghostty-build", "Ghostty build scripts"),
            MockCoprResult("user3", "htop", "Process viewer"),
        ]
        result = _filter_copr_by_keywords(results, ["ghostty"])
        assert len(result) == 2

    def test_match_owner(self):
        """Match owner"""
        results = [
            MockCoprResult("python", "cpython", "Python interpreter"),
            MockCoprResult("python", "pypy", "PyPy interpreter"),
            MockCoprResult("user", "myproject", "My project"),
        ]
        result = _filter_copr_by_keywords(results, ["python"])
        assert len(result) == 2

    def test_no_match_description(self):
        """Does not match description"""
        results = [
            MockCoprResult("user1", "myapp", "Fast terminal emulator"),
            MockCoprResult("user2", "other", "Terminal multiplexer"),
            MockCoprResult("user3", "tool", "File manager"),
        ]
        result = _filter_copr_by_keywords(results, ["terminal"])
        assert len(result) == 0


class TestFilterCoprByRegex:
    """Test _filter_copr_by_regex function"""

    def test_basic_regex(self):
        """Basic regex match"""
        import re
        results = [
            MockCoprResult("user1", "ghostty"),
            MockCoprResult("user2", "ghostty-build"),
            MockCoprResult("user3", "htop"),
        ]
        patterns = [re.compile("^ghostty")]
        result = _filter_copr_by_regex(results, patterns)
        assert len(result) == 2

    def test_complex_regex(self):
        """Complex regex match"""
        import re
        results = [
            MockCoprResult("user1", "python3.11"),
            MockCoprResult("user2", "python3.12"),
            MockCoprResult("user3", "python2.7"),
        ]
        patterns = [re.compile(r"python3\.\d+")]
        result = _filter_copr_by_regex(results, patterns)
        assert len(result) == 2


class TestParseOwnerProject:
    """Test OWNER/PROJECT parsing"""

    def test_valid(self):
        assert _parse_owner_project("user/project") == ("user", "project")

    def test_invalid(self):
        assert _parse_owner_project("userproject") is None
        assert _parse_owner_project("/project") is None
        assert _parse_owner_project("user/") is None


class TestObsProjectExistsInSystem:
    """Test OBS project deduplication"""

    def test_match_normalized(self):
        repo_ids = {"home_user1"}
        assert _obs_project_exists_in_system("home:user1", repo_ids) is True

    def test_not_exists(self):
        repo_ids = {"home_other"}
        assert _obs_project_exists_in_system("home:user1", repo_ids) is False
