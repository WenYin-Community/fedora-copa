"""dnf_backend 模块测试"""

import pytest
from unittest.mock import patch, MagicMock
from copa.dnf_backend import DnfBackend, Package, Repo


class TestDnfBackend:
    """测试 DnfBackend 类"""

    def test_init_dnf5(self):
        """初始化使用 dnf5"""
        backend = DnfBackend(use_dnf5=True)
        assert backend._binary == "dnf5"

    def test_init_dnf(self):
        """初始化使用 dnf"""
        backend = DnfBackend(use_dnf5=False)
        assert backend._binary == "dnf"

    @patch("subprocess.run")
    def test_run_command(self, mock_run):
        """执行命令"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        backend = DnfBackend()
        backend._run(["repolist", "--enabled"])
        mock_run.assert_called_once_with(
            ["dnf5", "repolist", "--enabled"],
            capture_output=True,
            text=True,
        )

    @patch("subprocess.run")
    def test_run_command_with_sudo(self, mock_run):
        """执行 sudo 命令"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        backend = DnfBackend()
        backend._run(["install", "htop"], sudo=True)
        mock_run.assert_called_once_with(
            ["sudo", "dnf5", "install", "htop"],
            capture_output=True,
            text=True,
        )

    def test_parse_repolist(self):
        """解析 repolist 输出"""
        backend = DnfBackend()
        output = """repo id                                                             repo name
fedora                                                              Fedora 44 - x86_64
updates                                                             Fedora 44 - x86_64 - Updates
copr:copr.fedorainfracloud.org:user:project                         Copr repo"""
        repos = backend._parse_repolist(output)
        assert len(repos) == 3
        assert repos[0].id == "fedora"
        assert repos[0].name == "Fedora 44 - x86_64"
        assert repos[2].id == "copr:copr.fedorainfracloud.org:user:project"

    def test_get_enabled_repos(self):
        """获取已启用仓库分类"""
        backend = DnfBackend()
        # Mock repolist 方法
        backend.repolist = MagicMock(return_value=[
            Repo(id="fedora", name="Fedora", enabled=True),
            Repo(id="updates", name="Updates", enabled=True),
            Repo(id="rpmfusion-free", name="RPM Fusion Free", enabled=True),
            Repo(id="terra", name="Terra", enabled=True),
            Repo(id="copr:user:project", name="Copr", enabled=True),
            Repo(id="home_user", name="OBS", enabled=True),
        ])
        repos = backend.get_enabled_repos()
        assert "fedora" in repos
        assert "copr" in repos
        assert "obs" in repos

    @patch("subprocess.run")
    def test_copr_enable(self, mock_run):
        """启用 Copr 仓库"""
        mock_run.return_value = MagicMock(returncode=0)
        backend = DnfBackend()
        result = backend.copr_enable("user/project", "fedora-43-x86_64")
        assert result is True

    @patch("subprocess.run")
    def test_copr_disable(self, mock_run):
        """禁用 Copr 仓库"""
        mock_run.return_value = MagicMock(returncode=0)
        backend = DnfBackend()
        result = backend.copr_disable("user/project")
        assert result is True

    @patch("subprocess.run")
    def test_install_package(self, mock_run):
        """安装包"""
        mock_run.return_value = MagicMock(returncode=0)
        backend = DnfBackend()
        result = backend.install("htop")
        assert result is True

    @patch("subprocess.run")
    def test_makecache(self, mock_run):
        """刷新缓存"""
        mock_run.return_value = MagicMock(returncode=0)
        backend = DnfBackend()
        result = backend.makecache()
        assert result is True


class TestPackage:
    """测试 Package 数据类"""

    def test_create_package(self):
        """创建包对象"""
        pkg = Package(
            name="htop",
            version="3.2.2",
            release="1.fc43",
            arch="x86_64",
            summary="Interactive process viewer",
            repo="fedora",
            evr="0:3.2.2-1.fc43",
        )
        assert pkg.name == "htop"
        assert pkg.version == "3.2.2"
        assert pkg.arch == "x86_64"


class TestRepo:
    """测试 Repo 数据类"""

    def test_create_repo(self):
        """创建仓库对象"""
        repo = Repo(id="fedora", name="Fedora 44", enabled=True)
        assert repo.id == "fedora"
        assert repo.name == "Fedora 44"
        assert repo.enabled is True
