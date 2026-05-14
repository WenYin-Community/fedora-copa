"""cli 模块测试"""

from copa.cli import (
    _filter_by_keywords,
    _filter_by_regex,
    _filter_copr_by_keywords,
    _filter_copr_by_regex,
)


class MockPackage:
    """模拟包对象"""
    def __init__(self, name, evr="1.0-1.fc43", arch="x86_64", repo="fedora", summary=""):
        self.name = name
        self.evr = evr
        self.arch = arch
        self.repo = repo
        self.summary = summary


class MockCoprProject:
    """模拟 Copr 项目"""
    def __init__(self, owner, name, description=""):
        self.owner = owner
        self.name = name
        self.description = description


class MockCoprResult:
    """模拟 Copr 搜索结果"""
    def __init__(self, owner, name, description="", supports_chroot=True, risk_level="low"):
        self.project = MockCoprProject(owner, name, description)
        self.supports_chroot = supports_chroot
        self.risk_level = risk_level


class TestFilterByKeywords:
    """测试 _filter_by_keywords 函数"""

    def test_single_keyword_match(self):
        """单关键词匹配"""
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
        """多关键词 AND 逻辑"""
        packages = [
            MockPackage("vim-enhanced", summary="Vim text editor"),
            MockPackage("neovim", summary="Vim-fork text editor"),
            MockPackage("vim-python", summary="Python support for vim"),
        ]
        result = _filter_by_keywords(packages, ["vim", "python"])
        assert len(result) == 1
        assert result[0].name == "vim-python"

    def test_no_match(self):
        """无匹配"""
        packages = [
            MockPackage("htop", summary="Interactive process viewer"),
            MockPackage("git", summary="Version control system"),
        ]
        result = _filter_by_keywords(packages, ["vim"])
        assert len(result) == 0

    def test_case_insensitive(self):
        """大小写不敏感"""
        packages = [
            MockPackage("VIM-enhanced", summary="Vim text editor"),
            MockPackage("vim-python", summary="Python support for VIM"),
        ]
        result = _filter_by_keywords(packages, ["vim"])
        assert len(result) == 2

    def test_match_desc_false(self):
        """不匹配描述"""
        packages = [
            MockPackage("vim-enhanced", summary="Text editor"),
            MockPackage("nano", summary="Vim-like editor"),
        ]
        result = _filter_by_keywords(packages, ["vim"], match_desc=False)
        assert len(result) == 1
        assert result[0].name == "vim-enhanced"


class TestFilterByRegex:
    """测试 _filter_by_regex 函数"""

    def test_basic_regex(self):
        """基本正则匹配"""
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
        """复杂正则匹配"""
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
        """多正则 AND 逻辑"""
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
        """无匹配"""
        import re
        packages = [
            MockPackage("vim"),
            MockPackage("htop"),
        ]
        patterns = [re.compile("^python")]
        result = _filter_by_regex(packages, patterns)
        assert len(result) == 0


class TestFilterCoprByKeywords:
    """测试 _filter_copr_by_keywords 函数"""

    def test_single_keyword(self):
        """单关键词匹配"""
        results = [
            MockCoprResult("user1", "ghostty", "Terminal emulator"),
            MockCoprResult("user2", "ghostty-build", "Ghostty build scripts"),
            MockCoprResult("user3", "htop", "Process viewer"),
        ]
        result = _filter_copr_by_keywords(results, ["ghostty"])
        assert len(result) == 2

    def test_match_owner(self):
        """匹配 owner"""
        results = [
            MockCoprResult("python", "cpython", "Python interpreter"),
            MockCoprResult("python", "pypy", "PyPy interpreter"),
            MockCoprResult("user", "myproject", "My project"),
        ]
        result = _filter_copr_by_keywords(results, ["python"])
        assert len(result) == 2

    def test_match_description(self):
        """匹配描述"""
        results = [
            MockCoprResult("user1", "myapp", "Fast terminal emulator"),
            MockCoprResult("user2", "other", "Terminal multiplexer"),
            MockCoprResult("user3", "tool", "File manager"),
        ]
        result = _filter_copr_by_keywords(results, ["terminal"])
        assert len(result) == 2


class TestFilterCoprByRegex:
    """测试 _filter_copr_by_regex 函数"""

    def test_basic_regex(self):
        """基本正则匹配"""
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
        """复杂正则匹配"""
        import re
        results = [
            MockCoprResult("user1", "python3.11"),
            MockCoprResult("user2", "python3.12"),
            MockCoprResult("user3", "python2.7"),
        ]
        patterns = [re.compile(r"python3\.\d+")]
        result = _filter_copr_by_regex(results, patterns)
        assert len(result) == 2
