"""config 模块测试"""

import pytest
import tempfile
from pathlib import Path
from copa.config import (
    Config,
    SearchConfig,
    InstallConfig,
    BackendConfig,
    UIConfig,
    RiskConfig,
)


@pytest.fixture
def temp_config_file(tmp_path):
    """创建临时配置文件"""
    return tmp_path / "config.toml"


@pytest.fixture
def sample_config():
    """创建示例配置"""
    config = Config()
    config.search.enable_fedora = True
    config.search.enable_rpmfusion = False
    config.install.default_copr_post_action = "disable"
    config.backend.prefer_dnf5 = True
    return config


class TestSearchConfig:
    """测试 SearchConfig"""

    def test_default_values(self):
        """默认值"""
        config = SearchConfig()
        assert config.enable_fedora is True
        assert config.enable_rpmfusion is True
        assert config.enable_terra_if_present is True
        assert config.enable_copr is True

    def test_custom_values(self):
        """自定义值"""
        config = SearchConfig(enable_fedora=False, enable_copr=False)
        assert config.enable_fedora is False
        assert config.enable_copr is False


class TestInstallConfig:
    """测试 InstallConfig"""

    def test_default_values(self):
        """默认值"""
        config = InstallConfig()
        assert config.default_copr_post_action == "disable"
        assert config.strict_selected_repo is True


class TestConfig:
    """测试 Config"""

    def test_create_default_config(self):
        """创建默认配置"""
        config = Config()
        assert config.search.enable_fedora is True
        assert config.install.default_copr_post_action == "disable"

    def test_save_and_load(self, temp_config_file, sample_config):
        """保存和加载配置"""
        sample_config.save(temp_config_file)
        loaded = Config.load(temp_config_file)
        assert loaded.search.enable_fedora is True
        assert loaded.search.enable_rpmfusion is False
        assert loaded.install.default_copr_post_action == "disable"

    def test_load_nonexistent_file(self, temp_config_file):
        """加载不存在的文件"""
        config = Config.load(temp_config_file)
        assert config.search.enable_fedora is True  # 默认值

    def test_load_invalid_file(self, temp_config_file):
        """加载无效文件"""
        temp_config_file.write_text("invalid toml")
        config = Config.load(temp_config_file)
        assert config.search.enable_fedora is True  # 默认值

    def test_generate_example(self, temp_config_file):
        """生成示例配置"""
        Config.generate_example(temp_config_file)
        assert temp_config_file.exists()
        content = temp_config_file.read_text()
        assert "enable_fedora = true" in content
        assert "default_copr_post_action" in content
